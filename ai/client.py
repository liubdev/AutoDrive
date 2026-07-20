"""
AI client - LLM API wrapper (OpenAI / compatible / local)
"""
import json
import logging
from typing import Optional, List, Dict, Any, Callable

from config import settings

logger = logging.getLogger("autocar.ai")


class AIClient:
    """
    AI client - interacts with LLM for intelligent automation

    Supports:
        - OpenAI API / compatible endpoints
        - Structured output (function calling)
        - Multi-turn conversation context
        - Retry and timeout
    """

    def __init__(self, model: str = None, api_key: str = None,
                 api_base: str = None, temperature: float = None):
        self.model = model or settings.ai_model
        self.api_key = api_key or settings.api_key
        self.api_base = api_base or settings.api_base
        self.temperature = temperature or settings.ai_temperature
        self.max_tokens = settings.ai_max_tokens
        self._client = None

    def _ensure_client(self):
        """Initialize the OpenAI client"""
        if self._client is not None:
            return True
        try:
            from openai import OpenAI
            kwargs = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.api_base:
                kwargs["base_url"] = self.api_base
            self._client = OpenAI(**kwargs)
            logger.info(f"AI client ready (model={self.model})")
            return True
        except ImportError:
            logger.error("openai not installed: pip install openai")
            return False
        except Exception as e:
            logger.error(f"AI client init failed: {e}")
            return False

    def chat(self, messages: List[Dict], tools: List[Dict] = None,
             json_mode: bool = False, max_tokens: int = None) -> Dict:
        """
        Send a chat message

        Args:
            messages: [{"role": "user", "content": "..."}]
            tools: function calling tool definitions
            json_mode: force JSON output
        Returns:
            full response object
        """
        if not self._ensure_client():
            return {"error": "AI client not ready"}

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            resp = self._client.chat.completions.create(**kwargs)
            return resp
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return {"error": str(e)}

    def chat_simple(self, prompt: str, system: str = None) -> str:
        """Simple chat - returns text response"""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self.chat(messages)
        if "error" in resp:
            return f"[AI Error] {resp['error']}"

        try:
            return resp.choices[0].message.content or ""
        except Exception:
            return ""

    def chat_json(self, prompt: str, system: str = None) -> Dict:
        """
        Chat - force JSON output

        Returns:
            parsed JSON dict, or {"error": "..."}
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self.chat(messages, json_mode=True)
        if "error" in resp:
            return {"error": resp["error"]}

        try:
            content = resp.choices[0].message.content or "{}"
            return json.loads(content)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"JSON parse failed: {e}")
            return {"error": f"JSON parse failed: {e}"}

    def function_call(self, messages: List[Dict],
                      tools: List[Dict]) -> Optional[Dict]:
        """
        Call function calling

        Returns:
            {"name": "...", "arguments": {...}} or None
        """
        resp = self.chat(messages, tools=tools)
        if "error" in resp:
            logger.error(f"Function call failed: {resp['error']}")
            return None

        try:
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return None

            tc = msg.tool_calls[0]
            return {
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments),
            }
        except (AttributeError, json.JSONDecodeError) as e:
            logger.error(f"Failed to parse tool_calls: {e}")
            return None

    def function_loop(self, messages: List[Dict],
                      tools: List[Dict],
                      tool_handlers: Dict[str, Callable],
                      max_rounds: int = 10) -> List[Dict]:
        """
        Multi-turn function calling loop - auto-execute tools until done

        Args:
            messages: initial conversation
            tools: tool definitions
            tool_handlers: {"tool_name": handler_func}
            max_rounds: max iterations
        Returns:
            full message history
        """
        for _ in range(max_rounds):
            resp = self.chat(messages, tools=tools)
            if "error" in resp:
                break

            msg = resp.choices[0].message
            messages.append({"role": "assistant", "content": msg.content,
                             "tool_calls": msg.tool_calls} if msg.tool_calls
                            else {"role": "assistant", "content": msg.content})

            if not msg.tool_calls:
                break

            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments)
                handler = tool_handlers.get(fn_name)

                if handler:
                    logger.info(f"Executing tool: {fn_name}({fn_args})")
                    try:
                        result = handler(**fn_args)
                    except Exception as e:
                        result = {"error": str(e)}
                else:
                    result = {"error": f"Unknown tool: {fn_name}"}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return messages

    def is_available(self) -> bool:
        """Check if AI service is available"""
        return self._ensure_client()

    @property
    def model_name(self) -> str:
        return self.model

"""
DeepSeek API 客户端（OpenAI 兼容，纯标准库实现）。

- 请求: POST {base_url}/chat/completions
- 鉴权: Authorization: Bearer <api_key>
- 模型: deepseek-chat（默认）/ deepseek-reasoner
- 依赖: 仅 urllib，无第三方包（打包 exe 不需要额外 hidden-import）

key 读取优先级：构造参数 > config.settings.api_key (data/config.json) > 环境变量 DEEPSEEK_API_KEY。

线程安全：本类无共享可变状态，可在后台线程调用（阻塞式）。
"""

import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request

log = logging.getLogger("autodrive.ai.deepseek")


class AiError(Exception):
    """AI 调用失败（消息面向用户，可直接展示）"""


class DeepSeekClient:
    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        timeout: int = None,
        max_tokens: int = None,
        temperature: float = None,
        retries: int = 2,
    ):
        # 未显式传参 → 从 settings（data/config.json）取默认
        try:
            from config.settings import settings as cfg
        except Exception:
            cfg = None

        def _s(attr, default):
            return getattr(cfg, attr, None) or default

        self.api_key = api_key if api_key else self._resolve_key()
        self.base_url = (base_url or _s("api_base", "https://api.deepseek.com")).rstrip("/")
        self.model = model or _s("ai_model", "deepseek-chat")
        self.timeout = timeout if timeout is not None else _s("ai_timeout", 120)
        self.max_tokens = max_tokens if max_tokens is not None else _s("ai_max_tokens", 4000)
        self.temperature = temperature if temperature is not None else _s("ai_temperature", 0.2)
        self.retries = retries

    # ── 配置 ──────────────────────────────────────

    @staticmethod
    def _resolve_key() -> str:
        """参数未给 key 时：config.json → 环境变量"""
        try:
            from config.settings import settings
            key = getattr(settings, "api_key", None)
            if key:
                return str(key).strip()
        except Exception:
            pass
        return os.environ.get("DEEPSEEK_API_KEY", "").strip()

    @property
    def configured(self) -> bool:
        """是否已配置可用 key"""
        return bool(self.api_key)

    # ── 主调用 ────────────────────────────────────

    def chat(
        self,
        messages: list,
        max_tokens: int = None,
        temperature: float = None,
    ) -> str:
        """
        发送对话并返回模型文本。

        Args:
            messages: [{"role": "system"|"user", "content": "..."}]
            max_tokens / temperature: 单次覆盖默认值

        Returns:
            choices[0].message.content

        Raises:
            AiError: 未配置 key / 鉴权失败 / 请求被拒 / 超时 / 网络错误 / 解析失败
        """
        if not self.api_key:
            raise AiError(
                "未配置 DeepSeek API Key。请设置环境变量 DEEPSEEK_API_KEY，"
                "或在 data/config.json 中填写 api_key 字段。"
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": (
                temperature if temperature is not None else self.temperature
            ),
            "stream": False,
        }
        url = f"{self.base_url}/chat/completions"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        last_err: AiError = None
        for attempt in range(1, self.retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers,
                                             method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                content = self._extract_content(body)
                return content

            except urllib.error.HTTPError as e:
                detail = self._read_err_body(e)
                if e.code in (401, 403):
                    raise AiError(
                        f"DeepSeek 鉴权失败（HTTP {e.code}），请检查 API Key"
                    ) from e
                if e.code in (400, 404, 422, 429):
                    raise AiError(
                        f"DeepSeek 请求被拒（HTTP {e.code}）：{detail}"
                    ) from e
                # 5xx 等：可重试
                last_err = AiError(f"DeepSeek 服务异常（HTTP {e.code}）：{detail}")
            except urllib.error.URLError as e:
                last_err = AiError(f"无法连接 DeepSeek：{e.reason}")
            except (socket.timeout, TimeoutError) as e:
                last_err = AiError(f"DeepSeek 请求超时（>{self.timeout}s）")
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
                raise AiError(f"DeepSeek 返回内容解析失败：{e}") from e
            except Exception as e:  # noqa: BLE001 —— 兜底，转成用户可读错误
                last_err = AiError(f"AI 调用异常：{e}")

            if attempt < self.retries:
                time.sleep(1.0 * attempt)  # 退避后重试
                log.warning("DeepSeek 调用重试 %d/%d", attempt + 1, self.retries)

        raise last_err or AiError("AI 请求失败")

    # ── 解析 ──────────────────────────────────────

    @staticmethod
    def _extract_content(body: str) -> str:
        parsed = json.loads(body)
        content = parsed["choices"][0]["message"]["content"]
        return content or ""

    @staticmethod
    def _read_err_body(e: urllib.error.HTTPError) -> str:
        try:
            return e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            return ""

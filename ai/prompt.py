"""
Prompt engineering - system prompts and templates for automation tasks
"""
import json
from typing import List, Dict, Any


class PromptBuilder:
    """
    Build prompts for AI-powered automation
    """

    # -- System prompts --

    SYSTEM_PLAN = """You are a Windows desktop application automation expert. Your task is to analyze the current UI state,
create an action plan, and execute it step by step using function calls.

Core principles:
1. **Use control-driven approach** - prefer auto_id, name, control_type for locating elements
2. **Robust first** - ensure controls are visible and enabled before each action
3. **Step by step** - one action at a time, confirm each result
4. **Report errors** - don't retry blindly, analyze alternatives

When the task is complete, respond with "【DONE】" and a summary."""

    SYSTEM_PLAN_SIMPLE = """Convert natural language automation requirements into structured step-by-step plans.
Output in JSON format with action type and parameters for each step.
Use UIA control-based element location."""

    SYSTEM_CODE_GEN = """You are a Windows UI automation script generator.
Generate Python code using the autocar framework based on natural language descriptions.
Generated code should:
- Use AppDriver for process management
- Use Locator for element location
- Use Actions for element interaction
- Include error handling
- Include appropriate logging and waits"""

    # -- Plan generation template --

    @staticmethod
    def plan_from_goal(goal: str, ui_context: Dict = None) -> str:
        """
        Generate a plan prompt from a user goal

        Args:
            goal: user goal description
            ui_context: current UI context (control tree)
        """
        parts = [f"User goal: {goal}\n"]
        if ui_context:
            parts.append("Current UI state:\n")
            parts.append(json.dumps(ui_context, indent=2, ensure_ascii=False)[:3000])
            parts.append("\n")

        parts.append("""
Please output an action plan in JSON format:
{
    "steps": [
        {
            "action": "click|input|select|wait|scroll|keyboard|launch|close",
            "target": "control description (button text/auto_id/name)",
            "value": "input value or parameter",
            "description": "what this step does"
        }
    ],
    "expected": "expected result description"
}
""")
        return "".join(parts)

    @staticmethod
    def analyze_screenshot(goal: str) -> str:
        """Prompt for screenshot analysis"""
        return f"""User goal: {goal}

Analyze this screenshot and identify the UI elements (buttons, inputs, lists, etc.).
Describe which controls need to be interacted with and their positions. Focus on:
1. Controls related to the goal
2. Control types and readable text
3. Action sequence"""

    @staticmethod
    def fix_error(goal: str, error: str, step: str, context: Dict = None) -> str:
        """Error recovery prompt"""
        prompt = f"""Automation execution encountered an error.

Goal: {goal}
Failed step: {step}
Error: {error}
"""
        if context:
            prompt += f"\nCurrent state: {json.dumps(context, indent=2, ensure_ascii=False)[:2000]}"

        prompt += "\n\nAnalyze the failure and propose a fix (use the original strategy or try alternatives)."
        return prompt

    # -- Function calling tool definitions --

    @staticmethod
    def get_action_tools() -> List[Dict]:
        """Get action tool definitions for function calling"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "click",
                    "description": "Click a control",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string", "description": "Control descriptor (text/auto_id/name)"},
                            "by": {"type": "string", "enum": ["text", "auto_id", "name", "type", "class"],
                                   "description": "Locator strategy"},
                        },
                        "required": ["target", "by"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "input_text",
                    "description": "Type text into an input box",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string", "description": "Input control descriptor"},
                            "text": {"type": "string", "description": "Text to input"},
                            "clear_first": {"type": "boolean", "description": "Clear existing content first", "default": True},
                        },
                        "required": ["target", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "select",
                    "description": "Select an item from a combobox or list",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {"type": "string", "description": "Control descriptor"},
                            "item": {"type": "string", "description": "Item text to select"},
                        },
                        "required": ["target", "item"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wait",
                    "description": "Wait for a specified time or for a control to appear",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "seconds": {"type": "number", "description": "Seconds to wait"},
                            "target": {"type": "string", "description": "Optional control to wait for"},
                        },
                        "required": ["seconds"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "send_keys",
                    "description": "Send keyboard keys",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "keys": {"type": "string", "description": "Key combination, e.g. ^a (Ctrl+A), {ENTER}"},
                        },
                        "required": ["keys"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "screenshot",
                    "description": "Take a screenshot of the current screen",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "task_complete",
                    "description": "Mark the task as complete",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "description": "Execution summary"},
                            "success": {"type": "boolean", "description": "Whether the task was successful"},
                        },
                        "required": ["summary", "success"],
                    },
                },
            },
        ]

    @staticmethod
    def get_explorer_tools() -> List[Dict]:
        """UI explorer tool definitions"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "explore_window",
                    "description": "Explore the current window structure",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Window title keyword"},
                            "depth": {"type": "integer", "description": "Traversal depth", "default": 5},
                        },
                        "required": ["title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "find_control",
                    "description": "Find a specific control by its properties",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "auto_id": {"type": "string", "description": "AutomationId"},
                            "control_type": {"type": "string", "description": "Control type"},
                            "name": {"type": "string", "description": "Control name"},
                            "text": {"type": "string", "description": "Text content"},
                        },
                        "required": [],
                    },
                },
            },
        ]

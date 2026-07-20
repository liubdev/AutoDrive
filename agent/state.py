"""
Runtime state - tracks automation execution context
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List
from datetime import datetime

logger = logging.getLogger("autocar.state")


class AutoState:
    """
    Automation runtime state manager

    Tracks:
        - Current process/window
        - Step execution history
        - Errors and recovery info
        - User-defined variables
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all state"""
        self.process_id: Optional[int] = None
        self.process_path: Optional[str] = None
        self.window_handle: Optional[int] = None
        self.window_title: Optional[str] = None

        self.steps: List[Dict] = []
        self.current_step_index: int = -1
        self.step_count: int = 0
        self.success_count: int = 0
        self.fail_count: int = 0

        self.start_time: Optional[datetime] = None
        self.last_action_time: Optional[datetime] = None
        self.status: str = "idle"  # idle | running | paused | error | done

        self.variables: Dict[str, Any] = {}

        self.last_error: Optional[str] = None
        self.retry_count: int = 0
        self.max_retries: int = 3

        self.context: Dict[str, Any] = {}

    def record_step(self, action: str, target: str = "",
                    result: bool = True, detail: str = ""):
        """Record an operation step"""
        step = {
            "index": self.step_count,
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "target": target,
            "result": "success" if result else "fail",
            "detail": detail,
            "elapsed_ms": self._elapsed_since_start(),
        }
        self.steps.append(step)
        self.step_count += 1
        self.current_step_index = step["index"]
        self.last_action_time = datetime.now()

        if result:
            self.success_count += 1
        else:
            self.fail_count += 1

        logger.debug(f"Step {step['index']}: {action} -> {step['result']}")
        return step

    def _elapsed_since_start(self) -> int:
        if self.start_time:
            return int((datetime.now() - self.start_time).total_seconds() * 1000)
        return 0

    def mark_running(self):
        """Mark as running"""
        self.status = "running"
        self.start_time = datetime.now()

    def mark_done(self, success: bool = True):
        """Mark as done"""
        self.status = "done" if success else "error"

    def mark_paused(self):
        self.status = "paused"

    def mark_idle(self):
        self.status = "idle"

    def set_error(self, error_msg: str):
        """Record an error"""
        self.last_error = error_msg
        self.fail_count += 1
        self.status = "error"

    def can_retry(self) -> bool:
        """Check if we can still retry"""
        return self.retry_count < self.max_retries

    def do_retry(self):
        """Increment retry counter"""
        self.retry_count += 1

    def reset_retry(self):
        self.retry_count = 0

    def set(self, key: str, value: Any):
        """Set a variable"""
        self.variables[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a variable"""
        return self.variables.get(key, default)

    def summary(self) -> Dict:
        """Generate execution summary"""
        elapsed = self._elapsed_since_start() if self.start_time else 0
        return {
            "status": self.status,
            "steps_total": self.step_count,
            "success": self.success_count,
            "failures": self.fail_count,
            "elapsed_ms": elapsed,
            "last_error": self.last_error,
            "window": self.window_title,
            "variables": dict(self.variables),
        }

    def export(self, path: str = None) -> str:
        """Export execution report to JSON"""
        report = {
            "summary": self.summary(),
            "steps": self.steps,
            "context": {k: str(v) for k, v in self.context.items()},
        }
        output = path or str(
            Path.cwd() / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Report exported: {output}")
        return output

    def update_window(self, title: str = None, handle: int = None):
        """Update window info"""
        if title:
            self.window_title = title
        if handle:
            self.window_handle = handle

    def __repr__(self):
        return (f"<State: {self.status} "
                f"steps={self.step_count} "
                f"success={self.success_count} "
                f"fail={self.fail_count}>")

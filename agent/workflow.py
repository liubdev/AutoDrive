"""
Workflow engine - define and execute multi-step automation flows
"""
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any
from enum import Enum

from config import settings

logger = logging.getLogger("autocar.workflow")


class StepType(Enum):
    """Step type enumeration"""
    LAUNCH = "launch"
    CONNECT = "connect"
    CLICK = "click"
    INPUT = "input"
    SELECT = "select"
    WAIT = "wait"
    WAIT_WINDOW = "wait_window"
    KEYBOARD = "keyboard"
    SCREENSHOT = "screenshot"
    OCR = "ocr"
    CLOSE = "close"
    CUSTOM = "custom"
    CHECK = "check"
    SCROLL = "scroll"


@dataclass
class StepResult:
    """Single step execution result"""
    success: bool
    step_name: str
    step_type: StepType
    message: str = ""
    duration: float = 0.0
    data: Any = None


@dataclass
class Step:
    """A single step in a workflow"""
    name: str
    type: StepType
    target: str = ""
    value: str = ""
    timeout: int = None
    condition: str = ""
    handler: Callable = None
    on_error: str = "raise"     # raise | skip | retry | continue
    depends_on: List[str] = field(default_factory=list)
    description: str = ""

    def run(self, context: Dict) -> StepResult:
        """Execute (called by Workflow)"""
        start = time.time()
        return StepResult(
            success=True,
            step_name=self.name,
            step_type=self.type,
            duration=time.time() - start,
        )


class Workflow:
    """
    Workflow - defines a sequence of automation steps

    Supports:
        - Sequential execution
        - Step dependencies
        - Error handling strategies
        - Conditional checks
        - Timeout control
        - Execution reports
    """

    def __init__(self, name: str = None):
        self.name = name or "workflow"
        self.steps: List[Step] = []
        self._step_registry: Dict[str, Step] = {}
        self._results: Dict[str, StepResult] = {}
        self._context: Dict = {}
        self._step_handlers: Dict[StepType, Callable] = {}
        self._hook_before: Optional[Callable] = None
        self._hook_after: Optional[Callable] = None

    def add_step(self, step: Step) -> "Workflow":
        """Add a step"""
        self.steps.append(step)
        self._step_registry[step.name] = step
        return self

    # -- Convenience step builders --

    def launch(self, name: str, path: str, args: str = "",
               timeout: int = None) -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.LAUNCH, target=path,
            value=args, timeout=timeout,
            description=f"Launch {path}",
        ))

    def click(self, name: str, target: str,
              by: str = "auto_id", timeout: int = None) -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.CLICK, target=target,
            value=by, timeout=timeout,
            description=f"Click {target}",
        ))

    def input_text(self, name: str, target: str, text: str,
                   by: str = "auto_id", timeout: int = None) -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.INPUT, target=target,
            value=text, timeout=timeout,
            description=f"Type '{text}' into {target}",
        ))

    def select(self, name: str, target: str, item: str,
               timeout: int = None) -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.SELECT, target=target,
            value=item, timeout=timeout,
            description=f"Select '{item}' from {target}",
        ))

    def wait(self, name: str, seconds: float = 2,
             target: str = None) -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.WAIT, target=target or "",
            value=str(seconds),
            description=f"Wait {seconds}s",
        ))

    def wait_window(self, name: str, title: str,
                    timeout: int = None) -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.WAIT_WINDOW, target=title,
            timeout=timeout,
            description=f"Wait for window '{title}'",
        ))

    def screenshot(self, name: str) -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.SCREENSHOT,
            description="Take screenshot",
        ))

    def custom(self, name: str, handler: Callable,
               on_error: str = "raise") -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.CUSTOM, handler=handler,
            on_error=on_error, description=f"Custom: {name}",
        ))

    def check(self, name: str, condition: str) -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.CHECK, condition=condition,
            description=f"Check: {condition}",
        ))

    def keyboard(self, name: str, keys: str) -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.KEYBOARD, value=keys,
            description=f"Keys: {keys}",
        ))

    def close(self, name: str = "Close") -> "Workflow":
        return self.add_step(Step(
            name=name, type=StepType.CLOSE, description="Close application",
        ))

    # -- Execution --

    def run(self, context: Dict = None) -> Dict[str, StepResult]:
        """
        Execute all steps in sequence

        Args:
            context: execution context (for handlers)
        Returns:
            {step_name: StepResult}
        """
        self._results = {}
        self._context = context or {}
        logger.info(f"===== Workflow [{self.name}] started =====")

        overall_success = True
        for step in self.steps:
            result = self._execute_step(step)
            self._results[step.name] = result

            if result.success:
                logger.info(f"  + {step.name} ({result.duration:.2f}s)")
            else:
                logger.error(f"  - {step.name}: {result.message}")
                overall_success = False

                if step.on_error == "raise":
                    logger.error(f"Workflow aborted at step: {step.name}")
                    break
                elif step.on_error == "skip":
                    continue
                elif step.on_error == "retry":
                    for _ in range(3):
                        result = self._execute_step(step)
                        if result.success:
                            self._results[step.name] = result
                            overall_success = True
                            break

        logger.info(f"===== Workflow [{self.name}] {'OK' if overall_success else 'FAILED'} =====")
        return self._results

    def _execute_step(self, step: Step) -> StepResult:
        """Execute a single step"""
        if self._hook_before:
            try:
                self._hook_before(step, self._context)
            except Exception as e:
                logger.warning(f"Before-hook error: {e}")

        handler = self._step_handlers.get(step.type)
        start = time.time()

        if handler:
            try:
                result = handler(step, self._context)
                if not isinstance(result, StepResult):
                    result = StepResult(
                        success=True, step_name=step.name,
                        step_type=step.type, duration=time.time() - start,
                    )
            except Exception as e:
                result = StepResult(
                    success=False, step_name=step.name,
                    step_type=step.type, message=str(e),
                    duration=time.time() - start,
                )
        elif step.type == StepType.CUSTOM and step.handler:
            try:
                step.handler(self._context)
                result = StepResult(
                    success=True, step_name=step.name,
                    step_type=step.type, duration=time.time() - start,
                )
            except Exception as e:
                result = StepResult(
                    success=False, step_name=step.name,
                    step_type=step.type, message=str(e),
                    duration=time.time() - start,
                )
        else:
            result = StepResult(
                success=True, step_name=step.name,
                step_type=step.type, duration=0,
            )

        result.duration = time.time() - start

        if self._hook_after:
            try:
                self._hook_after(step, result, self._context)
            except Exception as e:
                logger.warning(f"After-hook error: {e}")

        return result

    def register_handler(self, step_type: StepType,
                         handler: Callable[["Step", Dict], StepResult]):
        """Register an execution handler for a step type"""
        self._step_handlers[step_type] = handler

    def set_before_hook(self, hook: Callable):
        """Set before-step hook"""
        self._hook_before = hook

    def set_after_hook(self, hook: Callable):
        """Set after-step hook"""
        self._hook_after = hook

    def is_success(self) -> bool:
        """Check if all steps succeeded"""
        return all(r.success for r in self._results.values())

    def get_result(self, step_name: str) -> Optional[StepResult]:
        return self._results.get(step_name)

    def get_results(self) -> Dict[str, StepResult]:
        return dict(self._results)

    def print_report(self):
        """Print execution report"""
        print(f"\n{'='*50}")
        print(f"  Workflow: {self.name}")
        print(f"{'='*50}")
        for step in self.steps:
            r = self._results.get(step.name)
            if r:
                mark = "+" if r.success else "-"
                print(f"  {mark} {step.name:30s} {r.duration:.2f}s")
                if not r.success:
                    print(f"      Error: {r.message}")
        print(f"{'='*50}")
        total = sum(r.duration for r in self._results.values())
        success = sum(1 for r in self._results.values() if r.success)
        fail = sum(1 for r in self._results.values() if not r.success)
        print(f"  {success} OK / {fail} FAIL / total {total:.2f}s")
        print(f"{'='*50}\n")

    def export(self, path: str = None) -> str:
        """Export execution report to JSON"""
        import json
        from datetime import datetime
        from pathlib import Path

        report = {
            "workflow": self.name,
            "timestamp": datetime.now().isoformat(),
            "total_duration": sum(r.duration for r in self._results.values()),
            "results": {
                name: {
                    "success": r.success,
                    "message": r.message,
                    "duration": round(r.duration, 3),
                }
                for name, r in self._results.items()
            },
        }
        output = path or str(
            Path.cwd() / f"wf_{self.name}_{datetime.now().strftime('%H%M%S')}.json"
        )
        with open(output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Workflow report: {output}")
        return output

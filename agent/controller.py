"""
Auto controller - orchestrates automation execution

Integrates Driver, Locator, Actions, State, and AI modules.
"""

import time
import logging
from typing import Optional, Dict, Any, List, Callable

from config import settings
from automation.driver import AppDriver
from automation.locator import Locator, Element, By, ElementNotFoundError
from automation.actions import Actions
from .state import AutoState
from .workflow import Workflow, Step, StepType, StepResult

logger = logging.getLogger("autocar.controller")


class AutoController:
    """
    Automation controller - core coordinator

    Usage:
        ctrl = AutoController()
        ctrl.launch("notepad.exe")
        ctrl.click("Open", by="name")
        ctrl.type_text("input", "test.txt")
    """

    def __init__(self):
        self.driver = AppDriver()
        self.state = AutoState()
        self._actions = Actions()
        self._workflow_handlers_registered = False

    # -- Launch / Connect --

    def launch(
        self, path: str, args: str = "", wait_seconds: float = None
    ) -> "AutoController":
        """Launch an application"""
        self.state.mark_running()
        self.state.process_path = path
        self.driver.start(path, args)
        if wait_seconds:
            time.sleep(wait_seconds)
        self._update_state_window()
        self.state.record_step("launch", path)
        return self

    def connect(
        self, path: str = None, pid: int = None, title: str = None
    ) -> "AutoController":
        """Connect to a running process"""
        if path:
            self.driver.connect(path=path)
        elif pid:
            self.driver.connect(pid=pid)
        elif title:
            self.driver.connect(title=title)
        self.state.mark_running()
        self._update_state_window()
        self.state.record_step("connect", title or path or str(pid))
        return self

    def connect_existing(self, path: str) -> "AutoController":
        """Connect to an existing process by executable path"""
        self.driver.connect_existing(path)
        self.state.mark_running()
        self._update_state_window()
        return self

    # -- Locator --

    def locator(self) -> Locator:
        """Get a locator instance"""
        return Locator()

    def find(
        self,
        text: str = None,
        auto_id: str = None,
        name: str = None,
        control_type: str = None,
        title: str = None,
        class_name: str = None,
        timeout: int = None,
    ) -> Optional[Element]:
        """
        Find a control - multi-strategy

        Selects strategy based on which parameter is provided.
        """
        loc = Locator(timeout=timeout)
        if text:
            loc.by_text(text)
        if auto_id:
            loc.by_auto_id(auto_id)
        if name:
            loc.by_name(name)
        if control_type:
            loc.by_type(control_type)
        if title:
            loc.by_title(title)
        if class_name:
            loc.by_class(class_name)
        return loc.find()

    # -- Actions --

    def click(
        self,
        target: str = None,
        by: str = "auto_id",
        element: Element = None,
        timeout: int = None,
    ) -> bool:
        """
        Click a control

        Args:
            target: control descriptor (text/auto_id/name)
            by: locator strategy
            element: pass Element directly (skip lookup)
            timeout: seconds
        """
        if element:
            el = element
        else:
            el = self._locate_ctrl(target, by, timeout)
            if not el:
                return False

        result = self._actions.click(el, timeout)
        self.state.record_step("click", target or str(el), result)
        return result

    def type_text(
        self,
        target: str = None,
        text: str = "",
        by: str = "auto_id",
        element: Element = None,
        clear_first: bool = True,
        timeout: int = None,
    ) -> bool:
        """Type text into an input box"""
        if element:
            el = element
        else:
            el = self._locate_ctrl(target, by, timeout)
            if not el:
                return False

        result = self._actions.type_text(el, text, clear_first, timeout)
        self.state.record_step("type_text", target, result, f"text='{text[:50]}'")
        return result

    def set_text(
        self,
        target: str = None,
        text: str = "",
        by: str = "auto_id",
        element: Element = None,
    ) -> bool:
        """Directly set text"""
        el = element or self._locate_ctrl(target, by)
        if not el:
            return False
        result = self._actions.set_text(el, text)
        self.state.record_step("set_text", target, result)
        return result

    def select(
        self,
        target: str = None,
        item: str = "",
        by: str = "auto_id",
        element: Element = None,
    ) -> bool:
        """Select from combobox/list"""
        el = element or self._locate_ctrl(target, by)
        if not el:
            return False
        result = self._actions.select_item(el, item)
        self.state.record_step("select", target, result)
        return result

    def wait(
        self,
        seconds: float = 1,
        target: str = None,
        by: str = "text",
        timeout: int = None,
    ) -> bool:
        """Wait"""
        if target:
            el = self._locate_ctrl(target, by, timeout)
            if not el:
                return False
            self.state.record_step("wait", target, True)
            return True
        else:
            time.sleep(seconds)
            self.state.record_step("wait", f"{seconds}s", True)
            return True

    def wait_window(self, title: str, timeout: int = None) -> bool:
        """Wait for a window to appear"""
        try:
            self.driver.wait_window(title, timeout)
            self._update_state_window()
            self.state.record_step("wait_window", title, True)
            return True
        except Exception as e:
            logger.error(f"Wait window failed: {e}")
            self.state.record_step("wait_window", title, False, str(e))
            return False

    def send_keys(self, keys: str) -> "AutoController":
        """Send keyboard keys"""
        self._actions.send_keys(keys)
        self.state.record_step("send_keys", keys)
        return self

    def screenshot(self, output: str = None) -> Optional[str]:
        """Take a screenshot"""
        try:
            from vision.screenshot import ScreenCapture

            sc = ScreenCapture()
            path = sc.fullscreen(output)
            self.state.record_step("screenshot", path, True)
            return path
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            self.state.record_step("screenshot", "", False, str(e))
            return None

    def ocr_text(self, image_path: str) -> str:
        """OCR text from an image"""
        try:
            from vision.ocr import OCR

            ocr = OCR()
            text = ocr.text_from_image(image_path)
            self.state.record_step(
                "ocr", image_path, True, f"Recognized {len(text)} chars"
            )
            return text
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""

    def close(self):
        """Close the application"""
        self.driver.close()
        self.state.mark_done()
        self.state.record_step("close", "", True)

    # -- AI-powered execution --

    def execute_goal(self, goal: str, app_path: str = None) -> bool:
        """
        Execute a natural language goal using AI

        Flow:
            1. Launch app (if path provided)
            2. AI analyzes goal + UI state, generates action plan
            3. Execute plan step by step
            4. Attempt recovery on errors

        Args:
            goal: natural language goal
            app_path: optional EXE path
        """
        from ai.client import AIClient
        from ai.prompt import PromptBuilder

        if app_path:
            self.launch(app_path)

        ai = AIClient()
        pb = PromptBuilder()

        # Probe current UI
        try:
            from inspector.explorer import UIExplorer

            explorer = UIExplorer()
            tree = explorer.dump_tree(max_depth=4)
        except Exception as e:
            tree = []
            logger.warning(f"UI probe failed: {e}")

        # Generate plan
        plan_prompt = pb.plan_from_goal(goal, {"controls": tree[:5] if tree else []})

        logger.info("Requesting action plan from AI...")
        plan = ai.chat_json(plan_prompt, system=pb.SYSTEM_PLAN)
        if "error" in plan:
            logger.error(f"AI plan failed: {plan['error']}")
            return False

        steps = plan.get("steps", [])
        if not steps:
            logger.warning("AI generated no steps")
            return False

        logger.info(f"AI plan: {len(steps)} steps")
        success = True

        for i, step in enumerate(steps):
            action = step.get("action", "")
            target = step.get("target", "")
            value = step.get("value", "")
            desc = step.get("description", "")

            logger.info(f"  [{i+1}/{len(steps)}] {desc or action}")

            try:
                if action == "click":
                    result = self.click(target=target, by="text")
                elif action == "input":
                    result = self.type_text(target=target, text=value)
                elif action == "select":
                    result = self.select(target=target, item=value)
                elif action == "wait":
                    result = self.wait(seconds=float(value or 2))
                elif action == "keyboard":
                    self.send_keys(value)
                    result = True
                elif action == "screenshot":
                    self.screenshot()
                    result = True
                elif action == "launch":
                    self.launch(target, value)
                    result = True
                else:
                    logger.warning(f"Unknown action: {action}")
                    result = False

                if not result:
                    # Attempt AI fix
                    fix_prompt = pb.fix_error(goal, f"Step {i+1} failed", str(step))
                    fix = ai.chat_json(fix_prompt)
                    if "fix" in fix:
                        logger.info(f"AI fix: {fix['fix']}")
                        time.sleep(1)
                        if action == "click":
                            result = self.click(target=target, by="text")
                        elif action == "input":
                            result = self.type_text(target=target, text=value)

                if not result:
                    success = False
                    logger.error(f"Step {i+1} failed")

            except Exception as e:
                logger.error(f"Step {i+1} exception: {e}")
                success = False

        self.state.mark_done(success)
        if success:
            logger.info("+ Goal completed")
        else:
            logger.error("- Goal had failures")
        return success

    # -- Workflow --

    def create_workflow(self, name: str = None) -> Workflow:
        """
        Create a controller-bound Workflow with pre-registered step handlers

        The workflow steps can directly control the UI through this controller.
        """
        wf = Workflow(name=name or "autocar_workflow")

        def launch_handler(step: Step, ctx: Dict) -> StepResult:
            self.launch(step.target, step.value, wait_seconds=2)
            return StepResult(True, step.name, step.type, "Launched")

        def click_handler(step: Step, ctx: Dict) -> StepResult:
            ok = self.click(
                step.target, by=step.value or "auto_id", timeout=step.timeout
            )
            return StepResult(ok, step.name, step.type, "OK" if ok else "Failed")

        def input_handler(step: Step, ctx: Dict) -> StepResult:
            ok = self.type_text(step.target, step.value, timeout=step.timeout)
            return StepResult(ok, step.name, step.type, "OK" if ok else "Failed")

        def select_handler(step: Step, ctx: Dict) -> StepResult:
            ok = self.select(step.target, step.value)
            return StepResult(ok, step.name, step.type, "OK" if ok else "Failed")

        def wait_handler(step: Step, ctx: Dict) -> StepResult:
            if step.target:
                ok = self.wait(target=step.target, timeout=step.timeout)
            else:
                self.wait(seconds=float(step.value or 1))
                ok = True
            return StepResult(ok, step.name, step.type, "Wait done")

        def wait_window_handler(step: Step, ctx: Dict) -> StepResult:
            ok = self.wait_window(step.target, step.timeout)
            return StepResult(ok, step.name, step.type, "Found" if ok else "Timeout")

        def keyboard_handler(step: Step, ctx: Dict) -> StepResult:
            self.send_keys(step.value)
            return StepResult(True, step.name, step.type, f"Keys: {step.value}")

        def screenshot_handler(step: Step, ctx: Dict) -> StepResult:
            path = self.screenshot()
            return StepResult(True, step.name, step.type, f"Screenshot: {path}")

        def close_handler(step: Step, ctx: Dict) -> StepResult:
            self.close()
            return StepResult(True, step.name, step.type, "Closed")

        def check_handler(step: Step, ctx: Dict) -> StepResult:
            return StepResult(True, step.name, step.type, "Pass")

        wf.register_handler(StepType.LAUNCH, launch_handler)
        wf.register_handler(StepType.CLICK, click_handler)
        wf.register_handler(StepType.INPUT, input_handler)
        wf.register_handler(StepType.SELECT, select_handler)
        wf.register_handler(StepType.WAIT, wait_handler)
        wf.register_handler(StepType.WAIT_WINDOW, wait_window_handler)
        wf.register_handler(StepType.KEYBOARD, keyboard_handler)
        wf.register_handler(StepType.SCREENSHOT, screenshot_handler)
        wf.register_handler(StepType.CLOSE, close_handler)
        wf.register_handler(StepType.CHECK, check_handler)

        return wf

    # -- Internal --

    def _locate_ctrl(
        self, target: str, by: str, timeout: int = None
    ) -> Optional[Element]:
        """Internal control locator"""
        loc = Locator(timeout=timeout)

        if by == "text":
            loc.by_text(target)
        elif by == "auto_id":
            loc.by_auto_id(target)
        elif by == "name":
            loc.by_name(target)
        elif by == "type":
            loc.by_type(target)
        elif by == "class":
            loc.by_class(target)
        elif by == "title":
            loc.by_title(target)
        else:
            loc.by_text(target)

        el = loc.find()
        if el is None:
            logger.warning(f"Locate failed: by={by} target='{target}'")
        return el

    def _update_state_window(self):
        """Update window info in state"""
        try:
            win = self.driver.top_window
            self.state.update_window(
                title=win.window_text(),
                handle=win.handle,
            )
        except Exception:
            pass

    def report(self) -> Dict:
        """Get execution report"""
        return self.state.summary()

    def export_report(self, path: str = None) -> str:
        """Export report to file"""
        return self.state.export(path)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

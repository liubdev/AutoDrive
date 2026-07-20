"""
User actions - high-level interactions with located elements
"""
import time
import logging
from typing import Optional

import pywinauto.keyboard as kb

from config import settings
from .locator import Element

logger = logging.getLogger("autocar.actions")


class Actions:
    """
    High-level user actions - click, type, select, scroll, etc.

    Handles waiting for control readiness, retry, and logging.
    """

    # -- Click --

    @staticmethod
    def click(target: Element, timeout: int = None) -> bool:
        """Click a control"""
        if not Actions._ensure_ready(target, timeout):
            return False
        try:
            logger.info(f"Click: {target}")
            target.native.click()
            time.sleep(settings.action_delay)
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False

    @staticmethod
    def click_input(target: Element, timeout: int = None) -> bool:
        """Use click_input (lower-level, simulates real click)"""
        if not Actions._ensure_ready(target, timeout):
            return False
        try:
            logger.info(f"click_input: {target}")
            target.native.click_input()
            time.sleep(settings.action_delay)
            return True
        except Exception as e:
            logger.error(f"click_input failed: {e}")
            return False

    @staticmethod
    def double_click(target: Element, timeout: int = None) -> bool:
        """Double-click"""
        if not Actions._ensure_ready(target, timeout):
            return False
        try:
            target.native.double_click()
            time.sleep(settings.action_delay)
            return True
        except Exception as e:
            logger.error(f"Double click failed: {e}")
            return False

    @staticmethod
    def right_click(target: Element, timeout: int = None) -> bool:
        """Right-click"""
        if not Actions._ensure_ready(target, timeout):
            return False
        try:
            target.native.right_click()
            time.sleep(settings.action_delay)
            return True
        except Exception as e:
            logger.error(f"Right click failed: {e}")
            return False

    # -- Text input --

    @staticmethod
    def type_text(target: Element, text: str, clear_first: bool = True,
                  timeout: int = None) -> bool:
        """
        Type text into an input box

        Args:
            target: input control
            text: text to type
            clear_first: whether to clear existing content first
        """
        if not Actions._ensure_ready(target, timeout):
            return False
        try:
            if clear_first:
                logger.debug(f"Clearing input: {target}")
                target.native.select()
                kb.send_keys("{BACKSPACE}")
            target.native.type_keys(text, with_spaces=True)
            time.sleep(settings.action_delay)
            logger.info(f"Typed: '{text}' -> {target}")
            return True
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return False

    @staticmethod
    def set_text(target: Element, text: str) -> bool:
        """Directly set text (no keyboard simulation)"""
        try:
            target.native.set_edit_text(text)
            logger.info(f"Set text: '{text}' -> {target}")
            return True
        except Exception as e:
            logger.error(f"set_text failed: {e}")
            return False

    @staticmethod
    def clear_text(target: Element) -> bool:
        """Clear text"""
        try:
            target.native.select()
            kb.send_keys("{BACKSPACE}")
            time.sleep(settings.action_delay)
            return True
        except Exception:
            try:
                target.native.set_edit_text("")
                return True
            except Exception as e:
                logger.error(f"Clear text failed: {e}")
                return False

    # -- Selection --

    @staticmethod
    def select_item(target: Element, item_text: str) -> bool:
        """
        Select an item from a list/combobox

        Args:
            target: list or combobox control
            item_text: item text to select
        """
        if not Actions._ensure_ready(target):
            return False
        try:
            if target.is_combo:
                target.native.select(item_text)
            else:
                target.native.child_window(title=item_text).click()
            logger.info(f"Selected: '{item_text}' -> {target}")
            return True
        except Exception as e:
            logger.error(f"Selection failed: {e}")
            return False

    @staticmethod
    def select_by_index(target: Element, index: int) -> bool:
        """Select by index"""
        try:
            target.native.select(index)
            return True
        except Exception as e:
            logger.error(f"select_by_index failed: {e}")
            return False

    # -- Toggle --

    @staticmethod
    def toggle(target: Element, state: bool = True) -> bool:
        """Set checkbox/switch state"""
        if not Actions._ensure_ready(target):
            return False
        try:
            current = target.native.get_toggle_state()
            if (state and current != 1) or (not state and current == 1):
                target.native.click()
                time.sleep(settings.action_delay)
                logger.info(f"Toggled -> {state}: {target}")
            return True
        except Exception as e:
            logger.error(f"Toggle failed: {e}")
            return False

    # -- Focus / Scroll --

    @staticmethod
    def focus(target: Element) -> bool:
        """Focus on a control"""
        try:
            target.native.set_focus()
            return True
        except Exception as e:
            logger.error(f"Focus failed: {e}")
            return False

    @staticmethod
    def scroll(target: Element, direction: str = "down", amount: int = 3) -> bool:
        """Scroll (direction: up/down/left/right)"""
        try:
            for _ in range(amount):
                target.native.scroll(direction=direction)
                time.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return False

    # -- Window --

    @staticmethod
    def close_window(target: Element) -> bool:
        """Close a window"""
        try:
            target.native.close()
            return True
        except Exception as e:
            logger.error(f"Close window failed: {e}")
            return False

    @staticmethod
    def maximize(target: Element) -> bool:
        """Maximize window"""
        try:
            target.native.maximize()
            return True
        except Exception as e:
            logger.error(f"Maximize failed: {e}")
            return False

    @staticmethod
    def minimize(target: Element) -> bool:
        """Minimize window"""
        try:
            target.native.minimize()
            return True
        except Exception as e:
            logger.error(f"Minimize failed: {e}")
            return False

    @staticmethod
    def restore(target: Element) -> bool:
        """Restore window"""
        try:
            target.native.restore()
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    # -- Keyboard --

    @staticmethod
    def send_keys(keys: str):
        """Send keyboard keys"""
        kb.send_keys(keys)
        time.sleep(settings.action_delay)

    @staticmethod
    def press(key: str):
        """Press a single key"""
        kb.send_keys(f"{{{key.upper()}}}")
        time.sleep(settings.action_delay)

    @staticmethod
    def hotkey(*keys: str):
        """
        Send hotkey combination

        Examples:
            Actions.hotkey("^a")       # Ctrl+A
            Actions.hotkey("%{F4}")    # Alt+F4
        """
        for k in keys:
            kb.send_keys(k)
        time.sleep(settings.action_delay)

    # -- Drag and drop --

    @staticmethod
    def drag_drop(source: Element, target: Element) -> bool:
        """Drag source to target"""
        try:
            source.native.drag_mouse_input(
                target.native.rectangle.mid_point()
            )
            time.sleep(settings.action_delay)
            return True
        except Exception as e:
            logger.error(f"Drag-drop failed: {e}")
            return False

    # -- Wait helper --

    @staticmethod
    def wait(seconds: float):
        """Explicit wait"""
        time.sleep(seconds)

    # -- Internal --

    @staticmethod
    def _ensure_ready(target: Element, timeout: int = None) -> bool:
        """Ensure the control is visible and enabled"""
        timeout = timeout or settings.default_timeout
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if target.visible and target.enabled:
                    return True
            except Exception:
                pass
            time.sleep(settings.retry_interval)
        logger.warning(f"Control not ready: {target}")
        return False

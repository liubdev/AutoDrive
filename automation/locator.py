"""
Element locator - multi-strategy control search
"""
import time
import logging
import re
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Callable

from pywinauto import Desktop
from pywinauto.controls.uia_controls import EditWrapper, ButtonWrapper, ComboBoxWrapper
from pywinauto.base_wrapper import BaseWrapper

from config import settings

logger = logging.getLogger("autocar.locator")


class By(Enum):
    """Locator strategy"""
    NAME = "name"
    TITLE = "title"
    TEXT = "text"
    CLASS_NAME = "class_name"
    CONTROL_TYPE = "control_type"
    AUTO_ID = "auto_id"

    @staticmethod
    def is_valid(name: str) -> bool:
        return name in {e.value for e in By}


@dataclass
class Element:
    """Located UI element wrapper"""
    native: BaseWrapper
    by: By
    value: str
    found_at: float = 0.0

    # -- Control properties --

    @property
    def name(self) -> str:
        return self.native.element_info.name or ""

    @property
    def control_type(self) -> str:
        return self.native.element_info.control_type or ""

    @property
    def class_name(self) -> str:
        return self.native.class_name() or ""

    @property
    def automation_id(self) -> str:
        return self.native.element_info.automation_id or ""

    @property
    def text(self) -> str:
        """Get the control's text content"""
        try:
            return self.native.window_text()
        except Exception:
            return ""

    @property
    def rect(self):
        """Control rectangle (left, top, right, bottom)"""
        r = self.native.rectangle  # property, not method
        return r.left, r.top, r.right, r.bottom

    @property
    def center(self):
        """Control center coordinates (x, y)"""
        r = self.native.rectangle
        return (r.left + r.right) // 2, (r.top + r.bottom) // 2

    @property
    def visible(self) -> bool:
        return self.native.visible

    @property
    def enabled(self) -> bool:
        return self.native.enabled

    @property
    def is_editable(self) -> bool:
        return isinstance(self.native, EditWrapper) or "Edit" in self.control_type

    @property
    def is_button(self) -> bool:
        return isinstance(self.native, ButtonWrapper) or "Button" in self.control_type

    @property
    def is_combo(self) -> bool:
        return isinstance(self.native, ComboBoxWrapper) or "ComboBox" in self.control_type

    def __repr__(self):
        return f"<Element '{self.name}' type={self.control_type} at={self.center}>"


@dataclass
class Locator:
    """
    Element locator - multi-strategy, retry, cache

    Chainable usage:
        Locator().by_name("OK").with_timeout(5)
        Locator().by_text("Username").with_timeout(3)
    """
    title: Optional[str] = None
    title_re: Optional[str] = None
    class_name: Optional[str] = None
    control_type: Optional[str] = None
    auto_id: Optional[str] = None
    name: Optional[str] = None
    text: Optional[str] = None
    text_re: Optional[str] = None
    predicate: Optional[Callable] = None

    timeout: int = None
    retry_interval: float = None
    parent: Optional[BaseWrapper] = None
    index: int = 0

    _cache: Optional[Element] = None

    def __post_init__(self):
        self.timeout = self.timeout or settings.default_timeout
        self.retry_interval = self.retry_interval or settings.retry_interval

    # -- Chain setters --

    def by_title(self, title: str) -> "Locator":
        self.title = title; return self

    def by_title_re(self, pattern: str) -> "Locator":
        self.title_re = pattern; return self

    def by_class(self, class_name: str) -> "Locator":
        self.class_name = class_name; return self

    def by_type(self, control_type: str) -> "Locator":
        self.control_type = control_type; return self

    def by_auto_id(self, auto_id: str) -> "Locator":
        self.auto_id = auto_id; return self

    def by_name(self, name: str) -> "Locator":
        self.name = name; return self

    def by_text(self, text: str) -> "Locator":
        self.text = text; return self

    def by_text_re(self, pattern: str) -> "Locator":
        self.text_re = pattern; return self

    def by_predicate(self, fn: Callable) -> "Locator":
        self.predicate = fn; return self

    def within(self, parent: BaseWrapper) -> "Locator":
        self.parent = parent; return self

    def with_timeout(self, t: int) -> "Locator":
        self.timeout = t; return self

    def at_index(self, idx: int) -> "Locator":
        self.index = idx; return self

    # -- Search logic --

    def find(self) -> Optional[Element]:
        """
        Execute the search, return Element or None.

        Supports retry until timeout.
        """
        if self._cache and self._cache.visible:
            return self._cache

        start = time.time()
        strategy = self._identify_strategy()
        logger.debug(f"Locating: strategy={strategy}")

        deadline = time.time() + self.timeout
        last_error = None

        while time.time() < deadline:
            try:
                source = self.parent if self.parent else Desktop(backend=settings.uia_backend)

                kwargs = {}
                if self.title: kwargs["title"] = self.title
                if self.title_re: kwargs["title_re"] = self.title_re
                if self.class_name: kwargs["class_name"] = self.class_name
                if self.control_type: kwargs["control_type"] = self.control_type
                if self.auto_id: kwargs["auto_id"] = self.auto_id
                if self.name: kwargs["name"] = self.name

                if self.text:
                    kwargs["found_index"] = self.index if not self.text else 0
                else:
                    kwargs["found_index"] = self.index

                wrapped = source.window(**kwargs)

                if self.text or self.text_re:
                    control = self._find_by_text(source)
                elif self.predicate:
                    control = self._find_by_predicate(source)
                else:
                    if not wrapped.exists():
                        raise LookupError("Control does not exist")
                    wrapped.wait("visible", timeout=0)
                    control = Element(
                        native=wrapped,
                        by=self._identify_strategy(),
                        value=self.title or self.name or self.auto_id or "",
                        found_at=time.time() - start,
                    )

                self._cache = control
                logger.info(f"Found: {control} ({time.time()-start:.2f}s)")
                return control

            except (LookupError, Exception) as e:
                last_error = e
                time.sleep(self.retry_interval)

        logger.warning(f"Timed out ({self.timeout}s): {strategy}")
        return None

    def _find_by_text(self, source) -> Element:
        """Search for a control by text content (recursive)"""
        matches = self._recursive_search(source, check_func=self._text_matches)
        if not matches:
            raise LookupError("No control found with matching text")
        idx = min(self.index, len(matches) - 1)
        return Element(
            native=matches[idx],
            by=By.TEXT,
            value=self.text or self.text_re or "",
        )

    def _find_by_predicate(self, source) -> Element:
        """Search for a control by custom predicate"""
        matches = self._recursive_search(source, check_func=self.predicate)
        if not matches:
            raise LookupError("No control matched predicate")
        idx = min(self.index, len(matches) - 1)
        return Element(
            native=matches[idx],
            by=By.TITLE,
            value="predicate",
        )

    def _text_matches(self, ctrl) -> bool:
        """Check if a control's text matches"""
        try:
            t = ctrl.window_text()
            if self.text and self.text.lower() in t.lower():
                return True
            if self.text_re and re.search(self.text_re, t, re.IGNORECASE):
                return True
        except Exception:
            pass
        return False

    def _recursive_search(self, parent, check_func: Callable, depth: int = 5,
                          results: list = None) -> list:
        """Recursively traverse child controls"""
        if results is None:
            results = []
        if depth <= 0:
            return results
        try:
            children = parent.children()
        except Exception:
            return results
        for child in children:
            try:
                if check_func(child):
                    results.append(child)
            except Exception:
                continue
            self._recursive_search(child, check_func, depth - 1, results)
        return results

    def _identify_strategy(self) -> By:
        """Identify which strategy is being used"""
        if self.auto_id: return By.AUTO_ID
        if self.name: return By.NAME
        if self.title_re or self.title: return By.TITLE
        if self.text or self.text_re: return By.TEXT
        if self.control_type: return By.CONTROL_TYPE
        if self.class_name: return By.CLASS_NAME
        return By.TITLE

    def find_or_raise(self) -> Element:
        """Find or raise ElementNotFoundError"""
        el = self.find()
        if el is None:
            raise ElementNotFoundError(
                f"Element not found: {self._identify_strategy().value} "
                f"(timeout={self.timeout}s)"
            )
        return el

    def exists(self) -> bool:
        """Check if the control exists"""
        return self.find() is not None

    def wait_until_gone(self, timeout: int = None) -> bool:
        """Wait until the control disappears"""
        timeout = timeout or self.timeout
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self.find():
                return True
            time.sleep(self.retry_interval)
        return False

    def clear_cache(self):
        self._cache = None


class ElementNotFoundError(Exception):
    """Raised when a control cannot be found"""
    pass


# -- Convenience factories --

def find_text(text: str, **kwargs) -> Optional[Element]:
    """Find a control by text"""
    return Locator(text=text, **kwargs).find()

def find_by_auto_id(aid: str, **kwargs) -> Optional[Element]:
    """Find a control by AutomationId"""
    return Locator(auto_id=aid, **kwargs).find()

def find_by_type(ctrl_type: str, **kwargs) -> Optional[Element]:
    """Find a control by control type"""
    return Locator(control_type=ctrl_type, **kwargs).find()

"""
UI control tree explorer - traverse windows, export structure, interactive search

Uses UIAElementInfo (low-level API from find_elements) directly for
consistent behavior across pywinauto versions.
"""
import time
import logging
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from pywinauto.findwindows import find_elements

from config import settings

logger = logging.getLogger("autocar.explorer")


def _get_top_windows(backend: str = "uia"):
    """Get all top-level windows (returns list of UIAElementInfo)"""
    return find_elements(backend=backend, top_level_only=True, visible_only=False)


# Mapping from UIAElementInfo attribute names to our display keys
_ELEMENT_FIELDS = [
    ("handle", "handle"),
    ("name", "name"),
    ("control_type", "type"),
    ("class_name", "class"),
    ("automation_id", "auto_id"),
]


class UIExplorer:
    """
    UI control tree explorer

    Use cases:
        - View the complete control tree of a target window
        - Export control structure to JSON for AI analysis
        - Find the locating attributes of a specific control
        - Record user action sequences
    """

    def __init__(self, backend: str = None):
        self.backend = backend or settings.uia_backend

    # -- Window list --

    def list_windows(self) -> List[Dict]:
        """List all visible top-level windows"""
        result = []
        for w in _get_top_windows(self.backend):
            try:
                if not w.visible:
                    continue
                rect = w.rectangle
                result.append({
                    "handle": w.handle,
                    "title": w.name or "",
                    "class": w.class_name or "",
                    "rect": {
                        "left": rect.left, "top": rect.top,
                        "right": rect.right, "bottom": rect.bottom,
                        "width": rect.width(),
                        "height": rect.height(),
                    },
                })
            except Exception:
                continue
        return result

    def get_window_info(self, title: str = None, handle: int = None) -> Optional[Dict]:
        """Get structured info for a single window"""
        for w in _get_top_windows(self.backend):
            try:
                if title and title.lower() in (w.name or "").lower():
                    return self._describe(w)
                if handle is not None and w.handle == handle:
                    return self._describe(w)
            except Exception:
                continue
        return None

    # -- Control tree --

    def dump_tree(self, title: str = None, max_depth: int = 8,
                  handle: int = None) -> List[Dict]:
        """
        Export the hierarchical tree of controls (as JSON-compatible dict)

        Args:
            title: window title keyword to filter
            max_depth: max traversal depth
            handle: exact window handle
        """
        windows = _get_top_windows(self.backend)
        if handle is not None:
            windows = [w for w in windows if w.handle == handle]
        elif title:
            windows = [w for w in windows
                       if title.lower() in (w.name or "").lower()]

        if not windows:
            logger.warning("No matching windows found (title=%s)", title)
            return []

        tree = []
        for w in windows:
            try:
                tree.append(self._build_tree(w, max_depth))
            except Exception as e:
                logger.warning("Failed to traverse window: %s", e)
        return tree

    def _build_tree(self, element, depth: int) -> Dict:
        """Recursively build the control tree"""
        node = self._describe(element)
        if depth <= 1:
            return node

        children = []
        try:
            for child in element.children():
                try:
                    children.append(self._build_tree(child, depth - 1))
                except Exception:
                    continue
        except Exception:
            pass

        if children:
            node["children"] = children
        return node

    def _describe(self, element) -> Dict:
        """Describe a control's basic properties (safe, never throws)"""
        try:
            rect = element.rectangle
            return {
                "handle": element.handle,
                "name": element.name or "",
                "type": element.control_type or "",
                "class": element.class_name or "",
                "auto_id": element.automation_id or "",
                "rect": {
                    "x": rect.left, "y": rect.top,
                    "w": rect.width(),
                    "h": rect.height(),
                },
                "visible": element.visible,
                "enabled": element.enabled,
                "text": (element.name or "")[:100],
            }
        except Exception as e:
            return {"error": str(e)[:60]}

    # -- Export --

    def export_tree(self, title: str = None, output: str = None,
                    max_depth: int = 6) -> str:
        """Export control tree to a JSON file"""
        if output is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = settings.reports_dir / f"ui_tree_{timestamp}.json"

        tree = self.dump_tree(title=title, max_depth=max_depth)
        data = {
            "timestamp": datetime.now().isoformat(),
            "target": title or "all_windows",
            "count": len(tree),
            "tree": tree,
        }
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("Control tree exported: %s", output)
        return str(output)

    # -- Interactive search --

    def find_control(self, title: str = None, auto_id: str = None,
                     control_type: str = None, name: str = None,
                     class_name: str = None) -> List[Dict]:
        """Search for controls matching the given criteria"""
        matches = []
        for w in _get_top_windows(self.backend):
            try:
                if title and title.lower() not in (w.name or "").lower():
                    continue
                matches.extend(self._search(w, auto_id=auto_id,
                               control_type=control_type, name=name,
                               class_name=class_name))
            except Exception:
                continue
        return matches

    def _search(self, parent, **criteria) -> List[Dict]:
        """Recursively search for matching controls"""
        results = []
        try:
            for child in parent.children():
                try:
                    match = True
                    if criteria.get("auto_id") and criteria["auto_id"] not in (child.automation_id or ""):
                        match = False
                    if criteria.get("control_type") and criteria["control_type"] != child.control_type:
                        match = False
                    if criteria.get("name") and criteria["name"].lower() not in (child.name or "").lower():
                        match = False
                    if criteria.get("class_name") and criteria["class_name"] != child.class_name:
                        match = False
                    if match:
                        results.append(self._describe(child))
                    results.extend(self._search(child, **criteria))
                except Exception:
                    continue
        except Exception:
            pass
        return results

    # -- Simple recording --

    def record_actions(self, duration: int = 10) -> List[Dict]:
        """
        Record window state changes over a duration

        Args:
            duration: seconds to record
        Returns:
            list of snapshots
        """
        snapshots = []
        end = time.time() + duration
        seq = 0
        while time.time() < end:
            try:
                windows = _get_top_windows(self.backend)
                if windows:
                    top = windows[0]
                    snapshots.append({
                        "seq": seq,
                        "timestamp": time.time(),
                        "active_title": top.name or "",
                        "active_class": top.class_name or "",
                    })
                seq += 1
            except Exception:
                pass
            time.sleep(1)
        return snapshots

"""
AutoDrive App Modules - 通用 Windows 应用自动化框架

架构设计:
  BaseApp (基类)          ← 通用生命周期 + 窗口匹配 + 控件定位
    └── 任意 EXE

核心设计原则:
  1. 每个应用知道如何找到/启动自己 (find/launch/connect)
  2. 窗口匹配用 PID，不用标题子串（避免连错窗口）
  3. 控件定位有多重降级策略
  4. 应用与框架解耦：可以直接用 pywinauto，也可以通过 AutoController
"""

import time
import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import psutil
from pywinauto import Application
from pywinauto.findwindows import find_elements

from automation import background as bg

logger = logging.getLogger("autocar.apps")


class BaseApp:
    """
    应用基类 - 封装通用的启动/连接/窗口匹配逻辑

    子类只需覆写:
      - APP_EXE       : 可执行文件路径或名称
      - APP_KEYWORDS  : 用于窗口匹配的类名/标题关键字
      - is_single_instance(): 是否单实例
      - wait_ready()  : 等待应用就绪的自定义逻辑

    用法:
      app = ForkApp()
      app.ensure_running()       # 启动或连接
      window = app.window       # 获取顶层窗口
      app.click_by_auto_id(...) # 便捷操作
      app.disconnect()          # 断开，不杀进程
    """

    # --- 子类覆写 ---
    APP_EXE: str = ""  # e.g. "notepad.exe" 或完整路径
    APP_KEYWORDS: dict = {}  # 窗口匹配提示
    INSTANCE_MULTI: bool = True  # True=多实例, False=单实例
    BACKGROUND: bool = False     # True=消息式后台输入（不依赖前台，DTS 可后台运行）

    def __init__(self):
        self._app: Optional[Application] = None
        self._window = None
        self._pid: Optional[int] = None
        self._launched_by_us = False
        # 后台模式开关：子类可覆写 BACKGROUND 或在实例化后覆盖
        self.background = self.BACKGROUND

    # ── 公共属性 ──────────────────────────────────────────

    @property
    def window(self):
        """获取顶层窗口对象（pywinauto WindowSpecification）"""
        if self._window is None and self._app is not None:
            self._window = self._app.top_window()
        return self._window

    @property
    def pid(self) -> Optional[int]:
        return self._pid

    @property
    def is_connected(self) -> bool:
        return self._app is not None

    # ── 生命周期 ──────────────────────────────────────────

    def ensure_running(self, timeout: int = 20) -> bool:
        """
        确保应用正在运行并可交互

        流程:
          1. 按进程名查找已有实例
          2. 若未找到，启动新进程
          3. 等待窗口出现并按 PID 匹配
          4. 连接并等待就绪

        Returns:
            True 表示成功连接到应用窗口
        """
        # 1. 查找已有实例并尝试连接
        pid = self._find_process()
        if pid:
            logger.info(f"发现已有实例 PID={pid}")
            if self._connect_by_pid(pid):
                return True
            # 进程存在但连不上（无窗口），继续走启动流程
            logger.warning(f"PID={pid} 存在但无窗口，将启动新实例")

        # 2. 启动新进程
        if not self.APP_EXE:
            raise RuntimeError(f"{self.__class__.__name__}.APP_EXE 未设置")

        logger.info(f"启动: {self.APP_EXE}")
        proc = subprocess.Popen([self.APP_EXE])

        # 3. 等待窗口（处理多种场景）
        #    - 正常: 启动进程的 PID 就是窗口的 PID
        #    - 单实例: 启动的进程发现已有实例，退出，窗口在另一个进程
        #    - Win11 模式: 启动进程 A，窗口由进程 B 创建（如 Notepad）
        deadline = time.time() + timeout
        launched_pid = proc.pid

        while time.time() < deadline:
            launched_exited = proc.poll() is not None

            # 策略 A: 按我们启动的 PID 找窗口
            if not launched_exited:
                win = self._find_window_by_pid(launched_pid)
                if win:
                    self._launched_by_us = True
                    return self._connect_by_handle(win.handle, launched_pid)

            # 策略 B: 进程已退出 → 单实例应用，找同名进程的窗口
            if launched_exited:
                existing_pid = self._find_process()
                if existing_pid:
                    return self._connect_by_pid(existing_pid)

            # 策略 C: 按 exe 名找窗口（处理窗口 PID ≠ 启动 PID 的情况）
            wins = self._find_windows_by_exe()
            if wins:
                # 过滤掉旧的（如果已有连接则不重复连）
                win = max(wins, key=lambda w: w.handle)
                self._launched_by_us = True
                return self._connect_by_handle(win.handle, win.process_id)

            time.sleep(0.5)

        # 超时后的最终尝试
        logger.warning(f"超时 {timeout}s，最终尝试...")
        wins = self._find_windows_by_exe()
        if wins:
            win = max(wins, key=lambda w: w.handle)
            return self._connect_by_handle(win.handle, win.process_id)

        logger.error(f"无法连接到 {self.APP_EXE}")
        return False

    def connect_existing(self) -> bool:
        pid = self._find_process()
        if pid:
            return self._connect_by_pid(pid)
        logger.warning(f"未找到 {self.APP_EXE} 的运行实例")
        return False

    def disconnect(self):
        self._app = None
        self._window = None
        self._pid = None
        self._launched_by_us = False
        logger.info("已断开连接")

    def close(self):
        if self._launched_by_us and self._app:
            try:
                self._app.kill()
                logger.info("进程已关闭")
            except Exception as e:
                logger.warning(f"关闭失败: {e}")
        self.disconnect()

    # ── 窗口匹配（子类可覆写） ──────────────────────────

    def _find_process(self) -> Optional[int]:
        """
        按进程名查找正在运行的应用 PID
        """
        exe_name = Path(self.APP_EXE).stem.lower()
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                if not proc.is_running():
                    continue
                name = (proc.info["name"] or "").lower()
                exe = (proc.info["exe"] or "").lower()
                if name == f"{exe_name}.exe" or exe_name in exe:
                    return proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None

    def _find_window_by_pid(self, pid: int):
        """按 PID 找顶层窗口"""
        wins = find_elements(backend="uia", top_level_only=True)
        for w in wins:
            try:
                if w.process_id == pid:
                    return w
            except Exception:
                continue
        return None

    def _find_windows_by_exe(self, exe_name: str = None):
        """
        按进程可执行文件名找所有窗口 (比按 PID 更鲁棒)

        解决场景: Win11 的 Notepad 由进程 A 启动，但窗口由进程 B 创建
        (启动进程 PID != 窗口进程 PID)

        Args:
            exe_name: exe 名，默认用 APP_EXE
        Returns:
            匹配的窗口列表，按 handle 升序
        """
        exe_name = (exe_name or Path(self.APP_EXE).stem).lower()

        # 构建 PID → exe_name 映射
        pid_exe = {}
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pid_exe[proc.info["pid"]] = (proc.info["name"] or "").lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # 找所有窗口，检查其进程名
        wins = find_elements(backend="uia", top_level_only=True)
        matched = []
        for w in wins:
            try:
                proc_name = pid_exe.get(w.process_id, "")
                if exe_name in proc_name:
                    matched.append(w)
            except Exception:
                continue
        return matched

    def _find_window_by_class(self, class_keyword: str):
        """按类名关键字找窗口（降级方案）"""
        wins = find_elements(backend="uia", top_level_only=True)
        for w in wins:
            try:
                if w.class_name and class_keyword.lower() in w.class_name.lower():
                    return w
            except Exception:
                continue
        return None

    # ── 连接逻辑 ──────────────────────────────────────────

    def _connect_by_pid(self, pid: int) -> bool:
        """通过 PID 连接"""
        win = self._find_window_by_pid(pid)
        if win:
            return self._connect_by_handle(win.handle, pid)
        # 降级：等一会儿窗口出现
        logger.info(f"PID={pid} 窗口未出现，等待...")
        deadline = time.time() + 10
        while time.time() < deadline:
            win = self._find_window_by_pid(pid)
            if win:
                return self._connect_by_handle(win.handle, pid)
            time.sleep(0.5)
        # 再降级：按 exe 名找窗口（处理窗口 PID ≠ 启动 PID 的情况）
        logger.info(f"按 exe 名查找窗口...")
        wins = self._find_windows_by_exe()
        if wins:
            # 多实例：优先选 handle 最大的（最新创建的窗口）
            win = max(wins, key=lambda w: w.handle)
            return self._connect_by_handle(win.handle, win.process_id)
        return False

    def _connect_by_handle(self, handle: int, pid: int = None) -> bool:
        """通过窗口句柄连接"""
        try:
            self._app = Application(backend="uia").connect(handle=handle)
            self._window = self._app.top_window()
            self._pid = pid or self._app.process
            logger.info(f"已连接: '{self._window.window_text()}' (handle={handle})")
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False

    # ── 图片/文字定位（处理自绘控件、图片按钮） ──────────

    def click_image(
        self, template_name: str, threshold: float = 0.8, timeout: int = 10
    ) -> bool:
        """
        通过模板匹配点击图片按钮

        Args:
            template_name: data/templates/ 下的图片文件名
            threshold: 匹配阈值 0~1
            timeout: 超时秒数

        用法:
            # 先截图按钮保存到 data/templates/dts_confirm.png
            app.click_image("dts_confirm.png")
        """
        from vision.locate import ImageLocator

        locator = ImageLocator()

        deadline = time.time() + timeout
        while time.time() < deadline:
            handle = self._window.handle if self._window else None
            result = locator.find_image(
                template_name, window_handle=handle, threshold=threshold
            )
            if result:
                return locator.click(result)
            time.sleep(0.5)

        logger.warning(f"图片 '{template_name}' 在 {timeout}s 内未出现")
        return False

    def click_text(self, text: str, timeout: int = 10) -> bool:
        """
        通过 OCR 识别文字并点击

        Args:
            text: 要识别的文字（支持中文）
            timeout: 超时秒数

        用法:
            app.click_text("确认")       # 找到"确认"文字位置并点击
            app.click_text("提交申请")
        """
        from vision.locate import ImageLocator

        locator = ImageLocator()

        deadline = time.time() + timeout
        while time.time() < deadline:
            handle = self._window.handle if self._window else None
            result = locator.find_text(text, window_handle=handle)
            if result:
                return locator.click(result)
            time.sleep(0.5)

        logger.warning(f"文字 '{text}' 在 {timeout}s 内未找到")
        return False

    def double_click_text(self, text: str, timeout: int = 10) -> bool:
        """通过 OCR 找到文字并双击"""
        from vision.locate import ImageLocator

        locator = ImageLocator()
        deadline = time.time() + timeout
        while time.time() < deadline:
            handle = self._window.handle if self._window else None
            result = locator.find_text(text, window_handle=handle)
            if result:
                return locator.double_click(result)
            time.sleep(0.5)
        return False

    def double_click_image(
        self, template_name: str, threshold: float = 0.8, timeout: int = 10
    ) -> bool:
        """通过模板匹配找到图片并双击"""
        from vision.locate import ImageLocator

        locator = ImageLocator()
        deadline = time.time() + timeout
        while time.time() < deadline:
            handle = self._window.handle if self._window else None
            result = locator.find_image(
                template_name, window_handle=handle, threshold=threshold
            )
            if result:
                return locator.double_click(result)
            time.sleep(0.5)
        return False

    # ── 键盘操作 ──────────────────────────────────────

    def _hwnd(self) -> int:
        """当前连接窗口的顶层句柄（后台消息输入的目标窗口）"""
        try:
            return int(self.window.handle)
        except Exception:
            return 0

    def _send_key_sequence(self, keys: str):
        """按模式投递按键：后台=消息式定向窗口；前台=物理输入（0.6.3 SendKeys）"""
        if self.background:
            hwnd = self._hwnd()
            if hwnd:
                bg.send_keys(hwnd, keys)
                return
            logger.warning("后台按键但未连接窗口，跳过: %s", keys)
            return
        from pywinauto.keyboard import SendKeys

        SendKeys(keys)

    def send_enter(self, times: int = 1):
        """
        发送 Enter 键

        有的页面进入后按 Enter 即可触发下一步。

        Args:
            times: 按几次，默认 1 次

        用法:
            app.send_enter()       # 按一次 Enter
            app.send_enter(3)      # 连按 3 次
        """
        for _ in range(times):
            self._send_key_sequence("{ENTER}")
            time.sleep(0.1)
        logger.info(f"  Enter x{times}")
        return self

    def send_space(self, times: int = 1):
        """
        发送 Space 键

        有的页面进入后按 Space 即可触发下一步。

        Args:
            times: 按几次，默认 1 次

        用法:
            app.send_space()       # 按一次 Space
            app.send_space(3)      # 连按 3 次
        """
        for _ in range(times):
            self._send_key_sequence("{SPACE}")
            time.sleep(0.1)
        logger.info(f"  Space x{times}")
        return self

    def send_keys(self, keys: str):
        """
        发送任意键盘按键（pywinauto 语法）

        Args:
            keys: 例如 "^a" (Ctrl+A), "%{F4}" (Alt+F4), "{TAB 3}", 文件名文本

        用法:
            app.send_keys("^a")       # Ctrl+A 全选
            app.send_keys("{TAB 2}")  # Tab 两次
            app.send_keys("%{F4}")    # Alt+F4 关闭
        """
        self._send_key_sequence(keys)
        logger.info(f"  Keys: {keys}")
        return self

    def click_ctrl(self, ctrl) -> bool:
        """点击控件：后台=UIA Invoke（消息式，最小化/屏幕外均有效）；前台=物理点击"""
        if self.background:
            return bg.click_ctrl(ctrl, self._hwnd())
        try:
            ctrl.click_input()
            return True
        except Exception:
            return False

    def click_at(self, x: int, y: int) -> bool:
        """按屏幕坐标点击：后台=SendMessage 消息式；前台=物理鼠标"""
        if self.background:
            return bg.click_at(self._hwnd(), x, y)
        try:
            from pywinauto import mouse

            mouse.click(coords=(x, y))
            return True
        except Exception:
            return False

    def set_focus_bg(self, ctrl) -> bool:
        """聚焦控件：后台=AttachThreadInput+SetFocus（不抢前台）；前台=UIA set_focus"""
        if self.background:
            try:
                return bg.set_focus(int(ctrl.handle))
            except Exception:
                return False
        try:
            ctrl.set_focus()
            return True
        except Exception:
            return False

    def wait_for_control(self, auto_id: str, control_type: str = "Button",
                         timeout: int = 30) -> bool:
        """
        等待指定控件出现（用于确认页面切换完成）

        替代写死的 time.sleep，页面出现目标控件后立即继续。

        Args:
            auto_id: 控件 AutomationId
            control_type: 控件类型，默认 Button
            timeout: 超时秒数

        用法:
            app.wait_for_control("1013")       # 等待"上翻页"按钮出现
            app.wait_for_control("1202", "Edit")  # 等待版本信息文本出现
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                ctrl = self.window.child_window(auto_id=auto_id,
                                                control_type=control_type,
                                                found_index=0)
                if ctrl.exists(timeout=0.5):
                    logger.info(f"✓ 控件 {auto_id} 已出现")
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        logger.warning(f"控件 {auto_id} 在 {timeout}s 内未出现")
        return False

    def wait_for_image(self, template_name: str, timeout: int = 30) -> bool:
        """等待图片出现（用于确认页面切换完成）"""
        from vision.locate import ImageLocator

        locator = ImageLocator()

        deadline = time.time() + timeout
        while time.time() < deadline:
            handle = self._window.handle if self._window else None
            result = locator.find_image(
                template_name, window_handle=handle, threshold=0.7
            )
            if result:
                logger.info(f"✓ 图片 '{template_name}' 已出现")
                return True
            time.sleep(0.5)

        logger.warning(f"图片 '{template_name}' 在 {timeout}s 内未出现")
        return False

    # ── 分辨率自适应（硬编码坐标 + 多屏适配） ───────────

    # def click_at 已移除 —— 像素坐标跨分辨率不可靠，改用锚点比例

    def menu_select(self, path: str):
        """
        选择菜单项 (格式: "Menu->Submenu->Command")

        例如:  app.menu_select("Repository->Pull")
        """
        if not self.window:
            return
        items = [item.strip() for item in path.split("->")]
        current = self.window
        for item in items:
            current = current.child_window(title=item, control_type="MenuItem")
            current.click()
            time.sleep(0.3)

    def screenshot(self, path: str = None) -> Optional[str]:
        """截图"""
        try:
            from vision.screenshot import ScreenCapture

            return ScreenCapture().fullscreen(path)
        except Exception as e:
            logger.warning(f"截图失败: {e}")
            return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._launched_by_us:
            self.close()
        else:
            self.disconnect()

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

    def __init__(self):
        self._app: Optional[Application] = None
        self._window = None
        self._pid: Optional[int] = None
        self._launched_by_us = False

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

    # ── 控件定位便捷方法 ──────────────────────────────────

    def click_by_auto_id(self, auto_id: str, timeout: int = 5) -> bool:
        """按 auto_id 点击控件"""
        if not self.window:
            return False
        try:
            ctrl = self.window.child_window(auto_id=auto_id, control_type="Button")
            if ctrl.exists(timeout=timeout):
                ctrl.click()
                return True
        except Exception as e:
            logger.warning(f"click_by_auto_id({auto_id}) 失败: {e}")
        return False

    def click_by_text(self, text: str, timeout: int = 5) -> bool:
        """按文字内容点击控件"""
        if not self.window:
            return False
        # 策略1: MenuItem
        for ct in ("MenuItem", "Button", "Text", "Hyperlink"):
            try:
                ctrl = self.window.child_window(title=text, control_type=ct)
                if ctrl.exists(timeout=1):
                    ctrl.click()
                    return True
            except Exception:
                continue
        # 策略2: 遍历
        try:
            ctrl = self.window.child_window(title=text)
            if ctrl.exists(timeout=timeout):
                ctrl.click()
                return True
        except Exception:
            pass
        return False

    def find_element(self, **criteria):
        """通用元素查找"""
        if not self.window:
            return None
        try:
            ctrl = self.window.child_window(**criteria)
            return ctrl if ctrl.exists(timeout=5) else None
        except Exception:
            return None

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

    def double_click_at(
        self, x: int, y: int, ref_resolution: Tuple[int, int] = None
    ) -> bool:
        """按坐标双击（自动适配分辨率）"""
        from vision.locate import ResolutionAdapter

        adapter = ResolutionAdapter(reference=ref_resolution or (1920, 1080))
        sx, sy = adapter.scale(x, y)
        try:
            from pywinauto import mouse

            mouse.double_click(coords=(sx, sy))
            logger.info(f"  双击 ({sx}, {sy}) [原始 ({x},{y})]")
            time.sleep(settings.action_delay)
            return True
        except Exception as e:
            logger.error(f"双击失败: {e}")
            return False

    # ── 键盘操作 ──────────────────────────────────────

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
        from pywinauto.keyboard import send_keys

        for _ in range(times):
            send_keys("{ENTER}")
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
        from pywinauto.keyboard import send_keys

        for _ in range(times):
            send_keys("{SPACE}")
            time.sleep(0.1)
        logger.info(f"  Space x{times}")
        return self

    def send_keys(self, keys: str):
        """
        发送任意键盘按键

        Args:
            keys: pywinauto 键盘语法
                 例如: "^a" (Ctrl+A), "%{F4}" (Alt+F4), "{TAB 3}"

        用法:
            app.send_keys("^a")       # Ctrl+A 全选
            app.send_keys("{TAB 2}")  # Tab 两次
            app.send_keys("%{F4}")    # Alt+F4 关闭
        """
        from pywinauto.keyboard import send_keys

        send_keys(keys)
        logger.info(f"  Keys: {keys}")
        return self

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

    def click_at(
        self,
        x: int,
        y: int,
        ref_resolution: Tuple[int, int] = None,
        button: str = "left",
    ) -> bool:
        """
        按坐标点击（自动适配当前分辨率）

        Args:
            x, y: 参考分辨率下的坐标
            ref_resolution: 参考分辨率，默认 (1920, 1080)
            button: left/right

        用法:
            # 在 1920x1080 上截图测得按钮在 (855, 956)
            # 在 2560x1440 上自动缩放
            app.click_at(855, 956)
        """
        from vision.locate import ResolutionAdapter

        adapter = ResolutionAdapter(reference=ref_resolution or (1920, 1080))
        sx, sy = adapter.scale(x, y)

        try:
            from pywinauto import mouse

            mouse.click(button=button, coords=(sx, sy))
            logger.info(f"  坐标点击 ({sx}, {sy}) [原始 ({x},{y})]")
            time.sleep(settings.action_delay)
            return True
        except Exception as e:
            logger.error(f"坐标点击失败: {e}")
            return False

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

"""
AutoDrive 流程引擎

把「线性脚本」升级为「可配置流程」：
  - 每个步骤 = 动作(action) + 验证(verify) + 重试(retry)
  - 后台线程执行，UI 通过事件回调刷新进度
  - 支持取消、logging 自动转发到 UI

事件列表（通过 engine.on(event, cb) 订阅）:
  flow_start    ->  (engine)
  step_start    ->  (step)
  step_done     ->  (step)
  step_error    ->  (step)
  flow_done     ->  (engine)     自然完成
  flow_cancelled->  (engine)     被取消
  log           ->  (msg, level) 所有 Python logging 记录转发

线程说明:
  engine.run() 是阻塞方法，调用方负责放入后台线程（如 threading.Thread）。
  事件回调默认在「执行线程」里触发，UI 里需要再转发到主线程（如 root.after）。
"""

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

# ── 步骤状态 ──
PENDING = "pending"
RUNNING = "running"
DONE = "done"
ERROR = "error"
CANCELLED = "cancelled"

# 软验证（continue_on_missing）的最长等待：控件确认未出现时不必等满 timeout，
# 给"慢出现但确实存在"的控件留出机会，同时截断版本漂移控件的空等。
_SOFT_VERIFY_PROBE = 8


class FlowStep:
    """一个可执行步骤"""

    def __init__(
        self,
        name: str,
        action: Optional[Callable[[], bool]] = None,
        verify: Optional[dict] = None,
        retry: int = 1,
        timeout: int = 30,
        continue_on_missing: bool = False,
    ):
        """
        Args:
            name: 步骤名称（显示在 UI）
            action: 执行动作，返回 True=成功；None 表示该步只做验证
            verify: 验证条件 {"auto_id": ..., "control_type": ..., "timeout": ...}
            retry: 尝试次数（含首次），失败后自动重试
            timeout: 本步骤验证控件的超时秒数
            continue_on_missing: True=验证控件未出现时跳过该验证、继续下一步
                                 （软件版本间控件 ID 可能不同）；False=未出现则失败
        """
        self.name = name
        self.action = action
        self.verify = verify
        self.retry = retry
        self.timeout = timeout
        self.continue_on_missing = continue_on_missing

        # 运行时状态
        self.status = PENDING
        self.attempt = 0
        self.error: Optional[str] = None


class _EngineLogHandler(logging.Handler):
    """把 Python logging 记录转发为引擎的 log 事件"""

    def __init__(self, engine: "FlowEngine"):
        super().__init__()
        self._engine = engine

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self._engine._emit("log", msg, record.levelname.lower())
        except Exception:
            pass


class FlowEngine:
    """顺序执行步骤的流程引擎"""

    def __init__(self, steps: Optional[List[FlowStep]] = None):
        self.steps = steps or []
        self._cancel_event = threading.Event()
        self._callbacks: Dict[str, List[Callable]] = {}
        self.current: Optional[FlowStep] = None
        self.done: bool = False
        self._log_handler: Optional[_EngineLogHandler] = None

    # ── 事件订阅 ──────────────────────────────────

    def on(self, event: str, callback: Callable) -> "FlowEngine":
        """订阅事件。事件名见模块顶部说明。"""
        self._callbacks.setdefault(event, []).append(callback)
        return self

    def _emit(self, event: str, *args):
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args)
            except Exception:
                # 回调异常不能中断流程
                continue

    # ── 日志 ──────────────────────────────────────

    def log(self, msg: str, level: str = "info"):
        """引擎日志（同时进入 Python logging 与 UI）"""
        lv = getattr(logging, level.upper(), logging.INFO)
        logging.getLogger("autodrive.flow").log(lv, msg)

    # ── 取消 ──────────────────────────────────────

    def cancel(self):
        """请求取消：当前步骤结束后停止"""
        self._cancel_event.set()
        self.log("用户请求取消...", "warning")

    @property
    def cancelled(self) -> bool:
        return self._cancel_event.is_set()

    # ── 执行 ──────────────────────────────────────

    def run(self, verify_app=None):
        """
        同步执行所有步骤（阻塞）。调用方应放入后台线程。

        Args:
            verify_app: 提供 wait_for_control(auto_id, control_type, timeout)
                        的对象（如 DtsApp），用于步骤验证。
        """
        self.done = False
        self._cancel_event.clear()
        self._install_log_handler()

        # 重置所有步骤状态（支持重复运行）
        for step in self.steps:
            step.status = PENDING
            step.error = None
            step.attempt = 0

        self._emit("flow_start", self)

        try:
            for step in self.steps:
                if self.cancelled:
                    step.status = CANCELLED
                    break

                self.current = step
                step.status = RUNNING
                self._emit("step_start", step)

                ok = self._run_step(step, verify_app)
                if not ok:
                    step.status = ERROR
                    self._emit("step_error", step)
                    break  # 失败即停止（后续可扩展为继续模式）
        finally:
            self.done = True
            if self.cancelled:
                self._emit("flow_cancelled", self)
            else:
                self._emit("flow_done", self)
            self._remove_log_handler()

    def _run_step(self, step: FlowStep, verify_app) -> bool:
        """执行单个步骤（含验证与重试），返回是否成功"""
        for attempt in range(step.retry):
            step.attempt = attempt + 1
            try:
                # 1. 执行动作
                if step.action is not None:
                    result = step.action()
                    if not result:
                        raise RuntimeError("动作执行失败")

                # 2. 验证控件出现
                if step.verify and verify_app is not None:
                    v = step.verify
                    timeout = v.get("timeout", step.timeout)
                    if step.continue_on_missing:
                        # 软验证：只探测有限时间，未出现即跳过
                        timeout = min(timeout, _SOFT_VERIFY_PROBE)
                    ok = verify_app.wait_for_control(
                        v["auto_id"],
                        v.get("control_type", "Button"),
                        timeout=timeout,
                    )
                    if not ok:
                        if step.continue_on_missing:
                            # 该控件在当前软件版本中不存在 → 跳过验证，继续下一步
                            self.log(
                                f"  验证控件 {v['auto_id']} 未出现，跳过该验证，继续下一步",
                                "warning",
                            )
                            step.status = DONE
                            step.error = None
                            self._emit("step_done", step)
                            return True
                        raise RuntimeError(f"验证控件 {v['auto_id']} 未出现")

                step.status = DONE
                step.error = None
                self._emit("step_done", step)
                return True

            except Exception as e:
                step.error = str(e)
                self.log(f"  步骤失败(第{attempt+1}/{step.retry}次): {e}", "warning")
                if attempt < step.retry - 1:
                    time.sleep(1)

        step.status = ERROR
        return False

    # ── 便捷：后台线程执行 ────────────────────────

    def run_in_thread(self, verify_app=None) -> threading.Thread:
        """在新线程中执行 run()，立即返回线程对象"""
        t = threading.Thread(
            target=self.run, kwargs={"verify_app": verify_app}, daemon=True
        )
        t.start()
        return t

    # ── logging 转发 ──────────────────────────────

    def _install_log_handler(self):
        handler = _EngineLogHandler(self)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(handler)
        self._log_handler = handler

    def _remove_log_handler(self):
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler = None

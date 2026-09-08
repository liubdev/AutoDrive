"""诊断启动前清理配置的可执行文件，失败时禁止继续启动。"""
import logging
import ntpath
from pathlib import Path

import psutil

log = logging.getLogger(__name__)


def stop_executable(executable: str, timeout: float = 10):
    if not executable or not Path(executable).is_file():
        raise RuntimeError(f"诊断程序不存在: {executable}")
    target = ntpath.normcase(ntpath.normpath(str(Path(executable).resolve())))
    name = ntpath.basename(target)
    matches = []
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").casefold() != name.casefold():
                continue
            # 同名但安装目录不同的程序不结束；无权限核对路径则中止。
            actual = ntpath.normcase(ntpath.normpath(proc.exe()))
            if actual == target:
                matches.append(proc)
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise RuntimeError("无法核对 DTS 进程路径，请以相同权限运行客户端") from exc
    for proc in matches:
        try:
            log.info("结束旧 DTS 进程 PID=%s", proc.pid)
            proc.kill()
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied as exc:
            raise RuntimeError(f"无法结束 DTS 进程 PID={proc.pid}，停止启动") from exc
    _, alive = psutil.wait_procs(matches, timeout=timeout)
    if alive:
        raise RuntimeError(f"DTS 进程未退出，停止启动: {[p.pid for p in alive]}")
    log.info("DTS 旧进程清理完成，共 %d 个", len(matches))

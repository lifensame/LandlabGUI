"""
后台线程：在 QThread 中执行模拟引擎或用户代码片段，
通过信号把日志/进度/高程快照发回主线程（Qt 跨线程安全）。
"""

from __future__ import annotations

import io
import threading
import traceback

import numpy as np
from PySide6.QtCore import QThread, Signal


class StopFlag:
    """线程安全的停止标记（引擎每步检查一次）。"""

    def __init__(self):
        self.stop = False


class SimWorker(QThread):
    sig_log = Signal(str)
    sig_progress = Signal(int, int)
    sig_snapshot = Signal(object)      # np.ndarray 高程副本
    sig_done = Signal(bool, str)       # (是否成功, 消息)

    def __init__(self, engine, workflow, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.workflow = workflow
        self.flag = StopFlag()

    def run(self):
        ok, msg = True, "完成"
        try:
            self.engine.run(self.workflow)
        except Exception as e:
            ok = False
            msg = f"{type(e).__name__}: {e}"
            self.sig_log.emit("后台运行异常:\n" + traceback.format_exc())
        self.sig_done.emit(ok, msg)

    def stop(self):
        self.flag.stop = True


class CodeWorker(QThread):
    """执行代码编辑器中的 Python 片段，共享 workspace 上下文。"""
    sig_log = Signal(str)
    sig_done = Signal(bool, str)
    sig_snapshot = Signal(object)

    def __init__(self, code: str, workspace, plugins: dict, parent=None):
        super().__init__(parent)
        self.code = code
        self.ws = workspace
        self.plugins = plugins
        self.flag = StopFlag()

    def run(self):
        buf = _SignalWriter(self.sig_log)
        ok, msg = True, "代码执行完成"
        g = {"workspace": self.ws, "ws": self.ws,
             "grid": self.ws.grid,
             "np": np, "plugins": self.plugins, "print": buf.print}
        old_stdout = None
        try:
            import contextlib
            import sys
            with contextlib.redirect_stdout(buf):
                exec(compile(self.code, "<GUI代码片段>", "exec"), g)
        except Exception as e:
            ok = False
            msg = f"{type(e).__name__}: {e}"
            buf.write(traceback.format_exc())
        if self.ws.has_grid and "topographic__elevation" in self.ws.at_node:
            self.sig_snapshot.emit(np.array(self.ws.at_node["topographic__elevation"], copy=True))
        self.sig_done.emit(ok, msg)


class _SignalWriter(io.TextIOBase):
    """把 print 输出转发到 Qt 信号。"""

    def __init__(self, signal):
        self.sig = signal
        self._buf = ""

    def write(self, s):
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self.sig.emit(line)
        return len(s)

    def flush(self):
        pass

    def print(self, *args, **kwargs):
        self.write(" ".join(str(a) for a in args) + "\n")


class FuncWorker(QThread):
    """通用后台任务：在线程里执行 fn(*args, **kwargs)，日志/完成走信号。"""

    sig_log = Signal(str)
    sig_done = Signal(bool, str)      # (成功?, 消息/结果repr)
    sig_result = Signal(object)       # fn 的返回值（成功时）

    def __init__(self, fn, *args, parent=None, **kwargs):
        super().__init__(parent)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        buf = _SignalWriter(self.sig_log)
        try:
            import contextlib
            with contextlib.redirect_stdout(buf):
                result = self.fn(*self.args, **self.kwargs)
            self.sig_result.emit(result)
            self.sig_done.emit(True, "完成")
        except Exception as e:
            buf.write(traceback.format_exc())
            self.sig_done.emit(False, f"{type(e).__name__}: {e}")


class SweepWorker(QThread):
    """参数扫描批量实验。"""
    sig_log = Signal(str)
    sig_progress = Signal(int, int)
    sig_done = Signal(bool, str)
    sig_result = Signal(object)       # list[dict] 每个参数值的结果

    def __init__(self, base_wf, step_id, param_name, values, plugins, parent=None):
        super().__init__(parent)
        from ..core.sweep import run_sweep
        self._runner = run_sweep
        self.base_wf, self.step_id = base_wf, step_id
        self.param_name, self.values, self.plugins = param_name, values, plugins
        self.flag = StopFlag()

    def stop(self):
        self.flag.stop = True

    def run(self):
        import contextlib
        buf = _SignalWriter(self.sig_log)
        try:
            results = self._runner(
                self.base_wf, self.step_id, self.param_name, self.values,
                self.plugins, log=buf.print,
                progress=lambda i, n: self.sig_progress.emit(i, n),
                stop=lambda: self.flag.stop)
            self.sig_result.emit(results)
            self.sig_done.emit(True, f"扫描完成，共 {len(results)} 组")
        except Exception as e:
            buf.write(traceback.format_exc())
            self.sig_done.emit(False, f"{type(e).__name__}: {e}")


class AnimWorker(QThread):
    """导出演化动画（GIF/MP4）。"""
    sig_log = Signal(str)
    sig_done = Signal(bool, str)

    def __init__(self, frames, path, fps=10, parent=None):
        super().__init__(parent)
        self.frames, self.path, self.fps = frames, path, fps

    def run(self):
        try:
            from ..core.animate import write_animation
            write_animation(self.frames, self.path, self.fps)
            self.sig_done.emit(True, f"动画已保存: {self.path}")
        except Exception as e:
            self.sig_log.emit(traceback.format_exc())
            self.sig_done.emit(False, f"{type(e).__name__}: {e}")

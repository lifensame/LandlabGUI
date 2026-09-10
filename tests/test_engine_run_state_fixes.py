# -*- coding: utf-8 -*-
"""
回归测试：执行引擎"运行状态"与实验报告修复。
运行: QT_QPA_PLATFORM=offscreen python tests/test_engine_run_state_fixes.py

覆盖 6 个已修复 bug：
1. once_at_end 步骤拿不到 dt（TypeError 或静默不推进）
2. ws.history 跨多次运行累积（演化历史时间轴回跳）
3. 报告步数取自 history[-1][0]（比真实步数少，最多差 history_every-1）
4. 报告无条件拼接"（含中断）"
5. 用户中断后不导出（长任务的中间结果全部丢失）
6. 边界状态用魔数 1 而非 landlab 常量
另附：工作流名称与 history_every 的保存/载入往返。
"""
import copy
import json
import os
import shutil
import sys
import tempfile

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from app.core.engine import Engine          # noqa: E402
from app.core.plugin_loader import load_plugins  # noqa: E402
from app.core.report import generate_report  # noqa: E402
from app.core.workspace import Workspace     # noqa: E402


class StopAfter:
    """前 n 次调用返回 False，之后返回 True（引擎每步调一次）。"""

    def __init__(self, n: int):
        self.n = n
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls > self.n


def _base_wf(n_steps: int = 4, history_every: int = 2, steps: list = None) -> dict:
    return {
        "version": 1,
        "name": "回归测试",
        "grid": {"type": "RasterModelGrid",
                 "params": {"shape": [15, 20], "xy_spacing": 100.0}},
        "boundary": "south_open",
        "terrain": {"mode": "noise", "amplitude": 10.0, "slope": 0.01,
                    "slope_dir": "S", "seed": 42},
        "time": {"dt": 250.0, "n_steps": n_steps,
                 "refresh_every": 2, "history_every": history_every},
        "steps": steps or [],
    }


def _run(wf: dict, ws: Workspace = None, stop=None) -> Workspace:
    plugins = load_plugins(log=lambda s: None)
    ws = ws if ws is not None else Workspace()
    ws.log_fn = lambda s: None
    Engine(ws, plugins, log=lambda s: None, snapshot=lambda: None,
           stop_flag=stop).run(copy.deepcopy(wf))
    return ws


# --------------------------------------------------------------------------
def test_1_once_at_end_step_receives_dt():
    """结束时机的求解类组件必须收到 dt，且推进量随 dt 线性缩放。

    注：断言不能看全域起伏——边界节点在扩散中被固定，全域 max-min 不会变，
    必须比较内点相对"无步骤对照"的变化量。
    """
    step = {"id": "d1", "kind": "component", "component": "LinearDiffuser",
            "params": {"linear_diffusivity": 0.5},
            "when": "once_at_end", "step_style": "run_one_step"}

    ctrl = _run(_base_wf(n_steps=1, steps=[]))
    core = ctrl.grid.core_nodes
    z0 = np.array(ctrl.at_node["topographic__elevation"][core], copy=True)

    def dz(dt: float) -> float:
        wf = _base_wf(n_steps=1, steps=[step])
        wf["time"]["dt"] = dt
        ws = _run(wf)
        return float(np.abs(ws.at_node["topographic__elevation"][core] - z0).max())

    # 修复前：dt 未传入 -> TypeError: run_one_step() missing 1 required positional argument
    d250 = dz(250.0)
    assert d250 > 1e-6, "once_at_end 的 LinearDiffuser 完全没推进（dt 未传入）"

    d125 = dz(125.0)
    assert abs(d250 / d125 - 2.0) < 1e-9, (
        f"内点变化量未随 dt 线性缩放，说明 dt 未被真正使用: {d250} vs {d125}")


def test_2_history_not_accumulated_across_runs():
    """history 属于单次运行：第二次运行不应保留第一次的采样点。"""
    ws = _run(_base_wf(n_steps=10, history_every=2))
    first = [h[0] for h in ws.history]
    assert first == [1, 2, 4, 6, 8, 10], f"首次运行历史异常: {first}"

    _run(_base_wf(n_steps=6, history_every=2), ws=ws)
    second = [h[0] for h in ws.history]
    assert second == [1, 2, 4, 6], f"历史跨运行累积了: {second}"


def test_3_report_uses_real_step_count():
    """报告步数必须是真实完成步数，而不是最后一个历史采样点。"""
    wf = _base_wf(n_steps=6, history_every=5)
    ws = _run(wf)
    assert [h[0] for h in ws.history] == [1, 5], "history_every=5 应只采样 1、5 步"

    out = tempfile.mkdtemp()
    try:
        md = generate_report(ws, wf, out, log=lambda s: None)
        txt = open(md, encoding="utf-8").read()
        # 修复前：写成 history[-1][0]=5，且无条件附上"（含中断）"
        assert "实际运行 6 步" in txt, f"报告步数错误（应为 6）:\n{txt}"
        assert "中断" not in txt, "完整跑完的运行不应标记中断"
    finally:
        shutil.rmtree(out, ignore_errors=True)
    assert ws.steps_done == 6


def test_4_report_marks_user_interrupt():
    """真正被中断时，报告才标注中断，且步数为实际完成步数。"""
    wf = _base_wf(n_steps=50, history_every=5)
    ws = _run(wf, stop=StopAfter(3))

    out = tempfile.mkdtemp()
    try:
        md = generate_report(ws, wf, out, log=lambda s: None)
        txt = open(md, encoding="utf-8").read()
        # 修复前：写 history[-1][0]=1（只采样了第 1 步）
        assert "实际运行 3 步" in txt, f"中断运行的步数错误（应为 3）:\n{txt}"
        assert "用户中断" in txt, f"真正被中断的运行应标注中断:\n{txt}"
    finally:
        shutil.rmtree(out, ignore_errors=True)
    assert ws.interrupted is True
    assert ws.steps_done == 3


def test_5_export_survives_interrupt():
    """用户中断后仍应导出已达成的中间结果。"""
    out = tempfile.mkdtemp()
    wf = _base_wf(n_steps=50)
    wf["outputs"] = {"dir": out, "formats": ["ascii"], "river_min_area": 1e5}
    try:
        ws = _run(wf, stop=StopAfter(2))
        assert os.path.exists(os.path.join(out, "dem.asc")), "中断后未导出 DEM"
    finally:
        shutil.rmtree(out, ignore_errors=True)
    assert ws.interrupted is True


def test_6_boundary_uses_named_constant():
    """南缘开放出水口用 landlab 常量而非魔数。"""
    ws = _run(_base_wf(n_steps=1))
    g = ws.grid
    bottom = np.where(g.node_y == g.node_y.min())[0]
    assert np.all(g.status_at_node[bottom] == g.BC_NODE_IS_FIXED_VALUE)
    assert int(g.BC_NODE_IS_FIXED_VALUE) == 1, "常量值应与旧魔数一致，避免行为漂移"


# --------------------------------------------------------------------------
def _gui():
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QSettings
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QSettings("LandlabGUI", "main").setValue("wizard_seen", True)
    from app.gui.style import apply
    apply(app)
    return app


def test_7_workflow_name_and_history_every_roundtrip():
    """工作流名称与 history_every 必须能存进 JSON 并原样载回。"""
    _gui()
    from app.gui.main_window import MainWindow
    win = MainWindow()
    try:
        win.preset_list.setCurrentRow(0)
        win._load_preset(win.preset_list.item(0))
        p = win.workflow_panel
        assert p.name_edit.text().strip(), "载入预设后面板名称不应为空"

        p.name_edit.setText("我的场景")
        p.history_every.setValue(7)
        wf = p.to_workflow()
        assert wf["name"] == "我的场景", f"名称丢失: {wf['name']}"
        assert wf["time"]["history_every"] == 7, "history_every 应可独立配置"

        p.load_workflow(json.loads(json.dumps(wf)))
        assert p.name_edit.text() == "我的场景", "载入后名称未恢复"
        assert p.history_every.value() == 7, "载入后 history_every 未恢复"
    finally:
        win.close()


def test_8_legacy_workflow_history_every_fallback():
    """旧工作流没有 history_every：沿用 refresh_every//2，行为不变。"""
    _gui()
    from app.gui.main_window import MainWindow
    win = MainWindow()
    try:
        p = win.workflow_panel
        p.load_workflow({"version": 1, "name": "旧流程",
                         "time": {"dt": 250.0, "n_steps": 100, "refresh_every": 20},
                         "steps": []})
        assert p.history_every.value() == 10, "旧工作流应回退到 refresh_every//2"
        assert p.name_edit.text() == "旧流程"
    finally:
        win.close()


if __name__ == "__main__":
    tests = [test_1_once_at_end_step_receives_dt,
             test_2_history_not_accumulated_across_runs,
             test_3_report_uses_real_step_count,
             test_4_report_marks_user_interrupt,
             test_5_export_survives_interrupt,
             test_6_boundary_uses_named_constant,
             test_7_workflow_name_and_history_every_roundtrip,
             test_8_legacy_workflow_history_every_fallback]
    for fn in tests:
        fn()
        print("PASS", fn.__name__, flush=True)
    print("\n运行状态修复: 全部通过", flush=True)

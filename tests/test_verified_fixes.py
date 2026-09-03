# -*- coding: utf-8 -*-
"""
排查验证：6 个已修复 bug 的最小复现 + 回归断言。
运行: QT_QPA_PLATFORM=offscreen python tests/test_verified_fixes.py
覆盖: 缓存版本戳 / 参数去重 / int留空语义 / 缺组件预校验 /
      工作流网格配置保存与沿用 / 完整点击运行冒烟
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
from PySide6.QtCore import QSettings, QEventLoop, QTimer  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
msgs = []
QMessageBox.critical = staticmethod(lambda *a, **k: (msgs.append(a), QMessageBox.StandardButton.Ok)[1])
QMessageBox.warning = staticmethod(lambda *a, **k: (msgs.append(a), QMessageBox.StandardButton.Ok)[1])
QSettings("LandlabGUI", "main").setValue("wizard_seen", True)

from app.gui.style import apply  # noqa: E402
apply(app)


def test_1_cache_version_stamp():
    from app.core import introspection as I
    s = I.scan_all_components()          # 旧格式/篡改 → 自动重建
    cache = json.load(open(os.path.join(os.path.dirname(I.__file__),
                                        "components_cache.json"), encoding="utf-8"))
    assert "_meta" in cache and "components" in cache
    cache["_meta"]["landlab_version"] = "0.0-old"
    cache["components"]["X_stale"] = {"name": "X_stale"}
    path = os.path.join(os.path.dirname(I.__file__), "components_cache.json")
    json.dump(cache, open(path, "w", encoding="utf-8"), ensure_ascii=False)
    s = I.scan_all_components()
    assert "X_stale" not in s, "过期缓存应被拒绝"


def test_2_no_duplicate_params():
    from app.core import introspection as I
    s = I.scan_all_components()
    for comp in ("FlowAccumulator", "LossyFlowAccumulator"):
        names = [p["name"] for p in s[comp]["params"]]
        assert len(names) == len(set(names)), f"{comp} 参数重复: {names}"


def test_3_int_empty_skipped():
    from app.gui.form_builder import ParamForm
    f = ParamForm([{"name": "n", "type": "int", "default": 3}])
    f.set_values({"n": None})
    assert f.values() == {}
    f.set_values({"n": 7})
    assert f.values() == {"n": 7}


def _fresh_window():
    from app.gui.main_window import MainWindow
    return MainWindow()


def test_4_missing_component_blocked_before_grid():
    global msgs
    msgs.clear()
    win = _fresh_window()
    win.preset_list.setCurrentRow(0)
    win._load_preset(win.preset_list.item(0))
    win.workflow_panel.steps.append({"id": "bad", "kind": "component",
                                     "component": "DeletedComponent",
                                     "params": {}, "when": "every_step"})
    win.run_workflow()
    assert win.worker is None and any("DeletedComponent" in str(a) for a in msgs)
    win.close()


def test_5_workflow_grid_config_roundtrip():
    win = _fresh_window()
    win.preset_list.setCurrentRow(0)
    win._load_preset(win.preset_list.item(0))
    win.workflow_panel.grid_cfg = {"type": "RasterModelGrid",
                                   "params": {"shape": [20, 30], "xy_spacing": 100.0}}
    win.workflow_panel.rebuild_check.setChecked(False)
    wf = win.workflow_panel.to_workflow("rt")
    assert wf.get("grid") and wf.get("grid_rebuild") is False
    win.workflow_panel.load_workflow(json.loads(json.dumps(wf)))
    assert win.workflow_panel.rebuild_check.isChecked() is False

    from app.core.engine import Engine
    from app.core.plugin_loader import load_plugins
    from app.core.workspace import Workspace
    plugins = load_plugins(log=lambda s: None)
    ws = Workspace()
    ws.log_fn = lambda s: None
    try:
        Engine(ws, plugins, log=lambda s: None, snapshot=lambda: None).run(
            json.loads(json.dumps(wf)))
        raise AssertionError("无网格时应报错")
    except RuntimeError as e:
        assert "沿用当前网格" in str(e)
    Engine(ws, plugins, log=lambda s: None, snapshot=lambda: None)._build_grid(wf["grid"])
    n0 = ws.grid.number_of_nodes
    Engine(ws, plugins, log=lambda s: None, snapshot=lambda: None).run(
        json.loads(json.dumps(wf)))
    assert ws.grid.number_of_nodes == n0
    win.close()


def test_6_click_run_end_to_end():
    win = _fresh_window()
    win.preset_list.setCurrentRow(0)
    win._load_preset(win.preset_list.item(0))
    win.workflow_panel.n_steps.setValue(20)
    win.workflow_panel.refresh_every.setValue(5)
    win.workflow_panel.do_export.setChecked(False)
    win.workflow_panel.btn_run_big.click()
    app.processEvents()
    assert win.worker is not None and win.worker.isRunning()
    loop = QEventLoop()
    QTimer.singleShot(120000, loop.quit)
    worker = win.worker
    worker.sig_done.connect(lambda ok, msg: loop.quit())
    loop.exec()
    app.processEvents()
    assert len(win.history_panel.snapshots) == 1
    win.close()


if __name__ == "__main__":
    import numpy as np  # noqa: F401  (engine 运行依赖)
    for fn in [test_1_cache_version_stamp, test_2_no_duplicate_params,
               test_3_int_empty_skipped, test_4_missing_component_blocked_before_grid,
               test_5_workflow_grid_config_roundtrip, test_6_click_run_end_to_end]:
        fn()
        print("PASS", fn.__name__)
    print("排查验证: 全部通过")

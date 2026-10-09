# -*- coding: utf-8 -*-
"""课堂实验：进度不能靠连点跳过，记录里要有预设、步数、高程和答案。

运行: QT_QPA_PLATFORM=offscreen python tests/test_classroom_lab.py
"""
import inspect
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from app.core.classroom import (PRESET_NAME, PROCESS_STEPS, STEP_IDS, TAB_SLOPE_AREA,
                                TAB_TERRAIN, current_step, gate, order_ok, quiz_correct,
                                render_lab_note, views_ok, workflow_steps)


def _snap(**kwargs):
    base = {
        "acknowledged_goal": False,
        "workflow_name": "",
        "steps": [],
        "steps_done": 0,
        "interrupted": False,
        "completed_name": "",
        "tab_sequence": [],
        "quiz_index": None,
        "student_name": "",
        "note_written": False,
        "exported_name": "",
    }
    base.update(kwargs)
    return base


def test_1_wrong_order_does_not_advance():
    assert order_ok(list(PROCESS_STEPS))
    assert order_ok(list(PROCESS_STEPS) + [("component", "ChiFinder")])
    assert not order_ok(list(reversed(PROCESS_STEPS)))

    snap = _snap(
        acknowledged_goal=True,
        workflow_name=PRESET_NAME,
        steps=list(reversed(PROCESS_STEPS)),
    )
    assert current_step(snap) == 2
    ok, code = gate("order", snap)
    assert not ok and code == "order"
    # 顺序没对之前，跑完也不算进入看图
    snap["steps_done"] = 40
    assert current_step(snap) == 2


def test_2_run_must_finish_before_views():
    snap = _snap(
        acknowledged_goal=True,
        workflow_name=PRESET_NAME,
        steps=list(PROCESS_STEPS),
        steps_done=0,
    )
    assert current_step(snap) == 3
    ok, code = gate("run", snap)
    assert not ok and code == "run_none"

    snap["steps_done"] = 10
    snap["interrupted"] = True
    snap["completed_name"] = PRESET_NAME
    ok, code = gate("run", snap)
    assert not ok and code == "run_interrupted"
    assert current_step(snap) == 3

    snap["interrupted"] = False
    snap["completed_name"] = "快速测试"
    ok, code = gate("run", snap)
    assert not ok and code == "run_other"
    assert current_step(snap) == 3

    snap["completed_name"] = PRESET_NAME
    assert current_step(snap) == 4
    assert not views_ok([TAB_SLOPE_AREA, TAB_TERRAIN])
    assert views_ok([TAB_TERRAIN, TAB_SLOPE_AREA])
    snap["tab_sequence"] = [TAB_SLOPE_AREA, TAB_TERRAIN]
    assert current_step(snap) == 4
    snap["tab_sequence"] = [TAB_TERRAIN, TAB_SLOPE_AREA]
    assert current_step(snap) == 5


def test_3_lab_note_contains_results():
    text = render_lab_note(
        student="林夏",
        preset=PRESET_NAME,
        steps_done=40,
        mean_z=12.0,
        max_z=30.0,
        answer="汇水面积越大，河道坡度总体越缓",
        correct=True,
    )
    assert "林夏" in text
    assert PRESET_NAME in text
    assert "40" in text
    assert "12.0" in text
    assert "30.0" in text
    assert "汇水面积越大，河道坡度总体越缓" in text
    assert "回答正确" in text
    assert quiz_correct(0)
    assert not quiz_correct(1)

    changed = _snap(
        acknowledged_goal=True,
        workflow_name=PRESET_NAME,
        steps=list(PROCESS_STEPS),
        steps_done=40,
        completed_name=PRESET_NAME,
        tab_sequence=[TAB_TERRAIN, TAB_SLOPE_AREA],
        quiz_index=0,
        student_name="林夏",
        note_written=True,
        exported_name="陈旧姓名",
    )
    assert current_step(changed) == len(STEP_IDS) - 1
    ok, code = gate("note", changed)
    assert not ok and code == "note"


def test_4_preset_file_is_the_classroom_workflow():
    path = os.path.join(APP_DIR, "presets", "课堂实验-河流下切.json")
    with open(path, encoding="utf-8") as handle:
        wf = json.load(handle)
    assert wf["name"] == PRESET_NAME
    assert "outputs" not in wf
    assert workflow_steps(wf["steps"]) == list(PROCESS_STEPS)
    assert wf["time"]["n_steps"] <= 80


def test_5_offscreen_lab_walkthrough():
    import time

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    settings = QSettings("LandlabGUI", "main")
    settings.setValue("wizard_seen", False)
    settings.setValue("classroom_seen", False)
    settings.setValue("lang", "zh")

    warnings = []

    def _warn(*args, **kwargs):
        warnings.append(args)
        return QMessageBox.StandardButton.Ok

    QMessageBox.warning = staticmethod(_warn)
    QMessageBox.critical = staticmethod(_warn)

    win = MainWindow()
    try:
        win.show()
        app.processEvents()
        assert win.lab_panel is not None, "第一次启动应打开课堂实验"
        panel = win.lab_panel
        from PySide6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()
        assert win.lab_dock is not None and not win.lab_dock.isFloating()
        app.processEvents()
        goal = panel.goal_box.mapToGlobal(panel.goal_box.rect().center())
        assert screen.contains(goal), (goal, screen, win.geometry(), win.lab_dock.geometry())
        assert current_step(panel.snapshot()) == 0

        panel.refresh()
        assert current_step(panel.snapshot()) == 0

        panel.goal_box.setChecked(True)
        app.processEvents()
        assert current_step(panel.snapshot()) == 1

        assert win.load_preset_by_name(PRESET_NAME)
        assert win.workflow_panel.name_edit.text() == PRESET_NAME
        assert current_step(panel.snapshot()) == 3

        saved = [dict(step) for step in win.workflow_panel.steps]
        win.workflow_panel.steps = list(reversed(win.workflow_panel.steps))
        panel.refresh()
        assert current_step(panel.snapshot()) == 2

        win.workflow_panel.steps = saved
        panel.refresh()
        assert current_step(panel.snapshot()) == 3
        app.processEvents()
        assert panel.btn_run.isVisible() and panel.btn_run.isEnabled()
        run_at = panel.btn_run.mapToGlobal(panel.btn_run.rect().center())
        assert screen.contains(run_at), (run_at, screen, win.lab_dock.geometry())

        panel.note_tab(TAB_SLOPE_AREA)
        assert panel.tab_sequence == []

        win.ws.steps_done = 40
        win.ws.interrupted = False
        win.ws.completed_name = "快速测试"
        panel.refresh()
        assert current_step(panel.snapshot()) == 3

        panel._start_run()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            app.processEvents()
            finished = (
                win.ws.completed_name == PRESET_NAME
                and (win.worker is None or not win.worker.isRunning())
            )
            if finished:
                break
            time.sleep(0.02)
        else:
            raise AssertionError(
                "课堂预设没有跑完: "
                f"completed={win.ws.completed_name!r} steps={win.ws.steps_done} "
                f"interrupted={win.ws.interrupted}"
            )
        app.processEvents()
        assert win.ws.steps_done == 40
        assert current_step(panel.snapshot()) == 4
        assert panel.tab_sequence[0] == TAB_TERRAIN
        log_text = win.console.text.toPlainText()
        assert log_text.count("=== 开始运行工作流") == 1, log_text
        bar = win.canvas.tabBar()
        slope_at = bar.mapToGlobal(bar.tabRect(TAB_SLOPE_AREA).center())
        assert screen.contains(slope_at), (slope_at, screen, win.geometry())

        win.canvas.setCurrentIndex(TAB_SLOPE_AREA)
        app.processEvents()
        assert current_step(panel.snapshot()) == 5

        panel._quiz_buttons[0].setChecked(True)
        app.processEvents()
        assert current_step(panel.snapshot()) == 6
        assert panel.name_edit.isVisible()
        assert panel.name_edit.parent() is panel.name_row_wrap

        panel.export_note(os.path.join(tempfile.gettempdir(), "should-not-write.md"))
        assert current_step(panel.snapshot()) == 6

        panel.name_edit.setText("林夏")
        out = os.path.join(tempfile.mkdtemp(), "课堂实验记录.md")
        text = panel.export_note(out)
        assert os.path.exists(out)
        assert PRESET_NAME in text
        assert "40" in text
        assert "5.0" in text
        assert "38.9" in text
        assert "汇水面积越大，河道坡度总体越缓" in text
        assert current_step(panel.snapshot()) == len(STEP_IDS)
        assert settings.value("classroom_seen", False, bool)

        src_dir = inspect.getsource(MainWindow.open_plugin_dir)
        src_doc = inspect.getsource(MainWindow._open_plugin_doc)
        src_run = inspect.getsource(MainWindow.run_workflow)
        assert "startfile" not in src_dir
        assert "startfile" not in src_doc
        assert src_run.find("self.worker.start()") < src_run.find("setPriority")
        win.open_plugin_dir()

        warnings.clear()
        assert win.load_preset_by_name("没有这堂课") is False
        assert warnings, "找不到预设时应提示，而不是静默返回"
    finally:
        win.close()
        settings.setValue("wizard_seen", True)
        settings.setValue("classroom_seen", True)


def test_6_classroom_preset_cuts_a_declining_channel():
    """学生看到的坡度-面积必须向右下，而且只有这次跑完的课堂预设才算完成。"""
    import copy

    import numpy as np

    from app.core.engine import Engine
    from app.core.plugin_loader import load_plugins
    from app.core.plots import slope_area_binned
    from app.core.workspace import Workspace

    path = os.path.join(APP_DIR, "presets", "课堂实验-河流下切.json")
    with open(path, encoding="utf-8") as handle:
        wf = json.load(handle)

    ws = Workspace()
    ws.completed_name = "快速测试"
    ws.steps_done = 9
    plugins = load_plugins(log=lambda _s: None)
    Engine(ws, plugins, log=lambda _s: None, snapshot=lambda: None).run(copy.deepcopy(wf))

    assert ws.completed_name == PRESET_NAME
    assert ws.steps_done == wf["time"]["n_steps"]
    assert not ws.interrupted
    z = np.asarray(ws.at_node["topographic__elevation"], dtype=float)
    mean_z = float(np.nanmean(z))
    max_z = float(np.nanmax(z))
    assert 2.0 < mean_z < 12.0, mean_z
    assert 25.0 < max_z < 50.0, max_z

    slope = np.asarray(ws.grid.calc_slope_at_node(), dtype=float)
    area = np.asarray(ws.at_node["drainage_area"], dtype=float)
    mask = (area > 2e4) & np.isfinite(slope) & (slope > 0)
    assert int(mask.sum()) > 30
    corr = float(np.corrcoef(np.log10(area[mask]), np.log10(slope[mask]))[0, 1])
    binned = slope_area_binned(ws, a_min=2e4)
    bin_slope = None
    if binned is not None:
        a_med, s_med = binned
        bin_slope = float(np.polyfit(np.log10(a_med), np.log10(s_med), 1)[0])
    print(
        f"课堂预设: mean={mean_z:.2f} max={max_z:.2f} "
        f"corr={corr:.3f} bin={bin_slope} n={int(mask.sum())}",
        flush=True,
    )
    assert corr < -0.2, corr
    assert bin_slope is not None and bin_slope < -0.1, bin_slope

    class _StopNow:
        def __call__(self):
            return True

    stopped = Workspace()
    stopped.completed_name = PRESET_NAME
    stopped.steps_done = 40
    Engine(stopped, plugins, log=lambda _s: None, snapshot=lambda: None,
           stop_flag=_StopNow()).run(copy.deepcopy(wf))
    assert stopped.interrupted
    assert stopped.completed_name is None


if __name__ == "__main__":
    tests = [
        test_1_wrong_order_does_not_advance,
        test_2_run_must_finish_before_views,
        test_3_lab_note_contains_results,
        test_4_preset_file_is_the_classroom_workflow,
        test_5_offscreen_lab_walkthrough,
        test_6_classroom_preset_cuts_a_declining_channel,
    ]
    for fn in tests:
        fn()
        print("PASS", fn.__name__, flush=True)
    print("\n课堂实验测试全部通过", flush=True)

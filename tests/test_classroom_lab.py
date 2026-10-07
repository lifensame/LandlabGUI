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
    ok, code = gate("run", snap)
    assert not ok and code == "run_interrupted"
    assert current_step(snap) == 3

    snap["interrupted"] = False
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
    import numpy as np
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

        panel.note_tab(TAB_SLOPE_AREA)
        assert panel.tab_sequence == []

        win.ws.steps_done = 40
        win.ws.interrupted = False

        class _Grid:
            at_node = {"topographic__elevation": np.array([10.0, 12.0, 30.0])}

        win.ws.set_grid(_Grid(), {"type": "classroom-test", "params": {}})
        panel.refresh()
        assert current_step(panel.snapshot()) == 4
        assert panel.tab_sequence[0] == TAB_TERRAIN

        win.canvas.setCurrentIndex(TAB_SLOPE_AREA)
        app.processEvents()
        assert current_step(panel.snapshot()) == 5

        panel._quiz_buttons[0].setChecked(True)
        app.processEvents()
        assert current_step(panel.snapshot()) == 6

        panel.export_note(os.path.join(tempfile.gettempdir(), "should-not-write.md"))
        assert current_step(panel.snapshot()) == 6

        panel.name_edit.setText("林夏")
        out = os.path.join(tempfile.mkdtemp(), "课堂实验记录.md")
        text = panel.export_note(out)
        assert os.path.exists(out)
        assert PRESET_NAME in text
        assert "40" in text
        assert "17.3" in text
        assert "30.0" in text
        assert "汇水面积越大，河道坡度总体越缓" in text
        assert current_step(panel.snapshot()) == len(STEP_IDS)
        assert settings.value("classroom_seen", False, bool)

        src_dir = inspect.getsource(MainWindow.open_plugin_dir)
        src_doc = inspect.getsource(MainWindow._open_plugin_doc)
        assert "startfile" not in src_dir
        assert "startfile" not in src_doc
        win.open_plugin_dir()

        warnings.clear()
        assert win.load_preset_by_name("没有这堂课") is False
        assert warnings, "找不到预设时应提示，而不是静默返回"
    finally:
        win.close()
        settings.setValue("wizard_seen", True)
        settings.setValue("classroom_seen", True)


if __name__ == "__main__":
    tests = [
        test_1_wrong_order_does_not_advance,
        test_2_run_must_finish_before_views,
        test_3_lab_note_contains_results,
        test_4_preset_file_is_the_classroom_workflow,
        test_5_offscreen_lab_walkthrough,
    ]
    for fn in tests:
        fn()
        print("PASS", fn.__name__, flush=True)
    print("\n课堂实验测试全部通过", flush=True)

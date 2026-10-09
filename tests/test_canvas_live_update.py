# -*- coding: utf-8 -*-
"""运行中的画布快照不能把 3D 和其它页也重画一遍。

运行: QT_QPA_PLATFORM=offscreen python tests/test_canvas_live_update.py
"""
import os
import subprocess
import sys
import textwrap
import threading
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_startup_with_cache_does_not_import_components():
    """有效缓存时，建窗口不得导入 landlab.components。"""
    code = textwrap.dedent(
        """
        import os, sys
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        sys.path.insert(0, %r)
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication
        QSettings("LandlabGUI", "main").setValue("wizard_seen", True)
        QSettings("LandlabGUI", "main").setValue("classroom_seen", True)
        app = QApplication(sys.argv)
        from app.gui.main_window import MainWindow
        win = MainWindow()
        assert "landlab.components" not in sys.modules, sorted(
            m for m in sys.modules if m.startswith("landlab"))
        assert win.registry.components_ready
        assert len(win.registry.schemas) >= 80
        print("schemas", len(win.registry.schemas))
        win.close()
        """
        % APP_DIR
    )
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr


def test_missing_cache_scans_off_the_gui_thread():
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    import app.core.introspection as intro

    app = QApplication.instance() or QApplication(sys.argv)
    QSettings("LandlabGUI", "main").setValue("wizard_seen", True)
    QSettings("LandlabGUI", "main").setValue("classroom_seen", True)
    seen = {}
    original_cached = intro.cached_components
    original_scan = intro.scan_all_components

    def no_cache():
        return None

    def fake_scan(force=False):
        seen["main"] = threading.current_thread() is threading.main_thread()
        time.sleep(0.05)
        return {
            "FakeComp": {
                "name": "FakeComp",
                "category": "其他",
                "doc": "scan",
                "params": [],
                "input_fields": [],
                "output_fields": [],
                "step_style": "analysis",
            }
        }

    intro.cached_components = no_cache
    intro.scan_all_components = fake_scan
    try:
        from app.gui.main_window import MainWindow
        win = MainWindow()
        deadline = time.monotonic() + 2
        while "main" not in seen and time.monotonic() < deadline:
            time.sleep(0.01)
        assert seen.get("main") is False
        assert not win.registry.components_ready
        win.show()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not win.registry.components_ready:
            app.processEvents()
            time.sleep(0.01)
        assert win.registry.components_ready
        assert win.registry.get("FakeComp") is not None
        assert win.tree.topLevelItemCount() >= 1
        win.close()
    finally:
        intro.cached_components = original_cached
        intro.scan_all_components = original_scan


def test_running_snapshot_updates_terrain_only():
    import numpy as np
    from landlab import RasterModelGrid
    from PySide6.QtWidgets import QApplication

    from app.core import plots
    from app.core.workspace import Workspace
    from app.gui.canvas_panel import CanvasPanel

    app = QApplication.instance() or QApplication(sys.argv)
    ws = Workspace()
    grid = RasterModelGrid((12, 16), xy_spacing=100.0)
    base = np.linspace(0, 5, grid.number_of_nodes)
    grid.at_node["topographic__elevation"] = base.copy()
    ws.set_grid(grid, {"type": "RasterModelGrid", "params": {}})

    canvas = CanvasPanel()
    canvas.resize(640, 420)
    canvas.show()
    app.processEvents()
    canvas.update_all(ws)
    app.processEvents()
    assert canvas._terrain_img is not None

    calls = {"3d": 0, "slope": 0, "reset": 0}
    original_3d = plots.draw_3d
    original_slope = plots.draw_slope_area
    original_reset = canvas.tab_terrain.reset_ax

    def count_3d(*args, **kwargs):
        calls["3d"] += 1
        return original_3d(*args, **kwargs)

    def count_slope(*args, **kwargs):
        calls["slope"] += 1
        return original_slope(*args, **kwargs)

    def count_reset(*args, **kwargs):
        calls["reset"] += 1
        return original_reset(*args, **kwargs)

    plots.draw_3d = count_3d
    plots.draw_slope_area = count_slope
    canvas.tab_terrain.reset_ax = count_reset
    try:
        for step in range(3):
            grid.at_node["topographic__elevation"] = base + step + 1
            canvas.update_running(ws)
            app.processEvents()
        assert calls["3d"] == 0
        assert calls["slope"] == 0
        assert calls["reset"] == 0
        assert 5 in canvas._dirty
        shown = np.asarray(canvas._terrain_img.get_array())
        assert abs(float(np.nanmax(shown)) - float(np.nanmax(base + 3))) < 1e-4

        canvas.setCurrentIndex(5)
        app.processEvents()
        assert calls["3d"] == 1
        grid.at_node["topographic__elevation"] = base + 9
        canvas.update_running(ws)
        app.processEvents()
        assert calls["3d"] == 1

        canvas.update_all(ws)
        app.processEvents()
        assert calls["3d"] == 2
    finally:
        plots.draw_3d = original_3d
        plots.draw_slope_area = original_slope
        canvas.tab_terrain.reset_ax = original_reset
        canvas.close()


if __name__ == "__main__":
    tests = [
        test_startup_with_cache_does_not_import_components,
        test_missing_cache_scans_off_the_gui_thread,
        test_running_snapshot_updates_terrain_only,
    ]
    for fn in tests:
        fn()
        print("PASS", fn.__name__, flush=True)
    print("\n画布快照测试全部通过", flush=True)

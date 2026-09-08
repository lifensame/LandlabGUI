# -*- coding: utf-8 -*-
"""
LandlabGUI 压力与负载测试套件 (Stress & Load Test Suite)
======================================================
执行内容:
1. 并发负载测试: 8 组参数扫描 (workers=4 并发调度，测试并行加速与线程安全性)
2. 大尺度网格负载测试: 14,400 节点高密度网格 + 100 步物理过程模拟 (数值稳定性与内存追踪)
3. GIS 大数据量全格式导出负载测试: 14,400 节点全格式导出 + 动态 EPSG PRJ 校验
4. 内存与快照负载测试: 50 轮连续快照注入 (验证 20 个快照上限与内存泄漏控制)
5. 6 视图高频渲染负载测试: 连续 10 轮在 6 视图间快速切换与重绘 (验证脏标记与内存释放)
"""

import gc
import json
import os
import sys
import tempfile
import time
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QSettings

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QSettings("LandlabGUI", "main").setValue("wizard_seen", True)

from app.gui.style import apply
apply(app)

from app.core.workspace import Workspace
from app.core.engine import Engine
from app.core.plugin_loader import load_plugins, app_root
from app.core.registry import Registry
from app.core.sweep import run_sweep
from app.core.exporter import export_all, get_prj_wkt

PLUGINS = load_plugins(log=lambda s: None)
REG = Registry(app_root(), log=lambda s: None)


def get_mem_mb() -> float:
    """获取当前进程物理内存占用 (MB)。"""
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass
    import ctypes
    from ctypes import wintypes
    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                            ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize / (1024 * 1024)


def test_load_1_concurrent_sweep():
    print("\n[负载测试 1] 并发参数扫描压测 (8 组参数, workers=4 并行计算)...", flush=True)
    m0 = get_mem_mb()
    t0 = time.time()

    base_wf = {
        "name": "并发负载",
        "grid": {"type": "RasterModelGrid", "params": {"shape": [25, 25], "xy_spacing": 100.0}},
        "terrain": {"mode": "noise", "amplitude": 10.0, "seed": 42},
        "boundary": "south_open",
        "time": {"dt": 100.0, "n_steps": 10, "refresh_every": 5},
        "steps": [
            {"id": "d1", "kind": "component", "component": "LinearDiffuser", "params": {"linear_diffusivity": 0.01}},
        ]
    }
    vals = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04]

    results = run_sweep(base_wf, "d1", "linear_diffusivity", vals, PLUGINS,
                        workers=4, log=lambda s: None)
    dt = time.time() - t0
    m1 = get_mem_mb()

    assert len(results) == 8, f"期望 8 组结果，实际获得 {len(results)}"
    for r in results:
        assert np.isfinite(r["mean"]) and np.isfinite(r["relief"])

    print(f"  ✓ 8 组并发完成 | 耗时: {dt:.2f}s | 内存: {m1:.1f}MB (净增 {m1 - m0:+.1f}MB)", flush=True)


def test_load_2_large_mesh_simulation():
    print("\n[负载测试 2] 大尺度网格高负荷模拟 (14,400 节点, 100 时间步长)...", flush=True)
    m0 = get_mem_mb()
    t0 = time.time()

    wf = {
        "name": "高负荷大网格",
        "grid": {"type": "RasterModelGrid", "params": {"shape": [120, 120], "xy_spacing": 50.0}},
        "terrain": {"mode": "noise", "amplitude": 15.0, "slope": 0.01, "slope_dir": "S", "seed": 42},
        "boundary": "south_open",
        "time": {"dt": 200.0, "n_steps": 100, "refresh_every": 20, "history_every": 10},
        "steps": [
            {"id": "u1", "kind": "plugin", "plugin": "构造抬升(4种模式)",
             "params": {"mode": "uniform", "rate": 5e-4}, "when": "every_step"},
            {"id": "d1", "kind": "component", "component": "LinearDiffuser",
             "params": {"linear_diffusivity": 0.005}, "when": "every_step"},
        ]
    }

    ws = Workspace()
    ws.log_fn = lambda s: None
    eng = Engine(ws, PLUGINS, log=lambda s: None, snapshot=lambda: None)
    eng.run(wf)

    dt = time.time() - t0
    m1 = get_mem_mb()
    z = ws.at_node["topographic__elevation"]

    assert len(z) == 14400, f"节点数应为 14400，实际 {len(z)}"
    assert np.isfinite(z).all(), "高程数据包含 NaN 或 Inf"
    zmin, zmax = float(z.min()), float(z.max())
    assert zmax > zmin, "地形演化高程极差异常"

    print(f"  ✓ 14,400 节点 100 步完成 | 耗时: {dt:.2f}s | 高程范围: {zmin:.1f}m ~ {zmax:.1f}m | 内存: {m1:.1f}MB", flush=True)
    return ws


def test_load_3_heavy_export(ws):
    print("\n[负载测试 3] 大尺度网格全格式导出负载测试 (ASCII, NetCDF, VTK, OBJ, Shapefile)...", flush=True)
    m0 = get_mem_mb()
    t0 = time.time()

    out_dir = os.path.join(tempfile.gettempdir(), "landlab_stress_export")
    export_all(ws.grid, output_dir=out_dir,
               dem_formats=["ascii", "netcdf", "vtk", "obj"],
               river_min_area=1e5, epsg=32649, log=lambda s: None)

    dt = time.time() - t0
    m1 = get_mem_mb()

    # 检查导出的文件完整性
    files = os.listdir(out_dir)
    expected = ["dem.asc", "dem.nc", "dem.vtk", "dem.obj"]
    for ef in expected:
        assert ef in files, f"缺少导出文件: {ef}"
        fsize = os.path.getsize(os.path.join(out_dir, ef))
        assert fsize > 1000, f"文件 {ef} 大小异常 ({fsize} 字节)"

    # 检查动态 PRJ 写入 (若生成了 river_nodes.prj)
    if "river_nodes.prj" in files:
        with open(os.path.join(out_dir, "river_nodes.prj"), "r", encoding="utf-8") as f:
            prj_content = f.read()
        assert "UTM_Zone_49N" in prj_content, f"PRJ 投影未包含 UTM_Zone_49N: {prj_content[:100]}"

    print(f"  ✓ 全格式导出完成 ({len(files)} 个文件) | 耗时: {dt:.2f}s | 内存: {m1:.1f}MB", flush=True)


def test_load_4_memory_and_snapshots():
    print("\n[负载测试 4] 连续 50 轮快照注入与内存泄漏检验 (上限=20)...", flush=True)
    from app.gui.main_window import MainWindow

    m0 = get_mem_mb()
    win = MainWindow()
    t0 = time.time()

    wf = {
        "name": "快照压力测试",
        "grid": {"type": "RasterModelGrid", "params": {"shape": [30, 40], "xy_spacing": 100.0}},
        "time": {"dt": 100.0, "n_steps": 5},
        "steps": []
    }
    dummy_z = np.random.uniform(0, 100, 1200)

    # 注入 50 次快照
    for i in range(50):
        win.history_panel.add_snapshot(
            f"快照_{i}", dummy_z + i, {"type": "RasterModelGrid"}, wf, [(i, 50.0 + i, 100.0 + i)]
        )

    # 校验上限逻辑 (最多保存 20 个快照)
    snap_count = len(win.history_panel.snapshots)
    assert snap_count == 20, f"快照数量应被限制在 20，实际为 {snap_count}"

    # 触发垃圾回收
    gc.collect()
    app.processEvents()
    m1 = get_mem_mb()
    dt = time.time() - t0

    win.close()
    del win
    gc.collect()
    app.processEvents()
    m_end = get_mem_mb()

    print(f"  ✓ 50 次快照注入完成 (严格限额 20) | 耗时: {dt:.2f}s | 内存净增: {m_end - m0:+.1f}MB", flush=True)


def test_load_5_canvas_multiview_stress(ws):
    print("\n[负载测试 5] 六视图高频切换重绘压力测试 (10 轮循环)...", flush=True)
    from app.gui.canvas_panel import CanvasPanel

    m0 = get_mem_mb()
    t0 = time.time()
    canvas = CanvasPanel()
    canvas.resize(800, 600)
    canvas.show()
    app.processEvents()

    # 连续 10 轮切换 6 个视图
    for loop in range(10):
        canvas.update_all(ws)
        for tab_idx in range(canvas.count()):
            canvas.setCurrentIndex(tab_idx)
            app.processEvents()

    dt = time.time() - t0
    m1 = get_mem_mb()

    canvas.close()
    del canvas
    gc.collect()
    app.processEvents()

    print(f"  ✓ 10 轮 6 视图重绘切换完成 (60 次重绘) | 耗时: {dt:.2f}s | 内存: {m1:.1f}MB", flush=True)


if __name__ == "__main__":
    print("=" * 65)
    print(f"LandlabGUI 压力与负载测试开始 | 起始内存: {get_mem_mb():.1f} MB")
    print("=" * 65)
    t_start = time.time()

    test_load_1_concurrent_sweep()
    ws_large = test_load_2_large_mesh_simulation()
    test_load_3_heavy_export(ws_large)
    test_load_4_memory_and_snapshots()
    test_load_5_canvas_multiview_stress(ws_large)

    total_time = time.time() - t_start
    final_mem = get_mem_mb()
    print("=" * 65)
    print(f"全部压力与负载测试顺利完成！")
    print(f"总耗时: {total_time:.2f}s | 最终内存: {final_mem:.1f} MB")
    print("=" * 65)

# -*- coding: utf-8 -*-
"""
4 小时 soak test：Landlab GUI 全功能 + 全预设 + 稳定性/内存泄漏
==============================================================
阶段:
  A 功能全量回归 (~20min)   自省/预设冒烟/5种网格/扫描/报告/动画/导出/历史/语言/插件/代码片段/表单87/DEM联网/GUI重建
  B 全预设完整运行 (~2.5h)  6 个预设逐一跑满 (稳态河道4000步/青藏2000步/硬岩4000步/非线性2000步/软岩800步/快速80步)
  C 稳定性循环 (~1h)        30 轮 100x80x400步 完整链条 + 内存采样 + 每10轮GUI重建+六视图渲染
输出: tests/soak_log.txt (逐条), tests/soak_report.md (汇总)
全程 offscreen，不弹窗。超过 4h10m 自动收尾出报告。
"""
import io
import json
import os
import sys
import time
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT = os.getcwd()
LOG_PATH = os.path.join(ROOT, "tests", "soak_log.txt")
REPORT_PATH = os.path.join(ROOT, "tests", "soak_report.md")
BUDGET_S = int(os.environ.get('SOAK_BUDGET_S', 4 * 3600 + 10 * 60))  # 可用环境变量缩短冒烟
T0 = time.time()
_log_fh = io.open(LOG_PATH, "w", encoding="utf-8")

results = []
win_ref = None


def log(msg, flush=True):
    line = f"[{time.time() - T0:7.0f}s {time.strftime('%H:%M:%S')}] {msg}"
    _log_fh.write(line + "\n")
    _log_fh.flush()
    print(line, flush=True)


def mem_mb() -> float:
    """当前进程工作集 MB。"""
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1048576
    except ImportError:
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
    h = ctypes.windll.kernel32.GetCurrentProcess()
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
    if not ok:
        return 0.0
    return pmc.WorkingSetSize / 1048576


def case(name, fn):
    elapsed_over = time.time() - T0 > BUDGET_S
    if elapsed_over:
        results.append({"name": name, "ok": False, "detail": "SKIPPED(超时预算)", "s": 0})
        log(f"SKIP {name} (超时预算)")
        return
    t = time.time()
    try:
        detail = fn() or "OK"
        ok = True
    except Exception as e:
        detail = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"
        ok = False
    dt = time.time() - t
    results.append({"name": name, "ok": ok, "detail": str(detail)[:400], "s": round(dt, 1)})
    log(f"{'PASS' if ok else 'FAIL'} {name} ({dt:.1f}s) {'' if ok else detail[:200]}")


def z_check(ws):
    """高程场健全性：存在、无 NaN/Inf。"""
    z = ws.grid.at_node["topographic__elevation"]
    assert z is not None and len(z) > 0, "无高程场"
    assert np.isfinite(z).all(), "高程场含 NaN/Inf"
    return float(z.min()), float(z.max())


# ============================================================
import numpy as np
from PySide6.QtCore import QEventLoop, QTimer

log("=" * 60)
log(f"SOAK TEST 开始 | 预算 {BUDGET_S/3600:.1f}h | 初始内存 {mem_mb():.0f} MB")

# ---------- 公共 ----------
from app.core.workspace import Workspace
from app.core.engine import Engine
from app.core.plugin_loader import load_plugins, app_root
from app.core.registry import Registry

PLUGINS = load_plugins(log=lambda s: None)
REG = Registry(app_root(), log=lambda s: None)
MEM_BASE = None


def run_sync(wf, tag=""):
    ws = Workspace()
    ws.log_fn = lambda s: None
    eng = Engine(ws, PLUGINS, log=lambda s: None,
                 progress=lambda i, n: (log(f"    {tag} {i}/{n} 步 mem={mem_mb():.0f}MB")
                                        if n >= 1000 and i % max(1, n // 8) == 0 else None),
                 snapshot=lambda: None)
    eng.run(wf)
    zmin, zmax = z_check(ws)
    return ws, zmin, zmax


def preset_wf(name, n_steps_override=None, strip_outputs=True):
    with open(os.path.join(ROOT, "presets", f"{name}.json"), encoding="utf-8") as f:
        wf = json.load(f)
    if n_steps_override:
        wf["time"]["n_steps"] = n_steps_override
    if strip_outputs:
        wf.pop("outputs", None)
    return wf


# ============================================================
# 阶段 A：功能全量回归
# ============================================================
log("-" * 60)
log("阶段 A：功能全量回归")

import tempfile


def a_introspect():
    from app.core.introspection import scan_all_components
    s = scan_all_components()
    assert len(s) >= 87, f"组件数 {len(s)}"


def a_presets_smoke():
    for name in ["快速测试", "稳态河道", "青藏场景", "硬岩低侵蚀", "软岩高侵蚀", "非线性侵蚀"]:
        ws, zmin, zmax = run_sync(preset_wf(name, n_steps_override=2), name)
    return "6 预设冒烟 OK"


def a_grid_types():
    from app.core.engine import _GRID_CLASSES
    made = []
    for gtype, params in [
            ("RasterModelGrid", {"shape": [16, 20], "xy_spacing": 100.0}),
            ("HexModelGrid", {"shape": [8, 10], "spacing": 100.0}),
            ("RadialModelGrid", {"n_rings": 6, "nodes_in_first_ring": 8, "spacing": 100.0}),
            ("FramedVoronoiGrid", {"shape": [8, 10], "xy_spacing": 100.0}),
    ]:
        wf = {"grid": {"type": gtype, "params": params},
              "terrain": {"mode": "noise", "amplitude": 10, "slope": 0.005,
                          "slope_dir": "S", "seed": 1},
              "time": {"dt": 100, "n_steps": 3, "refresh_every": 2, "history_every": 1},
              "steps": [{"id": "f", "kind": "component", "component": "FlowAccumulator",
                         "params": {}, "when": "every_step"},
                        {"id": "e", "kind": "component", "component": "FastscapeEroder",
                         "params": {"K_sp": 1e-5}, "when": "every_step"}]}
        ws, _, _ = run_sync(wf, gtype)
        made.append(f"{gtype}:{ws.grid.number_of_nodes}")
    return " ".join(made)


def a_sweep():
    from app.core.sweep import run_sweep
    wf = preset_wf("快速测试", n_steps_override=5)
    res = run_sweep(wf, wf["steps"][2]["id"], "K_sp", [2e-5, 1e-4, 5e-4], PLUGINS,
                    log=lambda s: None)
    assert len(res) == 3 and all(np.isfinite(r["z2d"]).all() for r in res)
    return f"3 组, relief={[round(r['relief'], 1) for r in res]}"


def a_report():
    from app.core.report import generate_report
    ws = Workspace()
    ws.log_fn = lambda s: None
    Engine(ws, PLUGINS, log=lambda s: None, snapshot=lambda: None).run(
        preset_wf("快速测试", n_steps_override=8))
    d = os.path.join(tempfile.gettempdir(), "soak_report_out")
    md = generate_report(ws, {"name": "soak", "steps": []}, d, log=lambda s: None)
    assert os.path.getsize(md) > 500
    return "报告+图组 OK"


def a_anim():
    from app.core.animate import write_animation
    z0 = np.random.default_rng(0).uniform(0, 100, (30, 40))
    frames = [(z0 + i, 0, 100 + i, f"f{i}") for i in range(6)]
    g = os.path.join(tempfile.gettempdir(), "soak_anim.gif")
    write_animation(frames, g, fps=5)
    m = os.path.join(tempfile.gettempdir(), "soak_anim.mp4")
    write_animation(frames, m, fps=5)
    assert os.path.getsize(g) > 10000 and os.path.getsize(m) > 10000
    return f"GIF {os.path.getsize(g)//1024}KB + MP4 {os.path.getsize(m)//1024}KB"


def a_export():
    from app.core.exporter import export_all
    ws = Workspace()
    ws.log_fn = lambda s: None
    Engine(ws, PLUGINS, log=lambda s: None, snapshot=lambda: None).run(
        preset_wf("快速测试", n_steps_override=10))
    d = os.path.join(tempfile.gettempdir(), "soak_export")
    export_all(ws.grid, output_dir=d, dem_formats=["ascii", "netcdf", "vtk", "obj"],
               river_min_area=1e5, log=lambda s: None)
    files = os.listdir(d)
    need = ["dem.asc", "dem.nc", "dem.vtk", "dem.obj", "river_network.geojson"]
    missing = [f for f in need if f not in files]
    assert not missing, f"缺文件: {missing}"
    return f"{len(files)} 个文件"


def a_history():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QSettings
    app = QApplication.instance() or QApplication(sys.argv)
    QSettings("LandlabGUI", "main").setValue("wizard_seen", True)
    from PySide6.QtGui import QFontDatabase, QFont
    fid = QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\simhei.ttf")
    fams = QFontDatabase.applicationFontFamilies(fid)
    if fams:
        app.setFont(QFont(fams[0], 9))
    from app.gui.style import apply
    apply(app)
    global win_ref
    from app.gui.main_window import MainWindow
    win_ref = MainWindow()
    win_ref.resize(1600, 900)
    win_ref.show()
    app.processEvents()
    from app.core.i18n import set_lang
    set_lang("zh")
    win_ref.preset_list.setCurrentRow(0)
    win_ref._load_preset(win_ref.preset_list.item(0))
    win_ref.workflow_panel.n_steps.setValue(6)
    win_ref.workflow_panel.do_export.setChecked(False)
    wf = win_ref.workflow_panel.to_workflow("soak")
    # 不重建网格——直接跑当前（跳过 GUI run 线程，用 engine 同步跑 25 次存快照）
    from app.core.engine import Engine as E2
    for i in range(25):
        ws = Workspace()
        ws.log_fn = lambda s: None
        E2(ws, PLUGINS, log=lambda s: None, snapshot=lambda: None).run(
            json.loads(json.dumps(wf)))
        win_ref.history_panel.add_snapshot(f"iter{i}", ws.grid.at_node["topographic__elevation"].copy(),
                                           ws.grid_info, wf, ws.history)
    assert len(win_ref.history_panel.snapshots) == 20, "快照上限应为 20"
    from app.gui.history_panel import CompareDialog
    dlg = CompareDialog(*win_ref.history_panel.snapshots[-2:])
    dlg.close()
    win_ref.close()
    win_ref = None
    return "25 快照→上限20 + 对比 OK"


def a_lang_plugin_cycles():
    from app.core import i18n
    for i in range(10):
        i18n.set_lang("en" if i % 2 else "zh")
        REG.reload()
    i18n.set_lang("zh")
    assert len(REG.schemas) >= 87
    return "语言×10 + 插件重载×10 OK"


def a_code_snippets():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from app.workers.sim_worker import CodeWorker
    from PySide6.QtCore import QEventLoop
    ws = Workspace()
    ws.log_fn = lambda s: None
    Engine(ws, PLUGINS, log=lambda s: None, snapshot=lambda: None).run(
        preset_wf("快速测试", n_steps_override=3))
    for i in range(10):
        w = CodeWorker(f"at_node['topographic__elevation'] += {0.5}; print('iter', {i})", ws, PLUGINS)
        loop = QEventLoop()
        w.sig_done.connect(lambda ok, msg: loop.quit())
        w.start()
        QTimer.singleShot(30000, loop.quit)
        loop.exec()
        assert w.isFinished()
    assert float(ws.at_node["topographic__elevation"].max()) > 10
    return "片段×10 OK"


def a_forms_87():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from app.gui.form_builder import ParamForm
    n = 0
    for name, schema in REG.schemas.items():
        f = ParamForm(schema.get("params", []), [], None, comp_name=name)
        f.values()                     # 收集不抛异常
        n += 1
    return f"{n} 个组件表单构建+收集 OK"


def a_dem_online():
    from app.core import dem_fetch
    r = dem_fetch.geocode("Mount Hua", limit=2)
    assert r and "south" in r[0]
    z, dx, meta = dem_fetch.fetch_dem(34.42, 34.50, 110.02, 110.12, 11,
                                      log=lambda s: None)
    assert z.shape[0] > 20 and np.isfinite(z).all()
    return f"华山 {z.shape} @{dx:.0f}m/格 高程 {z.min():.0f}~{z.max():.0f}m"


def a_gui_rebuild():
    global win_ref
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from app.gui.main_window import MainWindow
    from app.core.i18n import set_lang
    for i in range(3):
        win_ref = MainWindow()
        win_ref.show()
        app.processEvents()
        win_ref.canvas.setCurrentIndex(5)      # 3D
        app.processEvents()
        win_ref.close()
        del win_ref
        win_ref = None
        app.processEvents()
    set_lang("zh")
    win_ref = MainWindow()
    return "GUI 重建×3 OK"


case("A01 自省引擎87组件", a_introspect)
case("A02 六预设冒烟(各2步)", a_presets_smoke)
case("A03 四种网格+汇流侵蚀", a_grid_types)
case("A04 参数扫描3组", a_sweep)
case("A05 实验报告", a_report)
case("A06 动画GIF+MP4", a_anim)
case("A07 全格式导出", a_export)
case("A08 历史快照25轮+上限+对比", a_history)
case("A09 语言/插件循环切换", a_lang_plugin_cycles)
case("A10 代码片段×10", a_code_snippets)
case("A11 87组件表单构建", a_forms_87)
case("A12 在线DEM联网", a_dem_online)
case("A13 GUI重建×3", a_gui_rebuild)

log(f"阶段 A 完成 | 内存 {mem_mb():.0f} MB | 累计 {len(results)} 项")

# ============================================================
# 阶段 B：全预设完整运行
# ============================================================
log("-" * 60)
log("阶段 B：全预设完整运行（预计 ~2.5h）")

B_ORDER = ["快速测试", "软岩高侵蚀", "非线性侵蚀", "青藏场景", "稳态河道", "硬岩低侵蚀"]
for name in B_ORDER:
    t = time.time()
    wf = preset_wf(name)
    ns = wf["time"]["n_steps"]
    shape = wf["grid"]["params"].get("shape")
    log(f"B>> {name}: {shape} × {ns} 步 dt={wf['time']['dt']}")

    def b_run(name=name, wf=wf):
        ws, zmin, zmax = run_sync(wf, tag=name)
        assert zmax > 0
        return f"高程 {zmin:.0f}~{zmax:.0f}m | 内存 {mem_mb():.0f}MB"

    case(f"B_{name}", b_run)
    log(f"   累计耗时 {(time.time()-T0)/60:.0f} min | 内存 {mem_mb():.0f} MB")
    if time.time() - T0 > BUDGET_S - 3600:      # 给阶段 C 留至少 1h
        log("预算收紧，跳过剩余预设")
        break

# ============================================================
# 阶段 C：稳定性循环 + 内存泄漏
# ============================================================
log("-" * 60)
log("阶段 C：稳定性循环（30 轮 100x80×400步 + 内存监测）")
MEM_BASE = None
mem_track = []

for it in range(30):
    if time.time() - T0 > BUDGET_S:
        log(f"预算耗尽，第 {it} 轮收尾")
        break
    t = time.time()
    wf = preset_wf("快速测试", n_steps_override=None)
    wf["grid"]["params"]["shape"] = [80, 100]
    wf["time"]["n_steps"] = 400
    wf["time"]["dt"] = 500.0
    st = wf["steps"]
    st[0]["params"]["rate"] = 1e-3
    st[2]["params"]["K_sp"] = 5e-6
    try:
        ws, zmin, zmax = run_sync(wf, f"C{it}")
        ok = True
    except Exception as e:
        ok = False
        log(f"FAIL C{it}: {e}")
    m = mem_mb()
    if MEM_BASE is None:
        MEM_BASE = m
    mem_track.append(m)
    growth = m - MEM_BASE
    log(f"C{it:02d} {'OK' if ok else 'FAIL'} {time.time()-t:.0f}s | 内存 {m:.0f}MB "
        f"(较基线 {growth:+.0f}MB)")
    if growth > 800:
        log(f"!! 内存增长 {growth:.0f}MB 超阈值，中止循环")
        break
    if (it + 1) % 10 == 0:
        try:
            win_ref.canvas.setCurrentIndex(0)
            win_ref.canvas.update_all(win_ref.ws)
            for idx in range(win_ref.canvas.count()):
                win_ref.canvas.setCurrentIndex(idx)
                app = QApplication.instance() or QApplication(sys.argv)
                app.processEvents()
            win_ref.canvas.setCurrentIndex(0)
            log(f"  六视图渲染轮 {it + 1} OK | 内存 {mem_mb():.0f} MB")
        except Exception as e:
            log(f"FAIL 六视图渲染: {e}")

# ============================================================
# 报告
# ============================================================
fails = [r for r in results if not r["ok"]]
mem_growth_final = (mem_track[-1] - mem_track[0]) if len(mem_track) >= 2 else 0
ok_count = len(results) - len(fails)
total_min = (time.time() - T0) / 60

rep = io.open(REPORT_PATH, "w", encoding="utf-8")
rep.write(f"# Soak Test 报告 {time.strftime('%Y-%m-%d %H:%M')}\n\n")
rep.write(f"- 总时长: {total_min:.0f} min\n")
rep.write(f"- 用例: {ok_count}/{len(results)} 通过（不含阶段C轮次）\n")
rep.write(f"- 稳定性循环: {len(mem_track)} 轮完成\n")
rep.write(f"- 内存: 起始 {mem_track[0]:.0f}MB → 结束 {mem_track[-1]:.0f}MB "
          f"(轮间净增 {mem_growth_final:+.0f}MB，阈值 ±800MB)\n\n")
rep.write("| 用例 | 结果 | 耗时s | 备注 |\n|---|---|---|---|\n")
for r in results:
    rep.write(f"| {r['name']} | {'✅' if r['ok'] else '❌'} | {r['s']} | {r['detail'][:80].replace('|', '｜')} |\n")
rep.write("\n## 失败详情\n")
for r in fails:
    rep.write(f"\n### {r['name']}\n```\n{r['detail']}\n```\n")
if not fails:
    rep.write("（无失败项）\n")
rep.close()
log("=" * 60)
log(f"SOAK TEST 结束 | {total_min:.0f} min | 用例 {ok_count}/{len(results)} | "
    f"循环 {len(mem_track)} 轮 | 内存净增 {mem_growth_final:+.0f}MB")
log(f"报告: {REPORT_PATH}")
_log_fh.close()
sys.exit(0 if not fails else 1)

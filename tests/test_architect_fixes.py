# -*- coding: utf-8 -*-
"""
架构修复回归测试：
1. MainWindow 无重复 open_sweep 方法
2. form_builder.py 无重复导入
3. exporter.py 动态 EPSG PRJ 生成 (WGS84, 3857, UTM 49N, CGCS2000)
4. engine.py 工作流字段依赖 (DAG) 校验器
5. sweep.py 参数扫描多工作线程并发
6. MainWindow 非规则网格动画帧插值收集
"""
import ast
import os
import sys
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_1_no_duplicate_open_sweep():
    mw_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "app", "gui", "main_window.py")
    with open(mw_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=mw_path)

    main_win_cls = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "MainWindow":
            main_win_cls = node
            break
    assert main_win_cls is not None, "未找到 MainWindow 类"

    func_names = [n.name for n in main_win_cls.body if isinstance(n, ast.FunctionDef)]
    sweep_count = func_names.count("open_sweep")
    assert sweep_count == 1, f"open_sweep 方法重复定义，数量为 {sweep_count}"


def test_2_clean_imports_form_builder():
    fb_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "app", "gui", "form_builder.py")
    with open(fb_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    tr_imports = [line.strip() for line in lines if "import tr" in line]
    assert len(tr_imports) == 1, f"tr 存在重复导入: {tr_imports}"


def test_3_dynamic_epsg_prj():
    from app.core.exporter import get_prj_wkt

    # WGS84
    wkt_4326 = get_prj_wkt(4326)
    assert "WGS_1984" in wkt_4326 and "Degree" in wkt_4326

    # Web Mercator
    wkt_3857 = get_prj_wkt(3857)
    assert "Mercator" in wkt_3857 and "Meter" in wkt_3857

    # UTM Zone 49N (四川/青藏部分)
    wkt_utm49 = get_prj_wkt(32649)
    assert "UTM_Zone_49N" in wkt_utm49 and "Transverse_Mercator" in wkt_utm49

    # CGCS2000
    wkt_4490 = get_prj_wkt(4490)
    assert "CGCS2000" in wkt_4490 or "China_2000" in wkt_4490

    # 字符串形式输入支持
    wkt_str = get_prj_wkt("EPSG:32650")
    assert "UTM_Zone_50N" in wkt_str


def test_4_workflow_dependency_dag_validation():
    from app.core.engine import validate_workflow_dependencies

    # 1) 正确顺序: 汇流路由 -> 河流侵蚀
    valid_wf = {
        "steps": [
            {"id": "s1", "kind": "component", "component": "PriorityFloodFlowRouter"},
            {"id": "s2", "kind": "component", "component": "FastscapeEroder"},
        ]
    }
    issues = validate_workflow_dependencies(valid_wf)
    assert len(issues) == 0, f"正确工作流不应报错，但得到了: {issues}"

    # 2) 错误顺序: 只有 FastscapeEroder (缺失 drainage_area 和 flow__receiver_node)
    invalid_wf = {
        "steps": [
            {"id": "s1", "kind": "component", "component": "FastscapeEroder"},
        ]
    }
    issues_bad = validate_workflow_dependencies(invalid_wf)
    assert len(issues_bad) >= 1, "缺少前置汇流组件应检测出依赖缺失"
    missing_fields = {it["missing_field"] for it in issues_bad}
    assert "drainage_area" in missing_fields, "应检测出缺少 drainage_area"
    assert "PriorityFloodFlowRouter" in issues_bad[0]["suggestion"]


def test_5_sweep_concurrency():
    from app.core.sweep import run_sweep
    from app.core.plugin_loader import load_plugins

    plugins = load_plugins(log=lambda s: None)
    base_wf = {
        "name": "并发测试",
        "grid": {"type": "RasterModelGrid", "params": {"shape": [15, 15], "xy_spacing": 100.0}},
        "terrain": {"mode": "noise", "amplitude": 10.0, "seed": 42},
        "boundary": "south_open",
        "time": {"dt": 100.0, "n_steps": 2, "refresh_every": 2},
        "steps": [
            {"id": "d1", "kind": "component", "component": "LinearDiffuser", "params": {"linear_diffusivity": 0.01}},
        ]
    }

    vals = [0.01, 0.02, 0.05]

    # 单线程执行
    res_seq = run_sweep(base_wf, "d1", "linear_diffusivity", vals, plugins, workers=1, log=lambda *_: None)
    assert len(res_seq) == 3

    # 多线程并发执行
    res_par = run_sweep(base_wf, "d1", "linear_diffusivity", vals, plugins, workers=2, log=lambda *_: None)
    assert len(res_par) == 3

    # 确认结果数值一致
    for s_item, p_item in zip(res_seq, res_par):
        assert abs(s_item["mean"] - p_item["mean"]) < 1e-6
        assert abs(s_item["relief"] - p_item["relief"]) < 1e-6


def test_6_unstructured_grid_collect_frame():
    from PySide6.QtWidgets import QApplication
    from app.gui.main_window import MainWindow
    from landlab import HexModelGrid

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()

    # 设置六边形网格（无 shape 属性）
    hex_grid = HexModelGrid((10, 10), spacing=100.0)
    hex_grid.add_zeros("topographic__elevation", at="node")
    win.ws.set_grid(hex_grid, {"type": "HexModelGrid"})

    z = np.arange(hex_grid.number_of_nodes, dtype=float)
    win._collect_frame(z)

    # 验证帧成功记录，而非静默跳过
    assert len(win._frames) == 1
    assert win._frames[0][0].shape == (80, 80)
    win.close()


if __name__ == "__main__":
    tests = [
        test_1_no_duplicate_open_sweep,
        test_2_clean_imports_form_builder,
        test_3_dynamic_epsg_prj,
        test_4_workflow_dependency_dag_validation,
        test_5_sweep_concurrency,
        test_6_unstructured_grid_collect_frame,
    ]
    for t in tests:
        t()
        print("PASS", t.__name__, flush=True)
    print("\n所有架构修复回归测试全部通过！", flush=True)

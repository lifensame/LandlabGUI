# -*- coding: utf-8 -*-
"""
回归测试：在线 DEM 下载的显示、卡顿与落盘修复。
运行: QT_QPA_PLATFORM=offscreen python tests/test_dem_download_fixes.py

覆盖：
1. 预计网格信息不随经纬度范围/搜索结果刷新（显示 bug）
2. 状态栏网格尺寸顺序与网格 pill 不一致（rows×cols vs cols×rows）
3. 建网格在主线程执行导致下载完成后卡顿（大区域实测 1.5 s）
4. 下载的 DEM 不落盘，用户找不到数据
5. 缺少"打开下载文件夹"入口
"""
import ast
import json
import os
import shutil
import sys
import tempfile

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402

from landlab import RasterModelGrid  # noqa: E402
from landlab.io import esri_ascii  # noqa: E402

from app.core import dem_fetch  # noqa: E402

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MW_PATH = os.path.join(APP_DIR, "app", "gui", "main_window.py")

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QSettings("LandlabGUI", "main").setValue("wizard_seen", True)

from app.gui.style import apply  # noqa: E402
apply(app)


def _fresh_window():
    from app.gui.main_window import MainWindow
    return MainWindow()


_ORIG_DOWNLOADS_DIR = getattr(dem_fetch, "downloads_dir", None)


def _sandbox_dir():
    """把下载目录改到临时目录，避免污染仓库；用完需调用 _restore_dir()。"""
    tmp = tempfile.mkdtemp()
    os.makedirs(tmp, exist_ok=True)

    def _dir(base=None):
        return tmp

    dem_fetch.downloads_dir = _dir
    return tmp


def _restore_dir():
    if _ORIG_DOWNLOADS_DIR is None:      # 修复前模块里没有这个函数
        if hasattr(dem_fetch, "downloads_dir"):
            delattr(dem_fetch, "downloads_dir")
    else:
        dem_fetch.downloads_dir = _ORIG_DOWNLOADS_DIR


def _fake_fetch(shape=(12, 16), dx=30.0):
    """替换真实网络下载：返回确定性的南北单调高程。"""
    h, w = shape
    z2d = np.arange(h, dtype=float)[:, None] * 100 + np.arange(w, dtype=float)[None, :]
    meta = {"south": 30.0, "north": 30.1, "west": 110.0, "east": 110.1,
            "zoom": 12, "dx_m": dx, "shape": [h, w], "source": "test"}

    def fake(south, north, west, east, zoom, proxies=None, log=print):
        return z2d.copy(), dx, dict(meta)

    return fake


# --------------------------------------------------------------------------
def test_1_grid_estimate_refreshes_with_bbox():
    """改动经纬度范围后，"预计网格"必须立刻跟着变（原来只连了 zoom）。"""
    from app.gui.dem_dialog import DemDownloadDialog
    dlg = DemDownloadDialog(QSettings("LandlabGUI", "main"))
    try:
        before = dlg.info_label.text()
        assert before, "初始化后就应显示预计网格信息"

        # 换成一个大得多的区域（富士山尺度）
        dlg.sp_south.setValue(35.0)
        dlg.sp_north.setValue(35.6)
        dlg.sp_west.setValue(138.5)
        dlg.sp_east.setValue(138.9)
        after = dlg.info_label.text()
        assert after != before, f"范围变了但预计网格没刷新: {before!r} → {after!r}"

        expect = dem_fetch.dem_info(35.0, 35.6, 138.5, 138.9, dlg.zoom.value())
        w, h = expect["nodes"]
        assert f"{h}×{w}" in after, f"信息内容与当前范围不符: {after!r}"
    finally:
        dlg.close()


def test_2_search_result_selection_refreshes_estimate():
    """选中搜索结果（_fill_bbox）后也要刷新，即使数值恰好未变。"""
    from app.gui.dem_dialog import DemDownloadDialog
    dlg = DemDownloadDialog(QSettings("LandlabGUI", "main"))
    try:
        dlg.results = [{"name": "测试峰", "south": -10.0, "north": -9.0,
                        "west": 20.0, "east": 21.0}]
        dlg._fill_bbox(0)
        expect = dem_fetch.dem_info(-10.0, -9.0, 20.0, 21.0, dlg.zoom.value())
        w, h = expect["nodes"]
        assert f"{h}×{w}" in dlg.info_label.text(), "选中搜索结果后预计网格未刷新"
    finally:
        dlg.close()


def test_3_status_shape_order_matches_pill():
    """状态栏与网格 pill 的行列顺序必须一致（都按 landlab shape = rows×cols）。"""
    win = _fresh_window()
    tmp = _sandbox_dir()
    try:
        h, w = 12, 16           # 行列不等，顺序错了就会被发现
        grid = RasterModelGrid((h, w), xy_spacing=30.0)
        grid.at_node["topographic__elevation"] = np.arange(h * w, dtype=float)
        win._dem_cfg = {"name": "次序测试", "boundary": "south_open"}
        win._dem_result = {"grid": grid, "dx": 30.0, "meta": {},
                           "shape": [h, w], "path": None}
        win.func_worker = None
        win._on_dem_done(True, "完成")

        status = win.status_label.text()
        pill = win.pill_grid.text()
        assert f"{h}×{w}" in status, f"状态栏尺寸顺序错误（应 rows×cols）: {status!r}"
        assert f"{h}×{w}" in pill, f"网格 pill 尺寸顺序变了: {pill!r}"
    finally:
        win.close()
        _restore_dir()
        shutil.rmtree(tmp, ignore_errors=True)


def test_4_grid_build_moved_off_gui_thread():
    """建网格必须发生在后台线程函数里，而不是 _on_dem_done（否则界面卡顿）。"""
    with open(MW_PATH, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=MW_PATH)

    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "MainWindow")
    funcs = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert "_dem_download_and_build" in funcs, "缺少后台下载+建网格函数"

    def uses_grid_ctor(node):
        return any(isinstance(n, ast.Name) and n.id == "RasterModelGrid"
                   for n in ast.walk(node))

    assert uses_grid_ctor(funcs["_dem_download_and_build"]), \
        "建网格应在后台函数 _dem_download_and_build 中完成"
    assert not uses_grid_ctor(funcs["_on_dem_done"]), \
        "_on_dem_done 仍在主线程建网格（下载完成会卡一下）"


def test_5_download_saves_asc_to_disk():
    """_dem_download_and_build 必须把 DEM 落到磁盘，并能被应用原样读回。"""
    win = _fresh_window()
    tmp = _sandbox_dir()
    try:
        original = dem_fetch.fetch_dem
        dem_fetch.fetch_dem = _fake_fetch((12, 16), 30.0)
        try:
            cfg = {"south": 30.0, "north": 30.1, "west": 110.0, "east": 110.1,
                   "zoom": 12, "proxy": None, "boundary": "south_open",
                   "name": "华山/测试:峰"}
            res = win._dem_download_and_build(cfg)
        finally:
            dem_fetch.fetch_dem = original

        path = res.get("path")
        assert path and os.path.exists(path), f"DEM 未落盘: {path!r}"
        assert os.path.dirname(os.path.abspath(path)) == os.path.abspath(tmp)
        assert os.path.basename(path).endswith(".asc")
        assert not any(c in os.path.basename(path) for c in '\\/:*?"<>|'), \
            f"文件名含非法字符: {os.path.basename(path)}"

        # 应用导入 DEM 用的就是 esri_ascii.load，必须原样还原
        with open(path) as f:
            back = esri_ascii.load(f, at="node", name="topographic__elevation")
        assert back.shape == (12, 16)
        assert np.allclose(back.at_node["topographic__elevation"],
                           res["grid"].at_node["topographic__elevation"])
    finally:
        win.close()
        _restore_dir()
        shutil.rmtree(tmp, ignore_errors=True)


def test_6_on_dem_done_logs_saved_path():
    """下载完成后应在控制台告知保存路径，用户才知道数据在哪。"""
    win = _fresh_window()
    tmp = _sandbox_dir()
    try:
        logs = []
        win.log = logs.append
        h, w = 10, 12
        grid = RasterModelGrid((h, w), xy_spacing=30.0)
        grid.at_node["topographic__elevation"] = np.zeros(h * w)
        fake_path = os.path.join(tmp, "华山_20260101_000000.asc")
        win._dem_cfg = {"name": "华山", "boundary": "south_open"}
        win._dem_result = {"grid": grid, "dx": 30.0, "meta": {},
                           "shape": [h, w], "path": fake_path}
        win.func_worker = None
        win._on_dem_done(True, "完成")

        assert any(fake_path in m for m in logs), f"日志未给出保存路径: {logs}"
    finally:
        win.close()
        _restore_dir()
        shutil.rmtree(tmp, ignore_errors=True)


def test_7_open_folder_entry_points_exist():
    """「打开下载文件夹」入口：菜单项 + 对话框按钮（不依赖当前界面语言）。"""
    with open(MW_PATH, encoding="utf-8") as f:
        mw_src = f.read()
    assert "打开DEM下载文件夹" in mw_src, "网格菜单缺少「打开DEM下载文件夹」"
    assert "def open_dem_dir" in mw_src, "缺少 open_dem_dir 方法"

    from app.gui.dem_dialog import DemDownloadDialog
    from PySide6.QtWidgets import QDialogButtonBox
    dlg = DemDownloadDialog(QSettings("LandlabGUI", "main"))
    try:
        texts = [b.text() for b in dlg.findChildren(QDialogButtonBox)[0].buttons()]
        # 语言由 QSettings 决定，中英文都算通过
        assert any(("打开下载文件夹" in t) or ("Open Downloads Folder" in t)
                   for t in texts), f"对话框缺少按钮: {texts}"
    finally:
        dlg.close()


def test_8_downloads_dir_created_and_ignored():
    """下载目录应自动创建，且不进入版本库。"""
    assert _ORIG_DOWNLOADS_DIR is not None, "dem_fetch 缺少 downloads_dir()"
    tmp = tempfile.mkdtemp()
    try:
        d = _ORIG_DOWNLOADS_DIR(base=tmp)
        assert os.path.basename(d) == "dem_downloads", f"目录名不符: {d}"
        assert os.path.isdir(d), f"目录未创建: {d}"

        gi = open(os.path.join(APP_DIR, ".gitignore"), encoding="utf-8").read()
        assert "dem_downloads/" in gi, ".gitignore 未忽略 dem_downloads/"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_9_safe_filename():
    """地名里的路径分隔符/非法字符必须被清理，且仍有可读名字。"""
    assert _ORIG_DOWNLOADS_DIR is not None, "dem_fetch 缺少 safe_filename()"
    assert "/" not in dem_fetch.safe_filename("华山/测试")
    assert "\\" not in dem_fetch.safe_filename(r"a\b")
    assert dem_fetch.safe_filename('x:*?"<>|y') == "x_y"
    assert dem_fetch.safe_filename("   ") == "dem"
    assert dem_fetch.safe_filename("华山") == "华山"
    assert len(dem_fetch.safe_filename("长" * 200)) <= 60


if __name__ == "__main__":
    tests = [test_1_grid_estimate_refreshes_with_bbox,
             test_2_search_result_selection_refreshes_estimate,
             test_3_status_shape_order_matches_pill,
             test_4_grid_build_moved_off_gui_thread,
             test_5_download_saves_asc_to_disk,
             test_6_on_dem_done_logs_saved_path,
             test_7_open_folder_entry_points_exist,
             test_8_downloads_dir_created_and_ignored,
             test_9_safe_filename]
    for fn in tests:
        fn()
        print("PASS", fn.__name__, flush=True)
    print("\n在线DEM下载修复: 全部通过", flush=True)

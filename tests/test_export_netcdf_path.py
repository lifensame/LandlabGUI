# -*- coding: utf-8 -*-
"""
回归测试：导出到含中文的目录时，NetCDF 必须落到目标目录，而不是凭空产生乱码文件。
运行: python tests/test_export_netcdf_path.py

背景：netCDF4 的 C 层按系统编码(GBK)解析路径。当中文目录名的 UTF-8 字节恰好是
合法 GBK 序列时，它不抛异常，而是把文件写到当前目录下一个乱码文件名里
（实测 "gui_results_快速测试\\dem.nc" → 目标目录为空，却多出
 "gui_results_蹇...昞dem.nc"）。原有的 `except (FileNotFoundError, OSError)`
兜底因此完全不触发。修复方式是总是先写 ASCII 临时文件再移动。
"""
import os
import shutil
import sys
import tempfile

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from landlab import RasterModelGrid  # noqa: E402

from app.core import exporter  # noqa: E402


def _grid():
    g = RasterModelGrid((10, 12), xy_spacing=100.0)
    g.at_node["topographic__elevation"] = np.arange(120, dtype=float)
    g.add_zeros("drainage_area", at="node")
    return g


class _Cwd:
    """切到临时目录跑（游离文件正是相对当前目录产生的），结束恢复。"""

    def __init__(self):
        self.prev = os.getcwd()
        self.work = tempfile.mkdtemp()

    def __enter__(self):
        os.chdir(self.work)
        return self.work

    def __exit__(self, *exc):
        os.chdir(self.prev)
        shutil.rmtree(self.work, ignore_errors=True)


def _stray_files(work):
    return sorted(os.listdir(work))


# --------------------------------------------------------------------------
def test_1_netcdf_to_chinese_abs_dir():
    """绝对中文目录：文件必须出现在目标目录，且当前目录无游离文件。"""
    with _Cwd() as work:
        out = os.path.join(work, "gui_results_快速测试")
        os.makedirs(out, exist_ok=True)
        exporter.export_dem_netcdf(_grid(), os.path.join(out, "dem.nc"),
                                   log=lambda s: None)

        assert os.path.isfile(os.path.join(out, "dem.nc")), \
            f"NetCDF 未写入目标目录，目录内容: {os.listdir(out)}"
        stray = _stray_files(work)
        assert stray == ["gui_results_快速测试"], f"产生了游离文件: {stray}"


def test_2_netcdf_to_chinese_relative_dir():
    """相对中文目录（预设里就是这种写法）同样要正确落盘。"""
    with _Cwd() as work:
        rel = "gui_results_青藏场景"
        os.makedirs(rel, exist_ok=True)
        exporter.export_dem_netcdf(_grid(), os.path.join(rel, "dem.nc"),
                                   log=lambda s: None)

        assert os.path.isfile(os.path.join(rel, "dem.nc"))
        stray = _stray_files(work)
        assert stray == [rel], f"产生了游离文件: {stray}"


def test_3_export_all_with_netcdf_no_stray():
    """完整导出流程（ascii + netcdf）不应在别处留下乱码文件。"""
    with _Cwd() as work:
        out = os.path.join(work, "gui_results_硬岩低侵蚀")
        os.makedirs(out, exist_ok=True)
        exporter.export_all(_grid(), output_dir=out, dem_formats=["ascii", "netcdf"],
                            river_min_area=1e5, log=lambda s: None)

        assert os.path.isfile(os.path.join(out, "dem.nc"))
        assert os.path.isfile(os.path.join(out, "dem.asc"))
        stray = _stray_files(work)
        assert stray == [os.path.basename(out)], f"产生了游离文件: {stray}"


def test_4_netcdf_content_is_valid():
    """落盘后的文件必须是内容有效的 NetCDF（不是空壳或半截文件）。

    这里只校验文件头，不用 landlab.read_netcdf —— 读回同样受 netCDF4 中文
    路径限制，而应用本身不读 .nc（"从DEM导入"只接受 .asc），无需为此扩展。
    """
    with _Cwd() as work:
        out = os.path.join(work, "结果目录")
        os.makedirs(out, exist_ok=True)
        target = os.path.join(out, "dem.nc")
        exporter.export_dem_netcdf(_grid(), target, log=lambda s: None)

        assert os.path.getsize(target) > 0, "NetCDF 文件为空"
        with open(target, "rb") as f:
            magic = f.read(8)
        # NetCDF4 默认写 HDF5（\x89HDF...），经典格式是 CDF\x01/\x02
        assert magic.startswith(b"\x89HDF") or magic.startswith(b"CDF"), \
            f"文件头不是合法 NetCDF: {magic!r}"


def test_5_no_temp_leftover():
    """临时文件必须被清理：本例产生的 landlab_*.nc 不得残留在任一目录。"""
    with _Cwd() as work:
        out = os.path.join(work, "gui_results_快速测试")
        os.makedirs(out, exist_ok=True)
        exporter.export_dem_netcdf(_grid(), os.path.join(out, "dem.nc"),
                                   log=lambda s: None)

        for d in (work, out, tempfile.gettempdir()):
            leftovers = [f for f in os.listdir(d)
                         if f.startswith("landlab_") and f.endswith(".nc")]
            assert not leftovers, f"{d} 残留临时文件: {leftovers}"


def test_6_ascii_path_still_works():
    """纯 ASCII 目录不能被改坏（回归保护）。"""
    with _Cwd() as work:
        out = os.path.join(work, "results")
        os.makedirs(out, exist_ok=True)
        exporter.export_dem_netcdf(_grid(), os.path.join(out, "dem.nc"),
                                   log=lambda s: None)

        assert os.path.isfile(os.path.join(out, "dem.nc"))
        assert _stray_files(work) == ["results"]


if __name__ == "__main__":
    tests = [test_1_netcdf_to_chinese_abs_dir,
             test_2_netcdf_to_chinese_relative_dir,
             test_3_export_all_with_netcdf_no_stray,
             test_4_netcdf_content_is_valid,
             test_5_no_temp_leftover,
             test_6_ascii_path_still_works]
    for fn in tests:
        fn()
        print("PASS", fn.__name__, flush=True)
    print("\nNetCDF 中文路径导出: 全部通过", flush=True)

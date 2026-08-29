"""
示例插件：构造抬升（移植自教程 erosion_model.py 的 4 种抬升模式）
================================================================
放在 plugins/ 目录下，GUI 启动时自动加载；
修改本文件后在 GUI 菜单"插件->重载插件"即可热更新。
"""

import numpy as np

from app.core.api import plugin


@plugin(
    name="构造抬升(4种模式)",
    category="构造抬升",
    params={
        "mode": {"type": "str", "default": "uniform", "choices": ["uniform", "tibet", "gradient", "two_block"],
                 "doc": "uniform=均匀 | tibet=青藏式(北高南低) | gradient=线性梯度 | two_block=两块式"},
        "rate": {"type": "float", "default": 5e-4, "doc": "均匀抬升速率 m/yr (教程默认 5e-4)"},
        "south": {"type": "float", "default": 1e-4, "doc": "[tibet] 南侧低抬升率 m/yr"},
        "north": {"type": "float", "default": 1e-3, "doc": "[tibet] 北侧高抬升率 m/yr"},
        "gradient": {"type": "float", "default": 2e-6, "doc": "[gradient] 每格抬升增量 m/yr"},
        "block_low": {"type": "float", "default": 2e-4, "doc": "[two_block] 低抬升块 m/yr"},
        "block_high": {"type": "float", "default": 1e-3, "doc": "[two_block] 高抬升块 m/yr"},
        "boundary_frac": {"type": "float", "default": 0.5, "doc": "[two_block] 分界位置(0~1,南北比例)"},
    },
    doc="每个时间步为网格施加构造抬升，含教程全部 4 种抬升模式")
def tectonic_uplift(workspace, params):
    grid = workspace.grid
    if "topographic__elevation" not in grid.at_node:
        raise RuntimeError("网格缺少 topographic__elevation 字段")

    ny = grid.shape[0] if hasattr(grid, "shape") else 0
    nx = grid.shape[1] if hasattr(grid, "shape") else 0
    z = grid.at_node["topographic__elevation"]
    mode = params.get("mode", "uniform")

    if mode == "uniform":
        z += params.get("rate", 5e-4) * np.ones_like(z)

    elif mode == "tibet" and ny > 1:
        # 北侧高抬升、南侧低抬升（教程"青藏高原式"）
        y = np.repeat(np.arange(ny), nx)
        frac = y / (ny - 1)              # 0=南 1=北
        z += params.get("south", 1e-4) + frac * (params.get("north", 1e-3) - params.get("south", 1e-4))

    elif mode == "gradient" and nx > 1:
        x = np.tile(np.arange(nx), ny)
        z += params.get("rate", 5e-4) + params.get("gradient", 2e-6) * x

    elif mode == "two_block" and ny > 1:
        y = np.repeat(np.arange(ny), nx)
        frac = y / (ny - 1)
        boundary = params.get("boundary_frac", 0.5)
        z += np.where(frac >= boundary, params.get("block_high", 1e-3),
                      params.get("block_low", 2e-4))

    else:
        z += params.get("rate", 5e-4) * np.ones_like(z)

"""
工作区（Workspace）：GUI 会话的全部状态。
========================================
持有当前网格、字段快照、已创建的组件实例和运行历史；
既是引擎执行的对象上下文，也是插件函数收到的第一个参数。
"""

from __future__ import annotations

import numpy as np

from .i18n import tr


class Workspace:
    """一个 GUI 会话对应一个 Workspace（后续可扩展多会话标签页）。"""

    def __init__(self):
        self.grid = None                  # 当前 landlab 网格
        self.grid_info: dict = {}         # 网格描述 {type, params}
        self.components: dict = {}        # 最近一次运行实例化的组件 {step_id: 实例}
        self.history: list = []           # 每次 (步数, 平均高程, 最大高程) 记录
        self.log_fn = print               # GUI 注入的日志函数
        self.dt = 1.0                     # 当前时间步长(yr)：引擎在时间循环中注入，
                                          # 插件按 物理量×workspace.dt 施加通量

    # ---------- 网格 ----------
    @property
    def has_grid(self) -> bool:
        return self.grid is not None

    def set_grid(self, grid, info: dict):
        self.grid = grid
        self.grid_info = info
        self.log(tr("网格已建立: {0} {1}").format(info.get("type"), info.get("params", {})))

    # ---------- 字段 ----------
    def field_names(self, at: str = "node") -> list:
        """列出当前网格某位置组的全部字段名。"""
        if self.grid is None:
            return []
        group = getattr(self.grid, f"at_{at}", None)
        return list(group.keys()) if group is not None else []

    def get_field(self, name: str, at: str = "node") -> np.ndarray:
        return self.grid.at_node[name] if at == "node" else getattr(self.grid, f"at_{at}")[name]

    @staticmethod
    def field_or_none(container, name: str):
        """landlab FieldDataset.get() 存在已知问题（键存在也返回 None），统一用 in+[] 读取。"""
        return container[name] if name in container else None

    def ensure_field(self, name: str, at: str = "node", dtype=float, value=0.0):
        """确保字段存在，不存在则创建（供引擎自动补必填字段）。"""
        group = getattr(self.grid, f"at_{at}")
        if name not in group:
            arr = np.full(self.grid.number_of_nodes if at == "node" else
                          getattr(self.grid, f"number_of_{at}"), value, dtype=dtype)
            group[name] = arr
            self.log(tr("自动创建字段: {0} (at={1}, dtype={2})").format(name, at, dtype.__name__))
            return True
        return False

    # ---------- 便捷写法（插件里直接用） ----------
    @property
    def at_node(self):
        """插件中 workspace.at_node["topographic__elevation"] 直接读写高程。"""
        return self.grid.at_node

    def log(self, msg: str):
        self.log_fn(str(msg))

    # ---------- 初始地形 ----------
    def init_terrain(self, mode: str = "noise", amplitude: float = 10.0,
                     slope: float = 0.01, slope_dir: str = "S", seed: int = 42):
        """生成初始地形。mode: noise(噪声+坡度) / gaussian(高斯山) / flat(平地)。

        坡度用节点坐标施加（对栅格/六边形/Voronoi 等所有网格类型通用）；
        高斯山仅对规则网格（有 shape）可用，否则回退为噪声。
        """
        g = self.grid
        rng = np.random.default_rng(seed)
        n = g.number_of_nodes
        z = rng.uniform(0, amplitude, n) if mode in ("noise", "gaussian") \
            else np.zeros(n)
        if mode == "gaussian":
            shape = getattr(g, "shape", None)
            if shape and len(shape) == 2 and shape[0] * shape[1] == n:
                ny, nx = shape
                yy, xx = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
                z = amplitude * np.exp(-(((xx - nx * 0.5) / (nx * 0.15)) ** 2 +
                                         ((yy - ny * 0.5) / (ny * 0.15)) ** 2)).reshape(-1)
        if slope > 0:
            # 坐标倾斜：出水口一侧地势最低（对任意网格类型通用）
            y, x = g.y_of_node, g.x_of_node
            tilt = {"S": y - y.min(), "N": y.max() - y,
                    "E": x - x.min(), "W": x.max() - x}.get(slope_dir, y - y.min())
            z = z + slope * tilt
        self.at_node["topographic__elevation"] = z
        self.log(tr("初始地形: {0}, 幅度={1}, 坡度={2} 方向={3}").format(mode, amplitude, slope, slope_dir))

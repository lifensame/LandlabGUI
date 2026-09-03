"""
可视化画布：六个标签页 —— 地形 / 面积 / 坡度-面积 / 剖面 / 历史 / 3D地形。
- 每页带 matplotlib 导航工具栏（缩放/平移/保存/回退）
- 地形页支持点击查值（显示该节点全部字段）与"取点剖面"（两点任意方向剖面）
绘图逻辑全部在 app.core.plots（与实验报告共用）。
"""

from __future__ import annotations

import numpy as np

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QTabWidget,
                               QVBoxLayout, QWidget)

from ..core import plots
from ..core.i18n import tr

matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False


class _PlotTab(QWidget):
    """带导航工具栏的单个 matplotlib 标签页。"""

    def __init__(self, title="", xlabel="", ylabel="", toolbar=True, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)
        self.fig = Figure(figsize=(5, 4))
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.title, self.xlabel, self.ylabel = title, xlabel, ylabel
        self.ax = self.fig.add_subplot(111)
        self.ax.set_title(title)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        lay.addWidget(self.canvas, stretch=1)
        self.toolbar = NavigationToolbar2QT(self.canvas, self) if toolbar else None
        if self.toolbar is not None:
            tb = QHBoxLayout()
            tb.addWidget(self.toolbar)
            lay.addLayout(tb)

    def reset_ax(self, projection: str = "2d"):
        """彻底重建坐标轴。

        ax.clear() 不会移除 colorbar 创建的独立坐标轴，反复刷新会堆积色标、
        挤压主图 —— 这里用 fig.clf() 一次性解决（工具栏绑定的是 canvas，
        不受重建影响）。
        """
        self.fig.clf()
        if projection == "3d":
            self.ax = self.fig.add_subplot(111, projection="3d")
        else:
            self.ax = self.fig.add_subplot(111)
            self.ax.set_xlabel(self.xlabel)
            self.ax.set_ylabel(self.ylabel)
        try:
            self.fig.tight_layout()      # 每次渲染排一次（渲染已节流，开销可忽略）
        except Exception:
            pass

    def draw(self):
        from ..core.i18n import tr as _tr
        self.ax.set_title(_tr(self.title))
        self.canvas.draw_idle()


class CanvasPanel(QTabWidget):
    """右侧可视化区。"""

    _TABS_ZH = ["地形", "面积", "坡度-面积", "剖面", "历史", "3D地形"]

    @property
    def TABS(self):
        return [tr(t) for t in self._TABS_ZH]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ws = None
        self.tab_terrain = _PlotTab(tr("地形高程 (m)"))
        self.tab_area = _PlotTab(tr("汇水面积 log10(m²)"))
        self.tab_slope_area = _PlotTab(tr("坡度-面积"), tr("汇水面积 A (m²)"), tr("坡度 S"))
        self.tab_profile = _PlotTab(tr("河道纵剖面"), tr("沿程距离 (m)"), tr("高程 (m)"))
        self.tab_history = _PlotTab(tr("演化历史"), tr("步数"), tr("高程 (m)"))
        self.tab_3d = _PlotTab(tr("3D地形"), tr("X (m)"), tr("Y (m)"))
        self.tab_3d.ax.remove()
        self.tab_3d.ax = self.tab_3d.fig.add_subplot(111, projection="3d")

        for i, t in enumerate([self.tab_terrain, self.tab_area, self.tab_slope_area,
                               self.tab_profile, self.tab_history, self.tab_3d]):
            self.addTab(t, self.TABS[i])

        # ---- 地形页辅助条：取点剖面 + 查值显示 ----
        bar = QHBoxLayout()
        self.btn_pick = QPushButton(tr("📏 取点剖面"))
        self.btn_pick.setCheckable(True)
        self.btn_pick.setToolTip(tr("勾选后在地形图上点两个点，即画出任意方向的地形剖面"))
        self.btn_pick.toggled.connect(self._toggle_pick)
        bar.addWidget(self.btn_pick)
        self.pick_hint = QLabel("")
        self.pick_hint.setStyleSheet("color:#3daee9;")
        bar.addWidget(self.pick_hint)
        bar.addStretch()
        wrap = QWidget()
        wrap.setLayout(bar)
        self.tab_terrain.layout().insertWidget(1, wrap)

        self.info_label = QLabel(tr("💡 运行后图表才有数据；点击图查数值；工具栏：🔍缩放 ✥平移（⌂◀▶ 在用过缩放后才亮起）"))
        self.info_label.setStyleSheet("color:#9aa0a6;")
        self.info_label.setWordWrap(True)
        wrap2 = QWidget()
        v = QVBoxLayout(wrap2)
        v.setContentsMargins(4, 0, 4, 2)
        v.addWidget(self.info_label)
        self.tab_terrain.layout().insertWidget(2, wrap2)

        # ---- 事件 ----
        self._picking = False
        self._pick_points = []
        self._custom_profiles = []          # [(label, dists, elevs)]
        self._dirty = set(range(6))         # 待刷新标签页（性能：只画可见页）
        self.currentChanged.connect(self._on_tab_changed)
        for tab in (self.tab_terrain, self.tab_area):
            tab.canvas.mpl_connect("button_press_event", self._on_click)

    # ================================================= 更新
    # 性能模型：update_all 只渲染"当前可见的标签页"，其余标记待刷新，
    # 切到时按需渲染（_on_tab_changed）。6 视图全部重画是卡顿根源。
    def update_all(self, ws, note: str = ""):
        self._ws = ws
        if not ws.has_grid:
            return
        if not ("topographic__elevation" in ws.at_node):
            return
        idx = self.currentIndex()
        self._render_tab(idx)
        for i in range(self.count()):
            if i != idx:
                self._dirty.add(i)

    def _render_tab(self, idx: int):
        """渲染指定标签页（只画看得到的那个）。"""
        self._dirty.discard(idx)
        ws = self._ws
        if ws is None or not ws.has_grid:
            return
        if not ("topographic__elevation" in ws.at_node):
            return
        grid = ws.grid
        z = ws.at_node["topographic__elevation"]
        if idx == 0:
            self.tab_terrain.reset_ax()
            ax = self.tab_terrain.ax
            plots.draw_field(ax, grid, z, colorbar_fig=self.tab_terrain.fig)
            self._draw_custom_profile_lines(ax, grid)
            self.tab_terrain.draw()
        elif idx == 1:
            self.tab_area.reset_ax()
            ax = self.tab_area.ax
            if "drainage_area" in ws.at_node:
                plots.draw_field(ax, grid, np.log10(np.maximum(ws.at_node["drainage_area"], 1.0)),
                                 cmap="viridis", colorbar_fig=self.tab_area.fig)
            else:
                ax.text(0.5, 0.5, tr("运行含汇流组件后显示"), transform=ax.transAxes,
                        ha="center", va="center", color="gray")
            self.tab_area.draw()
        elif idx == 2:
            self.tab_slope_area.ax.clear()
            plots.draw_slope_area(self.tab_slope_area.ax, ws)
            self.tab_slope_area.draw()
        elif idx == 3:
            self._render_profile_tab()
        elif idx == 4:
            self.tab_history.ax.clear()
            plots.draw_history(self.tab_history.ax, ws)
            self.tab_history.draw()
        elif idx == 5:
            self._render_3d()

    def _on_tab_changed(self, idx):
        if idx in self._dirty:
            self._render_tab(idx)

    def _render_profile_tab(self):
        ax = self.tab_profile.ax
        ax.clear()
        plots.draw_river_profile(ax, self._ws)
        for label, dists, elevs in self._custom_profiles:
            ax.plot(dists, elevs, lw=2.0, color="#f5c542", label=label)
        if self._custom_profiles:
            ax.legend()
        self.tab_profile.draw()

    def _render_3d(self, z=None):
        ws = self._ws
        if not ws or not ws.has_grid:
            return
        tab = self.tab_3d
        tab.reset_ax(projection="3d")
        z = z if z is not None else (
                ws.at_node["topographic__elevation"]
                if "topographic__elevation" in ws.at_node else None)
        if z is None:
            tab.draw()
            return
        plots.draw_3d(tab.ax, ws.grid, z)
        tab.ax.set_xlabel("X (m)")
        tab.ax.set_ylabel("Y (m)")
        tab.ax.set_zlabel(tr("高程 (m)"))
        tab.draw()

    def refresh_3d_only(self):
        self._dirty.discard(5)
        self._render_tab(5)

    # ================================================= 点击查值
    def _on_click(self, event):
        if event.inaxes is None or event.xdata is None or self._ws is None:
            return
        if getattr(event.canvas, "toolbar", None) is not None and event.canvas.toolbar.mode:
            return                        # 平移/缩放模式下不响应
        ws = self._ws
        if not ws.has_grid:
            return
        x, y = float(event.xdata), float(event.ydata)
        g = ws.grid
        if self._picking and event.inaxes is self.tab_terrain.ax:
            self._handle_pick(x, y, g)
            return
        try:
            node = g.find_nearest_node((x, y))
        except Exception:
            node = int(np.argmin((g.x_of_node - x) ** 2 + (g.y_of_node - y) ** 2))
        node = int(node)
        parts = [tr("节点 {0}  ({1}, {2})").format(node, f"{x:.0f}", f"{y:.0f}")]
        shown = 0
        for name, arr in ws.at_node.items():
            if shown >= 8:
                parts.append("...")
                break
            try:
                v = float(arr[node])
                parts.append(f"{name}={v:.4g}")
                shown += 1
            except Exception:
                continue
        self.info_label.setText("📍 " + "  |  ".join(parts))

    # ================================================= 取点剖面
    def _toggle_pick(self, on):
        self._picking = on
        self._pick_points.clear()
        self.pick_hint.setText(tr("点击第 1 个点...") if on else "")

    def _handle_pick(self, x, y, grid):
        self._pick_points.append((x, y))
        if len(self._pick_points) == 1:
            self.pick_hint.setText(tr("已选 A({0},{1})，点击第 2 个点...").format(f"{x:.0f}", f"{y:.0f}"))
            return
        p0, p1 = self._pick_points
        self._pick_points.clear()
        z = (self._ws.at_node["topographic__elevation"]
             if "topographic__elevation" in self._ws.at_node else None)
        if z is None:
            return
        dists, elevs = plots.sample_profile(grid, z, p0, p1)
        n = len(self._custom_profiles) + 1
        label = tr("剖面{n}: A-B").format(n=n)
        self._custom_profiles.append((label, dists, elevs))
        if len(self._custom_profiles) > 5:
            self._custom_profiles.pop(0)
        self.tab_profile.ax.clear()
        plots.draw_river_profile(self.tab_profile.ax, self._ws)
        for lb, d, e in self._custom_profiles:
            self.tab_profile.ax.plot(d, e, lw=2.0, color="#f5c542", label=lb)
        self.tab_profile.ax.legend()
        self.tab_profile.ax.set_title(tr("河道纵剖面") + " + " + tr("剖面"))
        self.tab_profile.draw()
        # 地形图上标记线段
        ax = self.tab_terrain.ax
        ax.plot([p0[0], p1[0]], [p0[1], p1[1]], "-", color="#f5c542", lw=1.5, alpha=0.9)
        ax.plot(*zip(p0, p1), "o", color="#f5c542", ms=4)
        self.tab_terrain.draw()
        self.pick_hint.setText(tr("剖面已画出（黄线），共 {0} 个采样点").format(len(dists)))
        self.setCurrentWidget(self.tab_profile)

    def _draw_custom_profile_lines(self, ax, grid):
        """重绘地形时恢复已取的剖面线段（仅保留最新3条避免混乱）。"""
        # 简化：重绘后不保留旧线段（坐标已随视图变化），只清空记录
        if self._custom_profiles:
            pass    # 保留数据供剖面标签页显示

    def clear_custom_profiles(self):
        self._custom_profiles.clear()
        self._render_profile_tab()

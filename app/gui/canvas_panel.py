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
        self.ax = self.fig.add_subplot(111)
        self.title = title
        self.ax.set_title(title)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        lay.addWidget(self.canvas, stretch=1)
        self.toolbar = NavigationToolbar2QT(self.canvas, self) if toolbar else None
        if self.toolbar is not None:
            tb = QHBoxLayout()
            tb.addWidget(self.toolbar)
            lay.addLayout(tb)

    def draw(self):
        from ..core.i18n import tr as _tr
        self.ax.set_title(_tr(self.title))
        try:
            self.fig.tight_layout()
        except Exception:
            pass
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

        self.info_label = QLabel(tr("💡 点击地形/面积图可查看该点数值；工具栏可缩放平移"))
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
        self._3d_dirty = False              # 3D 惰性渲染标记
        self.currentChanged.connect(self._on_tab_changed)
        for tab in (self.tab_terrain, self.tab_area):
            tab.canvas.mpl_connect("button_press_event", self._on_click)

    # ================================================= 更新
    def update_all(self, ws, note: str = ""):
        self._ws = ws
        if not ws.has_grid:
            return
        grid = ws.grid
        z = ws.at_node.get("topographic__elevation")
        if z is None:
            return
        ax = self.tab_terrain.ax
        ax.clear()
        plots.draw_field(ax, grid, z, colorbar_fig=self.tab_terrain.fig)
        self._draw_custom_profile_lines(ax, grid)
        self.tab_terrain.draw()

        ax = self.tab_area.ax
        ax.clear()
        if "drainage_area" in ws.at_node:
            plots.draw_field(ax, grid, np.log10(np.maximum(ws.at_node["drainage_area"], 1.0)),
                             cmap="viridis", colorbar_fig=self.tab_area.fig)
        else:
            ax.text(0.5, 0.5, "运行含汇流组件后显示", transform=ax.transAxes,
                    ha="center", va="center", color="gray")
        self.tab_area.draw()

        self.tab_slope_area.ax.clear()
        plots.draw_slope_area(self.tab_slope_area.ax, ws)
        self.tab_slope_area.draw()

        self._render_profile_tab()

        self.tab_history.ax.clear()
        plots.draw_history(self.tab_history.ax, ws)
        self.tab_history.draw()

        # 3D 渲染开销大：仅在 3D 标签页可见时实时渲染，否则标记待刷新
        if self.currentWidget() is self.tab_3d:
            self._render_3d(z)
        else:
            self._3d_dirty = True

    def _on_tab_changed(self, _idx):
        if self.currentWidget() is self.tab_3d and self._3d_dirty:
            self._3d_dirty = False
            self._render_3d()

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
        tab.ax.clear()
        z = z if z is not None else ws.at_node.get("topographic__elevation")
        if z is None:
            tab.draw()
            return
        plots.draw_3d(tab.ax, ws.grid, z)
        tab.ax.set_xlabel("X (m)")
        tab.ax.set_ylabel("Y (m)")
        tab.ax.set_zlabel("高程 (m)")
        tab.draw()

    def refresh_3d_only(self):
        if self._ws and self._ws.has_grid:
            self._3d_dirty = False
            self._render_3d()

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
        z = self._ws.at_node.get("topographic__elevation")
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

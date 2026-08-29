"""
运行历史面板：自动记录每次运行快照，支持 A/B 对比与回滚继续演化。
"""

from __future__ import annotations

import datetime

import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..core import plots
from ..core.i18n import tr


class RunSnapshot:
    """一次运行的快照（内存中，最多保留 MAX 条）。"""

    MAX = 20

    def __init__(self, name, z, grid_info, wf, history):
        self.name = name
        self.time = datetime.datetime.now()
        self.z = np.asarray(z, dtype=np.float32)          # 节省内存
        self.grid_info = dict(grid_info or {})
        self.wf = wf or {}
        self.history = list(history or [])
        self.z2d = None                                    # 惰性生成缩略图
        shape = self.grid_info.get("params", {}).get("shape")
        if shape and len(shape) == 2 and shape[0] * shape[1] == z.size:
            self.z2d = self.z.reshape(shape)

    @property
    def label(self):
        return f"{self.time:%H:%M:%S}  {self.name} ({tr('终点高程均值 {0}m').format(f'{np.nanmean(self.z):.1f}')})"


class HistoryPanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self.snapshots: list[RunSnapshot] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        self.listw = QListWidget()
        self.listw.setToolTip(tr("每次运行结束自动记录；选中两条可A/B对比，选中一条可回滚"))
        lay.addWidget(self.listw)
        btns = QHBoxLayout()
        b_cmp = QPushButton(tr("A/B 对比"))
        b_cmp.clicked.connect(self.compare_selected)
        b_rb = QPushButton(tr("回滚到此快照"))
        b_rb.clicked.connect(self.rollback_selected)
        b_del = QPushButton(tr("删除"))
        b_del.clicked.connect(self.delete_selected)
        for b in (b_cmp, b_rb, b_del):
            btns.addWidget(b)
        lay.addLayout(btns)

    # ------------------------------------------------ 记录
    def add_snapshot(self, name, z, grid_info, wf, history):
        snap = RunSnapshot(name, z, grid_info, wf, history)
        self.snapshots.append(snap)
        if len(self.snapshots) > RunSnapshot.MAX:
            self.snapshots.pop(0)
        self.refresh()

    def refresh(self):
        self.listw.clear()
        for s in reversed(self.snapshots):              # 最新在上
            item = QListWidgetItem(s.label)
            item.setData(Qt.UserRole, s)
            self.listw.addItem(item)

    def _selected(self) -> list:
        return [it.data(Qt.UserRole) for it in self.listw.selectedItems()]

    # ------------------------------------------------ A/B 对比
    def compare_selected(self):
        sel = self._selected()
        if len(sel) != 2:
            QMessageBox.information(self, tr("A/B 对比"), tr("请按住 Ctrl 选中恰好两条快照"))
            return
        dlg = CompareDialog(sel[0], sel[1], self)
        dlg.exec()

    # ------------------------------------------------ 回滚
    def rollback_selected(self):
        sel = self._selected()
        if len(sel) != 1:
            QMessageBox.information(self, tr("回滚到此快照"), tr("请选中一条快照"))
            return
        snap = sel[0]
        mw = self.mw
        if not snap.wf.get("grid"):
            QMessageBox.warning(self, tr("无法回滚"),
                                tr("该快照没有网格配置（交互建的网格），无法重建。\n"
                                   "提示：载入预设运行后即可回滚。"))
            return
        try:
            from ..core.engine import Engine
            eng = Engine(mw.ws, mw.registry.plugins, log=mw.log)
            eng._build_grid(snap.wf["grid"])
            if snap.wf.get("boundary"):
                eng._apply_boundary(snap.wf["boundary"])
            mw.ws.at_node["topographic__elevation"] = np.asarray(snap.z, dtype=float)
            mw.ws.history = list(snap.history)
            mw.canvas.update_all(mw.ws)
            mw.workflow_panel.load_workflow(snap.wf)
            mw.log(tr("已回滚到快照: {0}（可继续点运行演化）").format(snap.label))
            QMessageBox.information(mw, tr("回滚成功"),
                                    tr("已恢复该时刻的地形。\n注意：组件内部状态会重新实例化，直接点运行即可继续演化。"))
        except Exception as e:
            QMessageBox.critical(mw, tr("回滚失败"), str(e))

    def delete_selected(self):
        sel = self._selected()
        for s in sel:
            if s in self.snapshots:
                self.snapshots.remove(s)
        self.refresh()


class CompareDialog(QDialog):
    """两条快照并排对比：地形 + 剖面 + 统计差。"""

    def __init__(self, a: RunSnapshot, b: RunSnapshot, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("A/B 对比") + f": {a.name} vs {b.name}")
        self.resize(1000, 560)
        lay = QVBoxLayout(self)

        fig = Figure(figsize=(10, 4.6))
        canvas = FigureCanvasQTAgg(fig)
        lay.addWidget(canvas, stretch=1)

        za, zb = np.asarray(a.z, float), np.asarray(b.z, float)
        for ax, snap, z, tag in ((fig.add_subplot(1, 2, 1), a, za, "A"),
                                 (fig.add_subplot(1, 2, 2), b, zb, "B")):
            grid = _GridStub(snap)
            plots.draw_field(ax, grid, z, colorbar_fig=fig)
            ax.set_title(f"{tag}: {snap.name}")

        za, zb = za.astype(float), zb.astype(float)
        if za.size == zb.size:
            diff = zb - za
            txt = (tr("B−A 差值: 平均 {0} m | 最大 {1} m | 起伏 A={2}m, B={3}m").format(
            f"{np.nanmean(diff):+.2f}", f"{np.nanmax(diff):.2f}",
            f"{np.nanmax(za)-np.nanmin(za):.1f}", f"{np.nanmax(zb)-np.nanmin(zb):.1f}"))
        else:
            txt = tr("两次运行网格不同，无法逐点求差")
        lbl = QLabel(txt)
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        bb.clicked.connect(self.close)
        lay.addWidget(bb)


class _GridStub:
    """给 draw_field 用的轻量网格描述（快照不保存原网格对象）。"""

    def __init__(self, snap: RunSnapshot):
        params = snap.grid_info.get("params", {})
        shape = params.get("shape")
        self.shape = tuple(shape) if shape and len(shape) == 2 and \
            shape[0] * shape[1] == snap.z.size else None
        self.number_of_nodes = snap.z.size
        self.dx = float(params.get("xy_spacing", 1.0))

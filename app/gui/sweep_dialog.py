"""
参数扫描实验对话框：选步骤/参数/范围 → 后台批量运行 → 结果窗口对比图。
"""

from __future__ import annotations

import csv
import os

import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QProgressDialog,
                               QPushButton, QSpinBox, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core import sweep
from ..core.i18n import tr

SWEEP_PARAM_TAG = "__sweep_param__"


class SweepDialog(QDialog):
    """配置参数扫描；只负责收集配置，执行由主窗口托管（保证线程/结果窗口生命周期）。"""

    def __init__(self, workflow_panel, parent=None):
        super().__init__(parent)
        self.wfp = workflow_panel
        self.setWindowTitle(tr("参数扫描批量实验"))
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        tip = QLabel(tr("原理: 载入预设（或含网格配置的工作流）后，固定其他条件，\n"
                     "仅让一个参数在范围内取值，逐一完整模拟并对比结果。\n"
                     "建议先用小网格+少步数试跑一遍，再放大正式扫描。"))
        tip.setWordWrap(True)
        root.addWidget(tip)

        gb1 = QGroupBox(tr("扫描目标"))
        f1 = QFormLayout(gb1)
        self.step_combo = QComboBox()
        self.step_combo.currentIndexChanged.connect(self._refresh_params)
        f1.addRow(tr("目标步骤"), self.step_combo)
        self.param_combo = QComboBox()
        f1.addRow(tr("目标参数"), self.param_combo)
        root.addWidget(gb1)

        gb2 = QGroupBox(tr("取值范围"))
        f2 = QFormLayout(gb2)
        self.lo = QDoubleSpinBox()
        self.lo.setDecimals(8)
        self.lo.setRange(-1e12, 1e12)
        self.hi = QDoubleSpinBox()
        self.hi.setDecimals(8)
        self.hi.setRange(-1e12, 1e12)
        self.n = QSpinBox()
        self.n.setRange(2, 30)
        self.n.setValue(4)
        self.log_scale = QCheckBox(tr("对数等比（适合 K_sp 等跨数量级参数）"))
        self.log_scale.setChecked(True)
        f2.addRow(tr("起始值"), self.lo)
        f2.addRow(tr("终止值"), self.hi)
        f2.addRow(tr("取值个数"), self.n)
        f2.addRow(self.log_scale)
        root.addWidget(gb2)

        gb3 = QGroupBox(tr("输出"))
        f3 = QFormLayout(gb3)
        self.out_dir = QLineEdit("sweep_results")
        f3.addRow(tr("结果目录"), self.out_dir)
        root.addWidget(gb3)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("开始扫描"))
        bb.accepted.connect(self._start)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._refresh_steps()

    # ------------------------------------------------ UI 联动
    def _refresh_steps(self):
        from ..core import i18n
        self.step_combo.clear()
        for i, s in enumerate(self.wfp.steps):
            name = s.get("component") or s.get("plugin")
            tag = tr("组件") if s["kind"] == "component" else tr("插件")
            display = i18n.display_name(name) if s["kind"] == "component" else name
            self.step_combo.addItem(f"{i + 1}. [{tag}] {display}", s.get("id"))
        self._refresh_params()

    def _refresh_params(self):
        self.param_combo.clear()
        sid = self.step_combo.currentData()
        step = next((s for s in self.wfp.steps if s.get("id") == sid), None)
        if not step:
            return
        for k, v in (step.get("params") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                self.param_combo.addItem(k, (k, float(v)))

    # ------------------------------------------------ 启动
    def _start(self):
        item = self.param_combo.currentData()
        if not item:
            QMessageBox.warning(self, tr("缺少参数"), tr("该步骤没有可扫描的数值参数"))
            return
        pname, cur = item
        lo, hi = self.lo.value(), self.hi.value()
        if lo == hi:
            QMessageBox.warning(self, tr("范围无效"), tr("起始值与终止值不能相同"))
            return
        if self.log_scale.isChecked() and (lo <= 0 or hi <= 0):
            QMessageBox.warning(self, tr("范围无效"), tr("对数扫描要求两端 > 0（或改用线性）"))
            return
        try:
            values = sweep.make_values(lo, hi, self.n.value(), self.log_scale.isChecked())
        except ValueError as e:
            QMessageBox.warning(self, tr("范围无效"), str(e))
            return
        sid = self.step_combo.currentData()
        wf = self.wfp.to_workflow(tr("参数扫描"))
        if not wf.get("grid"):
            QMessageBox.warning(self, tr("无法扫描"),
                                tr("当前工作流没有网格配置（沿用交互网格）。\n"
                                   "请先载入任意预设，再打开参数扫描。"))
            return
        self.sweep_config = {"wf": wf, "step_id": sid, "param_name": pname,
                             "values": values,
                             "out_dir": self.out_dir.text().strip() or "sweep_results"}
        self.accept()


class SweepResultWindow(QWidget):
    """扫描结果浏览窗口：表格 + 坡度面积对比 + 统计曲线 + 地形缩略图。"""

    def __init__(self, results, param_name, out_dir, log=print, parent=None):
        super().__init__(parent)   # 挂到主窗口，避免本地引用被回收
        self.setWindowFlags(Qt.Window)     # 但仍作为独立浮动窗口显示
        self.setWindowTitle(tr("参数扫描结果: {0} ({1} 组)").format(param_name, len(results)))
        self.resize(1050, 700)
        self.results = results
        self.param_name = param_name

        tabs = QTabWidget()
        # ---- 表格 ----
        table = QTableWidget(len(results), 5)
        table.setHorizontalHeaderLabels([param_name, tr("平均高程"), tr("最大高程"), tr("最小高程"), tr("起伏 (m)")])
        for r, res in enumerate(results):
            for c, v in enumerate([res["value"], res["mean"], res["max"],
                                   res["min"], res["relief"]]):
                it = QTableWidgetItem(f"{v:.5g}" if c == 0 else f"{v:.1f}")
                table.setItem(r, c, it)
        table.resizeColumnsToContents()
        tabs.addTab(table, tr("统计表"))

        # ---- 坡度-面积对比 ----
        fig = Figure(figsize=(8, 5))
        ax = fig.add_subplot(111)
        cmap = matplotlib.colormaps["viridis"]
        n = len(results)
        plotted = 0
        for i, res in enumerate(results):
            if res.get("sa"):
                a, s = res["sa"]
                ax.loglog(a, s, "-o", ms=3, lw=1.2,
                          color=cmap(i / max(1, n - 1)),
                          label=f"{param_name}={res['value']:.3g}")
                plotted += 1
        if plotted:
            ax.set_xlabel(tr("汇水面积 A (m²)"))
            ax.set_ylabel(tr("坡度 S"))
            ax.legend(fontsize=8)
            ax.set_title(tr("坡度-面积曲线对比（凹度差异一眼可见）"))
        else:
            ax.text(0.5, 0.5, tr("无坡度-面积数据（需运行含汇流步骤）"),
                    transform=ax.transAxes, ha="center", va="center", color="gray")
        fig.tight_layout()
        tabs.addTab(_FigTab(fig), tr("坡度-面积对比"))

        # ---- 统计曲线 ----
        fig2 = Figure(figsize=(8, 5))
        ax2 = fig2.add_subplot(111)
        vals = [r["value"] for r in results]
        xs = range(len(vals))
        ax2.plot(xs, [r["relief"] for r in results], "-o", label=tr("起伏 (m)"), color="#e05c5c")
        ax2.plot(xs, [r["mean"] for r in results], "-s", label="平均高程", color="#3daee9")
        ax2.set_xticks(list(xs))
        ax2.set_xticklabels([f"{v:.3g}" for v in vals], rotation=30)
        ax2.set_xlabel(param_name)
        ax2.set_ylabel("高程 (m)")
        ax2.legend()
        ax2.set_title(tr("形态指标随参数变化"))
        fig2.tight_layout()
        tabs.addTab(_FigTab(fig2), tr("统计曲线"))

        # ---- 地形缩略图 ----
        fig3 = Figure(figsize=(10, 3 + n))
        cols = min(3, n)
        rows = (n + cols - 1) // cols
        vmax = max(r["max"] for r in results)
        vmin = min(r["min"] for r in results)
        for i, res in enumerate(results):
            ax = fig3.add_subplot(rows, cols, i + 1)
            ax.imshow(res["z2d"], origin="lower", cmap="terrain", vmin=vmin, vmax=vmax)
            ax.set_title(f"{param_name}={res['value']:.3g}", fontsize=9)
            ax.set_xticks([])
            ax.set_yticks([])
        fig3.tight_layout()
        tabs.addTab(_FigTab(fig3), tr("地形缩略图"))

        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        btns = QHBoxLayout()
        b_csv = QPushButton(tr("导出统计 CSV"))
        b_csv.clicked.connect(lambda: self._export_csv(out_dir, log))
        b_png = QPushButton(tr("保存对比图组"))
        b_png.clicked.connect(lambda: self._export_pngs(out_dir, log))
        btns.addWidget(b_csv)
        btns.addWidget(b_png)
        btns.addStretch()
        lay.addLayout(btns)

    def _export_csv(self, out_dir, log):
        import os
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, f"sweep_{self.param_name}.csv")
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow([self.param_name, "mean", "max", "min", "relief"])
            for r in self.results:
                w.writerow([r["value"], r["mean"], r["max"], r["min"], r["relief"]])
        log(tr("扫描统计已导出: {0}").format(p))

    def _export_pngs(self, out_dir, log):
        os.makedirs(out_dir, exist_ok=True)
        tabs = self.findChild(QTabWidget)
        for i in range(tabs.count()):
            w = tabs.widget(i)
            fig = getattr(w, "fig", None)
            if fig is not None:
                p = os.path.join(out_dir, f"sweep_{tabs.tabText(i)}.png")
                fig.savefig(p, dpi=130, bbox_inches="tight")
                log(tr("已保存: {0}").format(p))


class _FigTab(QWidget):
    def __init__(self, fig, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(FigureCanvasQTAgg(fig))
        self.fig = fig

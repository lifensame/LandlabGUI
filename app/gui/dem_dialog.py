"""在线DEM下载对话框：地名搜索 / 手动经纬度范围 / 缩放级别 / 代理设置。"""

from __future__ import annotations

from PySide6.QtCore import Qt

from ..core.i18n import tr
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QSpinBox, QVBoxLayout)

from ..core import dem_fetch


class DemDownloadDialog(QDialog):
    """返回 {south, north, west, east, zoom, proxy, name} 配置；下载由主窗口托管。"""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("从在线地图下载真实DEM"))
        self.setMinimumWidth(520)
        self.settings = settings
        self.results: list[dict] = []
        self._worker = None

        root = QVBoxLayout(self)
        tip = QLabel(tr(
            "在全球范围内选取真实地形（数据源: SRTM/Copernicus，免密钥）。\n"
            "搜索地名后自动填入范围，也可手动输入经纬度；下载后即可进行侵蚀分析。"))
        tip.setWordWrap(True)
        root.addWidget(tip)

        # ---- 地名搜索 ----
        gb1 = QGroupBox(tr("① 按地名搜索"))
        v1 = QVBoxLayout(gb1)
        h = QHBoxLayout()
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText(
            "例: 华山 / Mount Hua / 富士山 / Grand Canyon（歧义名建议用英文）")
        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.search)
        h.addWidget(self.query_edit)
        h.addWidget(self.btn_search)
        v1.addLayout(h)
        self.result_combo = QComboBox()
        self.result_combo.setEnabled(False)
        self.result_combo.currentIndexChanged.connect(self._fill_bbox)
        self.result_combo.setMinimumHeight(24)
        v1.addWidget(self.result_combo)
        root.addWidget(gb1)

        # ---- 经纬度范围 ----
        gb2 = QGroupBox(tr("② 区域范围（可手动修改）"))
        g2 = QGridLayout(gb2)
        self.sp_south = QDoubleSpinBox()
        self.sp_north = QDoubleSpinBox()
        for sp in (self.sp_south, self.sp_north):
            sp.setRange(-90, 90)
            sp.setDecimals(5)
        self.sp_west = QDoubleSpinBox()
        self.sp_east = QDoubleSpinBox()
        for sp in (self.sp_west, self.sp_east):
            sp.setRange(-180, 180)
            sp.setDecimals(5)
        for row, (label, sp) in enumerate([(tr("南纬 (South)"), self.sp_south),
                                           (tr("北纬 (North)"), self.sp_north),
                                           (tr("西经 (West)"), self.sp_west),
                                           (tr("东经 (East)"), self.sp_east)]):
            g2.addWidget(QLabel(label), row, 0)
            g2.addWidget(sp, row, 1)
        self.sp_south.setValue(34.40)
        self.sp_north.setValue(34.55)
        self.sp_west.setValue(110.00)
        self.sp_east.setValue(110.15)      # 默认华山附近
        root.addWidget(gb2)

        # ---- 缩放与边界 ----
        gb3 = QGroupBox(tr("③ 下载设置"))
        f3 = QFormLayout(gb3)
        self.zoom = QSpinBox()
        self.zoom.setRange(9, 14)
        self.zoom.setValue(12)
        self.zoom.valueChanged.connect(self._update_info)
        f3.addRow(tr("缩放级别 (越大越精细)"), self.zoom)
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color:#9aa0a6;")
        f3.addRow(self.info_label)
        self.boundary = QComboBox()
        self.boundary.addItems(["south_open (四周封闭+南缘出水口，教程同款)",
                                "all_closed (四周封闭)"])
        f3.addRow(tr("边界条件"), self.boundary)
        self.proxy_edit = QLineEdit()
        last = str(self.settings.value("dem_proxy", "") or "")
        self.proxy_edit.setText(last)
        self.proxy_edit.setPlaceholderText("留空=系统代理；直连失败可填 http://127.0.0.1:7890")
        f3.addRow(tr("网络代理"), self.proxy_edit)
        root.addWidget(gb3)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("🌐 下载并建网格"))
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)
        self._update_info()

    # ------------------------------------------------ 交互
    def search(self):
        q = self.query_edit.text().strip()
        if not q:
            return
        self.btn_search.setEnabled(False)
        self.btn_search.setText(tr("搜索中..."))
        from app.workers.sim_worker import FuncWorker
        self._worker = FuncWorker(dem_fetch.geocode, q,
                                  proxies=self.proxy_edit.text().strip() or None)
        self._worker.sig_result.connect(self._on_search_done)
        self._worker.sig_done.connect(self._on_search_fail)
        self._worker.start()

    def _on_search_done(self, results):
        self.btn_search.setEnabled(True)
        self.btn_search.setText(tr("搜索"))
        if not results:
            return
        self.results = results
        self.result_combo.blockSignals(True)
        self.result_combo.clear()
        for r in results:
            self.result_combo.addItem(r["name"][:90])
        self.result_combo.blockSignals(False)
        self.result_combo.setEnabled(True)
        self.result_combo.setCurrentIndex(0)
        self._fill_bbox(0)

    def _on_search_fail(self, ok, msg):
        self.btn_search.setEnabled(True)
        self.btn_search.setText(tr("搜索"))
        if not ok:
            QMessageBox.warning(self, tr("搜索失败"), msg)

    def _fill_bbox(self, idx):
        if 0 <= idx < len(self.results):
            r = self.results[idx]
            self.sp_south.setValue(r["south"])
            self.sp_north.setValue(r["north"])
            self.sp_west.setValue(r["west"])
            self.sp_east.setValue(r["east"])

    def _update_info(self):
        try:
            info = dem_fetch.dem_info(self.sp_south.value(), self.sp_north.value(),
                                      self.sp_west.value(), self.sp_east.value(),
                                      self.zoom.value())
            w, h = info["nodes"]
            self.info_label.setText(tr(
                "预计网格: {0} 格 | 分辨率≈{1} m/格").format(f"{h}×{w}", f"{info['dx']:.0f}")
                + (tr("  ⚠ 过大，建议降低缩放") if w * h > 1_200_000 else ""))
        except Exception:
            self.info_label.setText("")

    def _accept(self):
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.warning(self, tr("搜索进行中"), tr("地名搜索还在后台进行，请稍候再操作"))
            return
        w, h = dem_fetch.dem_info(self.sp_south.value(), self.sp_north.value(),
                                  self.sp_west.value(), self.sp_east.value(),
                                  self.zoom.value())["nodes"]
        if w * h > 1_500_000:
            QMessageBox.warning(self, tr("区域过大"),
                                tr("预计 {0} 格超出处理能力，请缩小范围或降低缩放级别").format(f"{h}×{w}"))
            return
        self.settings.setValue("dem_proxy", self.proxy_edit.text().strip())
        self.accept()

    # ------------------------------------------------ 结果
    def config(self) -> dict:
        return {"south": self.sp_south.value(), "north": self.sp_north.value(),
                "west": self.sp_west.value(), "east": self.sp_east.value(),
                "zoom": self.zoom.value(),
                "proxy": self.proxy_edit.text().strip() or None,
                "boundary": "south_open" if self.boundary.currentIndex() == 0 else "all_closed",
                "name": self.result_combo.currentText() if self.results else tr("手动范围")}

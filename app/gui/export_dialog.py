"""独立导出对话框：随时一键导出当前网格状态（DEM + 河网）。"""

from __future__ import annotations

import os

from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLineEdit, QPushButton, QVBoxLayout)

from ..core.i18n import tr


class ExportDialog(QDialog):
    def __init__(self, parent=None, last_dir: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr("导出当前地形与河网"))
        self.setMinimumWidth(420)
        self.out_dir = last_dir or os.getcwd()

        root = QVBoxLayout(self)
        gb1 = QGroupBox("输出目录")
        h = QHBoxLayout(gb1)
        self.dir_edit = QLineEdit(self.out_dir)
        btn = QPushButton("浏览...")
        btn.clicked.connect(self._pick_dir)
        h.addWidget(self.dir_edit)
        h.addWidget(btn)
        root.addWidget(gb1)

        gb2 = QGroupBox(tr("DEM 格式"))
        f2 = QVBoxLayout(gb2)
        self.fmts = {}
        for key, label, checked in [
                ("ascii", tr("ASCII (.asc) — QGIS/ArcGIS"), True),
                ("netcdf", tr("NetCDF (.nc) — ParaView，含全部字段"), False),
                ("vtk", tr("VTK (.vtk) — ParaView 3D"), False),
                ("obj", tr("OBJ (.obj) — Blender 3D"), False),
                ("geotiff", tr("GeoTIFF (.tif) — 需 rasterio"), False)]:
            cb = QCheckBox(label)
            cb.setChecked(checked)
            self.fmts[key] = cb
            f2.addWidget(cb)
        root.addWidget(gb2)

        gb3 = QGroupBox(tr("河网水系"))
        f3 = QFormLayout(gb3)
        self.export_river = QCheckBox(tr("提取并导出河网 (GeoJSON/Shapefile/CSV)"))
        self.export_river.setChecked(True)
        f3.addRow(self.export_river)
        self.river_area = QDoubleSpinBox()
        self.river_area.setDecimals(1)
        self.river_area.setRange(0, 1e12)
        self.river_area.setValue(1e5)
        f3.addRow(tr("汇水面积阈值 (m²)"), self.river_area)
        root.addWidget(gb3)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("确定"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录", self.dir_edit.text())
        if d:
            self.dir_edit.setText(d)

    def config(self) -> dict:
        fmts = [k for k, cb in self.fmts.items() if cb.isChecked()]
        return {"dir": self.dir_edit.text().strip() or "export",
                "formats": fmts,
                "river": self.export_river.isChecked(),
                "river_min_area": float(self.river_area.value())}

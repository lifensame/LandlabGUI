"""
网格对话框：新建网格（5 种类型）或从 DEM 导入 + 初始地形 + 边界条件。
"""

from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLineEdit,
                               QPushButton, QSpinBox, QVBoxLayout, QFileDialog, QLabel)

from ..core.i18n import tr

# 每种网格的参数定义（简化的硬编码 schema，够用且直观）
_GRID_DEFS = {
    "RasterModelGrid": [
        {"name": "shape", "type": "array", "default": [80, 100], "doc": "网格行数(南北), 列数(东西)"},
        {"name": "xy_spacing", "type": "float", "default": 100.0, "doc": "分辨率 m/格"},
    ],
    "HexModelGrid": [
        {"name": "shape", "type": "array", "default": [10, 12], "doc": "[行数, 每行节点数]"},
        {"name": "spacing", "type": "float", "default": 100.0, "doc": "节点间距 m"},
    ],
    "RadialModelGrid": [
        {"name": "n_rings", "type": "int", "default": 10, "doc": "环数"},
        {"name": "nodes_in_first_ring", "type": "int", "default": 8, "doc": "第一环节点数"},
        {"name": "spacing", "type": "float", "default": 100.0, "doc": "环间距 m"},
    ],
    "FramedVoronoiGrid": [
        {"name": "shape", "type": "array", "default": [10, 12], "doc": "[行, 列]"},
        {"name": "xy_spacing", "type": "float", "default": 100.0, "doc": "平均间距 m"},
    ],
    "VoronoiDelaunayGrid": [
        {"name": "__npts__", "type": "int", "default": 400, "doc": "随机点数（自动布点）"},
        {"name": "__width__", "type": "float", "default": 10000.0, "doc": "区域宽度 m"},
        {"name": "__height__", "type": "float", "default": 8000.0, "doc": "区域高度 m"},
    ],
}


class GridDialog(QDialog):
    """返回工作流 grid/terrain/boundary 配置 dict；dem_file 非空表示导入DEM。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("新建网格 / 导入DEM"))
        self.setMinimumWidth(430)
        self.dem_file = None
        self._form_widgets = []

        root = QVBoxLayout(self)

        # ---- 网格类型 ----
        gb1 = QGroupBox(tr("网格类型"))
        f1 = QFormLayout(gb1)
        self.type_combo = QComboBox()
        self.type_combo.addItems(list(_GRID_DEFS.keys()))
        f1.addRow(tr("类型"), self.type_combo)
        self.grid_form_box = QFormLayout()
        f1.addRow(self.grid_form_box)
        root.addWidget(gb1)

        # ---- 初始地形 ----
        gb2 = QGroupBox(tr("初始地形"))
        f2 = QFormLayout(gb2)
        self.terrain_mode = QComboBox()
        self.terrain_mode.addItems(["noise", "gaussian", "flat"])
        f2.addRow(tr("模式"), self.terrain_mode)
        self.amp = QDoubleSpinBox()
        self.amp.setDecimals(2)
        self.amp.setRange(0, 1e6)
        self.amp.setValue(10.0)
        f2.addRow(tr("噪声/山峰幅度 (m)"), self.amp)
        self.slope = QDoubleSpinBox()
        self.slope.setDecimals(4)
        self.slope.setRange(0, 1.0)
        self.slope.setSingleStep(0.001)
        self.slope.setValue(0.01)
        f2.addRow(tr("整体坡度 (引导水流)"), self.slope)
        self.slope_dir = QComboBox()
        self.slope_dir.addItems(["S", "N", "E", "W"])
        f2.addRow(tr("出水口方向"), self.slope_dir)
        self.seed = QSpinBox()
        self.seed.setRange(0, 999999)
        self.seed.setValue(42)
        f2.addRow(tr("随机种子"), self.seed)
        root.addWidget(gb2)

        # ---- 边界条件 ----
        gb3 = QGroupBox(tr("边界条件"))
        f3 = QFormLayout(gb3)
        self.boundary = QComboBox()
        self.boundary.addItems([tr("south_open (教程默认: 四周封闭+南缘出水口)"),
                                tr("all_closed (四周封闭)"), tr("default (landlab默认)")])
        f3.addRow(tr("方案"), self.boundary)
        root.addWidget(gb3)

        # ---- DEM 导入 ----
        gb4 = QGroupBox(tr("或从 DEM 文件导入（覆盖上面的网格/地形设置）"))
        f4 = QHBoxLayout(gb4)
        self.dem_edit = QLineEdit()
        self.dem_edit.setPlaceholderText("选择 .asc 文件后留空...")
        btn = QPushButton(tr("浏览..."))
        btn.clicked.connect(self._pick_dem)
        f4.addWidget(self.dem_edit)
        f4.addWidget(btn)
        root.addWidget(gb4)

        self.note = QLabel("")
        root.addWidget(self.note)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self.type_combo.currentTextChanged.connect(self._rebuild_grid_form)
        self._rebuild_grid_form(self.type_combo.currentText())

    def _rebuild_grid_form(self, gtype):
        # 清空旧行
        while self.grid_form_box.count():
            self.grid_form_box.removeRow(0)
        self._form_widgets = []
        for p in _GRID_DEFS[gtype]:
            if p["type"] == "array":
                w = QLineEdit(", ".join(str(v) for v in p["default"]))
            elif p["type"] == "int":
                w = QSpinBox()
                w.setRange(-1_000_000, 1_000_000)
                w.setValue(p["default"])
            else:
                w = QLineEdit(str(p["default"]))
                w.setPlaceholderText("如 1e2")
            w.setToolTip(p.get("doc", ""))
            self.grid_form_box.addRow(p["name"], w)
            self._form_widgets.append((p, w))

    def _pick_dem(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("打开"), "",
                                              "ESRI ASCII (*.asc);;所有文件 (*)")
        if path:
            self.dem_file = path
            self.dem_edit.setText(path)

    def result_config(self) -> dict:
        """打包为工作流配置片段。"""
        cfg = {}
        gtype = self.type_combo.currentText()
        params = {}
        for p, w in self._form_widgets:
            if p["name"].startswith("__"):       # Voronoi 等特殊参数运行期展开
                continue
            if p["type"] == "array":
                params[p["name"]] = [int(float(s)) for s in str(w.text()).replace(",", " ").split()]
            elif p["type"] == "int":
                params[p["name"]] = int(w.value())
            else:
                try:
                    params[p["name"]] = float(w.text())
                except ValueError:
                    params[p["name"]] = w.text()
        if gtype == "VoronoiDelaunayGrid":
            npts = width = height = None
            for p, w in self._form_widgets:
                try:
                    v = w.value() if hasattr(w, "value") else float(w.text() or 0)
                except ValueError:
                    raise ValueError(f"参数 {p['name']} 不是有效数字")
                if p["name"] == "__npts__":
                    npts = int(v)
                elif p["name"] == "__width__":
                    width = v
                elif p["name"] == "__height__":
                    height = v
            params = {"__npts__": npts, "__width__": width, "__height__": height}
        cfg["grid"] = {"type": gtype, "params": params}
        cfg["boundary"] = {"south_open": "south_open", "all_closed": "all_closed",
                           "default": "default"}[
            ("south_open" if "south_open" in self.boundary.currentText() else
             "all_closed" if "all_closed" in self.boundary.currentText() else "default")]
        cfg["terrain"] = {"mode": self.terrain_mode.currentText(),
                          "amplitude": float(self.amp.value()),
                          "slope": float(self.slope.value()),
                          "slope_dir": self.slope_dir.currentText(),
                          "seed": int(self.seed.value())}
        dem = self.dem_edit.text().strip()
        if dem:
            cfg["grid"]["dem_file"] = dem
            cfg["terrain"] = None
        return cfg

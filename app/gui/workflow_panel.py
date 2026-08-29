"""
工作流面板：时间配置 + 步骤列表（增删/排序/编辑参数）+ 输出配置。
左侧组件树双击 -> add_step(entry)；to_workflow() 打包为引擎可执行的 dict。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
                               QWidget)

from .form_builder import ParamForm

from ..core.i18n import tr

_WHEN_LABEL = {"every_step": "每步", "once_at_start": "开始一次", "once_at_end": "结束一次"}


def _when_disp(k):
    return tr(_WHEN_LABEL.get(k, "每步"))


class StepEditDialog(QDialog):
    """编辑单个步骤：参数表单 + 执行时机。"""

    def __init__(self, step: dict, params_def: list, field_names: list, parent=None):
        super().__init__(parent)
        step_label = step.get("component") or step.get("plugin") or "?"
        from ..core import i18n
        if step.get("kind") == "component":
            step_label = i18n.display_name(step_label)
        self.setWindowTitle(tr("编辑步骤: ") + step_label)
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        self.form = ParamForm(params_def, field_names, self,
                              comp_name=step.get("component") or step.get("plugin"))
        self.form.set_values(step.get("params", {}))
        lay.addWidget(self.form)
        f = QFormLayout()
        self.when_combo = QComboBox()
        for k, zh in [(k, tr(zh)) for k, zh in _WHEN_LABEL.items()]:
            self.when_combo.addItem(tr(zh), k)
        cur = step.get("when", "every_step")
        idx = self.when_combo.findData(cur)
        self.when_combo.setCurrentIndex(idx if idx >= 0 else 0)
        f.addRow(tr("执行时机"), self.when_combo)
        lay.addLayout(f)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def result_params(self):
        return self.form.values(), self.when_combo.currentData()


class WorkflowPanel(QWidget):
    def __init__(self, workspace, registry, parent=None):
        super().__init__(parent)
        self.ws = workspace
        self.registry = registry
        self.steps: list[dict] = []
        self._seq = 0
        # 工作流级网格配置（来自预设/文件载入；交互建网格后默认沿用现有网格）
        self.grid_cfg = None
        self.terrain_cfg = None
        self.boundary_cfg = None

        root = QVBoxLayout(self)

        # ---- 网格与时间 ----
        h_top = QHBoxLayout()
        gb_g = QGroupBox(tr("网格来源"))
        fg = QVBoxLayout(gb_g)
        self.rebuild_check = QCheckBox(tr("运行时按下方配置重建网格"))
        self.rebuild_check.setToolTip(tr("勾选后每次运行都会新建网格（预设场景用）；\n"
                                      "不勾选则沿用当前网格，可反复运行累积演化。"))
        self.rebuild_check.setEnabled(False)
        fg.addWidget(self.rebuild_check)
        self.grid_desc = QLabel(tr("（尚未配置网格 —— 请 菜单[网格]->新建网格 或载入预设）"))
        self.grid_desc.setWordWrap(True)
        fg.addWidget(self.grid_desc)
        h_top.addWidget(gb_g)

        gb_t = QGroupBox(tr("时间循环"))
        ft = QFormLayout(gb_t)
        self.dt = QDoubleSpinBox()
        self.dt.setDecimals(3)
        self.dt.setRange(0.001, 1e9)
        self.dt.setValue(250.0)
        ft.addRow(tr("时间步长 dt (yr)"), self.dt)
        self.n_steps = QSpinBox()
        self.n_steps.setRange(1, 10_000_000)
        self.n_steps.setValue(100)
        ft.addRow(tr("总步数"), self.n_steps)
        self.refresh_every = QSpinBox()
        self.refresh_every.setRange(1, 100000)
        self.refresh_every.setValue(10)
        ft.addRow(tr("画面刷新间隔(步)"), self.refresh_every)
        h_top.addWidget(gb_t)
        root.addLayout(h_top)

        # ---- 输出配置 ----
        gb_o = QGroupBox(tr("运行后导出（可选）"))
        fo = QFormLayout(gb_o)
        self.do_export = QCheckBox(tr("模拟结束后自动导出"))
        fo.addRow(self.do_export)
        self.out_dir = QLineEdit("gui_results")
        fo.addRow(tr("输出目录"), self.out_dir)
        self.fmt_ascii = QCheckBox("ASCII(.asc)")
        self.fmt_ascii.setChecked(True)
        self.fmt_netcdf = QCheckBox("NetCDF(.nc)")
        self.fmt_netcdf.setChecked(True)
        self.fmt_vtk = QCheckBox("VTK(.vtk)")
        self.fmt_obj = QCheckBox("OBJ(.obj)")
        hfmt = QHBoxLayout()
        for w in (self.fmt_ascii, self.fmt_netcdf, self.fmt_vtk, self.fmt_obj):
            hfmt.addWidget(w)
        fo.addRow(tr("DEM格式"), hfmt)
        self.river_area = QDoubleSpinBox()
        self.river_area.setDecimals(1)
        self.river_area.setRange(0, 1e12)
        self.river_area.setValue(1e5)
        fo.addRow(tr("河网汇水阈值(m²)"), self.river_area)
        root.addWidget(gb_o)

        # ---- 步骤列表 ----
        gb_s = QGroupBox(tr("处理步骤（自上而下，每个时间步按顺序执行）"))
        vs = QVBoxLayout(gb_s)
        self.step_list = QListWidget()
        self.step_list.itemDoubleClicked.connect(self._edit_step)
        vs.addWidget(self.step_list)
        btns = QHBoxLayout()
        for text, fn in [(tr("编辑参数"), self._edit_step), (tr("上移"), lambda: self._move(-1)),
                         (tr("下移"), lambda: self._move(1)), (tr("删除"), self._delete_step),
                         (tr("清空"), self._clear_steps)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            btns.addWidget(b)
        vs.addLayout(btns)
        hint = QLabel(tr("双击步骤编辑参数；分析类组件自动设为\"结束一次\"；"
                         "在左侧组件库双击任意组件/插件即可添加步骤"))
        hint.setWordWrap(True)
        vs.addWidget(hint)
        root.addWidget(gb_s, stretch=1)

    # ------------------------------------------------ 网格配置
    def set_grid_config(self, grid_cfg: dict, terrain_cfg: dict | None, boundary: str | None,
                        from_dialog: bool = True):
        """记录网格配置；交互建网格(from_dialog=True)默认沿用当前网格不重建。"""
        self.grid_cfg = grid_cfg
        self.terrain_cfg = terrain_cfg
        self.boundary_cfg = boundary
        self.rebuild_check.setChecked(not from_dialog)
        self.rebuild_check.setEnabled(True)
        g = grid_cfg.get("params", {})
        desc = grid_cfg.get("type", "?")
        if grid_cfg.get("dem_file"):
            import os
            desc += f" ← DEM: {os.path.basename(grid_cfg['dem_file'])}"
        elif g:
            desc += f"  {g}"
        self.grid_desc.setText(desc)

    # ------------------------------------------------ 步骤管理
    def add_step(self, entry):
        self._seq += 1
        when = "once_at_end" if entry.is_analysis else "every_step"
        step = {"id": f"s{self._seq}", "kind": entry.kind,
                "component" if entry.kind == "component" else "plugin": entry.name,
                "params": {p["name"]: p["default"] for p in entry.params_def
                           if not p["name"].startswith("__") and p.get("default") is not None},
                "when": when}
        if entry.kind == "component":
            step["step_style"] = (entry.schema or {}).get("step_style", "run_one_step")
        self.steps.append(step)
        self._refresh_list()
        self.ws.log(tr("已添加步骤: {0} ({1})").format(entry.name, _when_disp(when)))

    def _selected_row(self) -> int:
        r = self.step_list.currentRow()
        return r if 0 <= r < len(self.steps) else -1

    def _edit_step(self, *_):
        r = self._selected_row()
        if r < 0:
            return
        step = self.steps[r]
        entry = self.registry.get(step.get("component") or step.get("plugin"))
        if entry is None:
            QMessageBox.warning(self, tr("错误"), tr("找不到该功能的定义（组件或插件可能已移除）"))
            return
        dlg = StepEditDialog(step, entry.params_def, self.ws.field_names(), self)
        if dlg.exec():
            try:
                params, when = dlg.result_params()
            except ValueError as e:
                QMessageBox.warning(self, tr("参数错误"), str(e))
                return
            step["params"] = params
            step["when"] = when
            self._refresh_list()

    def _delete_step(self):
        r = self._selected_row()
        if r >= 0:
            del self.steps[r]
            self._refresh_list()

    def _clear_steps(self):
        self.steps.clear()
        self._refresh_list()

    def _move(self, delta: int):
        r = self._selected_row()
        nr = r + delta
        if 0 <= r < len(self.steps) and 0 <= nr < len(self.steps):
            self.steps[r], self.steps[nr] = self.steps[nr], self.steps[r]
            self._refresh_list()
            self.step_list.setCurrentRow(nr)

    def _refresh_list(self):
        from ..core import i18n
        self.step_list.clear()
        for i, s in enumerate(self.steps):
            name = s.get("component") or s.get("plugin") or "?"
            tag = tr("组件") if s["kind"] == "component" else tr("插件")
            display = i18n.display_name(name) if s["kind"] == "component" else name
            item = QListWidgetItem(
                f"{i + 1}. [{tag}] {display}  —  {_when_disp(s.get('when', 'every_step'))}")
            item.setData(Qt.UserRole, name)
            self.step_list.addItem(item)

    # ------------------------------------------------ 工作流打包/装载
    def to_workflow(self, name="未命名") -> dict:
        wf = {"version": 1, "name": name,
              "time": {"dt": float(self.dt.value()), "n_steps": int(self.n_steps.value()),
                       "refresh_every": int(self.refresh_every.value()),
                       "history_every": max(1, int(self.refresh_every.value()) // 2)},
              "steps": [dict(s) for s in self.steps]}
        if self.rebuild_check.isChecked() and self.grid_cfg:
            wf["grid"] = self.grid_cfg
            if self.terrain_cfg:
                wf["terrain"] = self.terrain_cfg
            if self.boundary_cfg:
                wf["boundary"] = self.boundary_cfg
        if self.do_export.isChecked():
            wf["outputs"] = {"dir": self.out_dir.text().strip() or "gui_results",
                             "formats": [f for f, cb in
                                         [("ascii", self.fmt_ascii), ("netcdf", self.fmt_netcdf),
                                          ("vtk", self.fmt_vtk), ("obj", self.fmt_obj)]
                                         if cb.isChecked()],
                             "river_min_area": float(self.river_area.value())}
        return wf

    def load_workflow(self, wf: dict):
        t = wf.get("time", {})
        self.dt.setValue(float(t.get("dt", 250.0)))
        self.n_steps.setValue(int(t.get("n_steps", 100)))
        self.refresh_every.setValue(int(t.get("refresh_every", 10)))
        self.steps = []
        for s in wf.get("steps", []):
            step = dict(s)
            step.setdefault("id", f"s{len(self.steps) + 1}")
            self.steps.append(step)
        self._refresh_list()
        if wf.get("grid"):
            self.set_grid_config(wf["grid"], wf.get("terrain"), wf.get("boundary"),
                                 from_dialog=False)
        else:
            self.grid_cfg, self.terrain_cfg, self.boundary_cfg = None, None, None
            self.grid_desc.setText(tr("（沿用当前网格）"))
            self.rebuild_check.setChecked(False)
        out = wf.get("outputs")
        self.do_export.setChecked(bool(out))
        if out:
            self.out_dir.setText(out.get("dir", "gui_results"))
            fmts = out.get("formats", ["ascii"])
            self.fmt_ascii.setChecked("ascii" in fmts)
            self.fmt_netcdf.setChecked("netcdf" in fmts)
            self.fmt_vtk.setChecked("vtk" in fmts)
            self.fmt_obj.setChecked("obj" in fmts)
            self.river_area.setValue(float(out.get("river_min_area", 1e5)))

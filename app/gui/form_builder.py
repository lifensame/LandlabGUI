"""
动态表单：把自省引擎的 params_def 渲染成 Qt 表单，收集时还原为 Python 值。
======================================================================

支持类型:
  float / int / str(+choices) / bool / none(可留空) / field_ref(引用网格字段)
  array(逗号或JSON) / dict / json(回退)
每个参数行附带 docstring 提示（tooltip），鼠标悬停即见官方文档。
"""

from __future__ import annotations

import json

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                               QLineEdit, QPlainTextEdit, QSpinBox, QWidget)

from ..core import i18n
from ..core.i18n import tr
from ..core.i18n import tr

_TYPE_LABEL = {
    "float": "浮点", "int": "整数", "str": "文本", "bool": "开关", "none": "可留空",
    "field_ref": "字段引用", "array": "数组", "dict": "JSON对象", "json": "JSON",
}


def _ttag(t):
    return tr(_TYPE_LABEL.get(t, t))


def _fmt_default(v) -> str:
    """默认值显示文本。"""
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, (list, tuple)):
        try:
            return json.dumps(list(v))
        except Exception:
            return str(v)
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


class ParamForm(QWidget):
    """schema.params 列表 <-> 表单。comp_name 用于查找中文参数释义。"""

    def __init__(self, params_def: list, field_names: list = None, parent=None,
                 comp_name: str = None):
        super().__init__(parent)
        self.params_def = params_def or []
        self.editors = {}          # name -> (widget, getter, setter)
        form = QFormLayout(self)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        for p in self.params_def:
            name = p.get("name", "")
            ptype = p.get("type", "str")
            default = p.get("default")
            doc = p.get("doc", "") or ""
            choices = p.get("choices")

            zh = i18n.param_zh_label(comp_name, name)
            label_text = f"{name}｜{zh}" if zh else name
            type_tag = _ttag(ptype)
            tip_body = i18n.param_doc(comp_name, name, doc) if i18n.is_zh() else doc
            tooltip = f"[{type_tag}] {tip_body}" if tip_body else f"[{type_tag}]"

            if ptype == "bool":
                w = QCheckBox()
                w.setChecked(bool(default))
                w.setToolTip(tooltip)
                getter = w.isChecked
                setter = w.setChecked
            elif ptype == "int":
                w = QSpinBox()
                w.setRange(-2_000_000_000, 2_000_000_000)
                w.setValue(int(default or 0))
                w.setToolTip(tooltip)
                getter = w.value
                setter = w.setValue
            elif ptype == "float":
                w = QLineEdit(_fmt_default(default))
                w.setPlaceholderText(tr("如 1e-5（留空=用组件默认值）"))
                w.setToolTip(tooltip)
                getter = (lambda ed=w: (float(ed.text()) if ed.text().strip()
                                        not in ("", "-") else None))
                setter = (lambda val, ed=w: ed.setText(_fmt_default(float(val))))
            elif ptype in ("str", "none") and choices:
                w = QComboBox()
                w.addItems([str(c) for c in choices])
                if default is not None:
                    w.setCurrentText(str(default))
                w.setToolTip(tooltip)
                getter = w.currentText
                setter = w.setCurrentText
            elif ptype == "field_ref":
                w = QComboBox()
                w.setEditable(True)
                items = list(field_names or [])
                if default and default not in items:
                    items.insert(0, str(default))
                w.addItems(items)
                if default is not None:
                    w.setCurrentText(str(default))
                w.setToolTip(tooltip + tr("（可选当前网格已有字段，也可手输）"))
                getter = (lambda cb=w: cb.currentText() if cb.currentText().strip() else None)
                setter = w.setCurrentText
            elif ptype in ("str", "none"):
                w = QLineEdit("" if default is None else str(default))
                w.setPlaceholderText(tr("留空") if ptype == "none" or default is None else "")
                w.setToolTip(tooltip)
                getter = (lambda ed=w: ed.text() if ed.text().strip() else None) \
                    if ptype == "none" else (lambda ed=w: ed.text())
                setter = (lambda val, ed=w: ed.setText("" if val is None else str(val)))
            elif ptype in ("array", "dict", "json"):
                w = QPlainTextEdit(_fmt_default(default))
                w.setMaximumHeight(56)
                w.setToolTip(tooltip + tr("（JSON 或逗号分隔）"))
                getter = (lambda ed=w: _parse_loose(ed.toPlainText()))
                setter = (lambda val, ed=w: ed.setPlainText(_fmt_default(val)))
            else:
                w = QLineEdit(_fmt_default(default))
                w.setToolTip(tooltip + tr("（原样传给组件）"))
                getter = (lambda ed=w: ed.text())
                setter = (lambda val, ed=w: ed.setText(str(val)))

            form.addRow(label_text, w)
            self.editors[name] = (w, getter, setter)

    # ---------- 读写 ----------
    def values(self) -> dict:
        """收集为参数 dict（组件可接受的 Python 值）。

        留空的数值/文本/字段引用返回 None，并从结果中剔除 ——
        让组件用自己的默认值（关键：如 K_sp=None 表示组件内部计算，绝不能传 0）。
        """
        out = {}
        for p in self.params_def:
            name = p.get("name", "")
            if name not in self.editors:
                continue
            w, getter, _ = self.editors[name]
            try:
                v = getter()
            except ValueError:
                raise ValueError(tr("参数 {0} 的值无法解析为数字").format(name))
            ptype = p.get("type")
            if ptype in ("dict", "json") and isinstance(v, str):
                v = _parse_loose(v)
            if ptype == "array" and isinstance(v, str):
                v = _parse_loose(v)
            if v is None:
                continue          # 留空 → 不传，让组件用自己的默认值
            if ptype == "str" and v == "":
                continue          # 清空的文本同样不传（可选参数如 depression_finder 传""会报错）
            if isinstance(v, dict) and name == "__extra_kwargs__":
                out.update(v)
                continue
            out[name] = v
        return out

    def set_values(self, values: dict):
        """用 dict 填充表单（编辑已有步骤/加载预设）。"""
        for name, v in (values or {}).items():
            if name in self.editors:
                _, _, setter = self.editors[name]
                try:
                    setter(v)
                except Exception:
                    pass

    def refresh_field_names(self, field_names: list):
        """网格变化后刷新 field_ref 下拉选项。"""
        for p in self.params_def:
            if p.get("type") == "field_ref" and p.get("name") in self.editors:
                w = self.editors[p["name"]][0]
                cur = w.currentText()
                w.clear()
                w.addItems(list(field_names or []))
                if cur:
                    w.setCurrentText(cur)


def _parse_loose(text: str):
    """宽容解析：JSON 优先，失败则按逗号分隔的数字列表。"""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    parts = [s.strip() for s in text.split(",") if s.strip()]
    vals = []
    for s in parts:
        try:
            vals.append(float(s) if ("." in s or "e" in s.lower()) else int(s))
        except ValueError:
            vals.append(s)
    return vals if len(vals) > 1 else (vals[0] if vals else text)

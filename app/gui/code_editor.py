"""
代码编辑器：Python 语法高亮 + 运行 + 另存为插件。
运行时以 workspace/grid/np/plugins 为上下文在后台线程执行。
"""

from __future__ import annotations

import os
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat)
from PySide6.QtWidgets import (QHBoxLayout, QInputDialog, QLineEdit,
                               QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ..core.i18n import tr
from app.core.plugin_loader import write_plugin_template

_DEFAULT_CODE = '''# 在这里写 Python 代码，可用变量：
#   workspace / ws  —— 会话对象（ws.grid 当前网格）
#   grid            —— 当前网格（等价 ws.grid）
#   at_node         —— 网格节点字段容器（等价 grid.at_node）
#   np              —— numpy
#   plugins         —— 已加载插件字典
# 示例：把高程整体抬高 10 米
if grid is not None and "topographic__elevation" in at_node:
    at_node["topographic__elevation"] += 10.0
    print("已抬高 10 米，请点击右侧\"地形\"标签查看")
else:
    print("请先新建网格")
'''

_KEYWORDS = ("False None True and as assert async await break class continue def del elif "
             "else except finally for from global if import in is lambda nonlocal not or "
             "pass raise return try while with yield").split()


class PythonHighlighter(QSyntaxHighlighter):
    """轻量正则高亮（关键字/字符串/注释/数字）。"""

    def __init__(self, doc):
        super().__init__(doc)
        self.rules = []
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#c678dd"))
        kw_fmt.setFontWeight(QFont.Bold)
        for k in _KEYWORDS:
            self.rules.append((re.compile(rf"\b{k}\b"), kw_fmt))
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor("#98c379"))
        self.rules.append((re.compile(r'"[^"\n]*"|\'[^\'\n]*\''), str_fmt))
        com_fmt = QTextCharFormat()
        com_fmt.setForeground(QColor("#7f848e"))
        com_fmt.setFontItalic(True)
        self.rules.append((re.compile(r"#[^\n]*"), com_fmt))
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor("#d19a66"))
        self.rules.append((re.compile(r"\b\d+\.?\d*(e[+-]?\d+)?\b", re.I), num_fmt))

    def highlightBlock(self, text):
        for rx, fmt in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


class CodeEditorPanel(QWidget):
    def __init__(self, workspace, registry, on_snapshot, log, parent=None):
        super().__init__(parent)
        self.ws = workspace
        self.registry = registry
        self.on_snapshot = on_snapshot      # 主线程回调(np.ndarray)
        self.log = log
        self.worker = None
        self.busy_check = lambda: False     # 主窗口注入：模拟运行中禁止片段执行

        lay = QVBoxLayout(self)
        btns = QHBoxLayout()
        self.btn_run = QPushButton(tr("▶ 运行代码 (Ctrl+R)"))
        self.btn_run.clicked.connect(self.run_code)
        btn_save = QPushButton(tr("另存为插件..."))
        btn_save.clicked.connect(self.save_as_plugin)
        btn_tpl = QPushButton(tr("插入模板"))
        btn_tpl.clicked.connect(lambda: self.editor.setPlainText(_DEFAULT_CODE))
        btns.addWidget(self.btn_run)
        btns.addWidget(btn_save)
        btns.addWidget(btn_tpl)
        btns.addStretch()
        lay.addLayout(btns)

        from PySide6.QtWidgets import QPlainTextEdit
        from PySide6.QtGui import QKeySequence, QShortcut
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.setPlainText(_DEFAULT_CODE)
        self._hl = PythonHighlighter(self.editor.document())
        lay.addWidget(self.editor)

        QShortcut(QKeySequence("Ctrl+R"), self.editor, activated=self.run_code)

    def run_code(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self, tr("提示"), tr("上一次代码还在运行中"))
            return
        if self.busy_check():
            QMessageBox.warning(self, tr("忙碌"), tr("模拟正在运行中，代码片段会与它竞争同一网格，请先停止模拟"))
            return
        from app.workers.sim_worker import CodeWorker
        code = self.editor.toPlainText()
        self.log(tr("[代码] 开始执行片段..."))
        self.worker = CodeWorker(code, self.ws, self.registry.plugins)
        self.worker.sig_log.connect(self.log)
        self.worker.sig_done.connect(self._on_done)
        self.worker.sig_snapshot.connect(self.on_snapshot)
        self.worker.start()

    def _on_done(self, ok: bool, msg: str):
        self.log(tr("[代码] {0}").format(msg) if ok else tr("[代码] 出错: {0}").format(msg))

    def save_as_plugin(self):
        name, ok = QInputDialog.getText(self, tr("另存为插件"), tr("插件功能名称："),
                                        text=tr("我的自定义功能"))
        if not ok or not name.strip():
            return
        from app.core.plugin_loader import plugins_dir
        safe = re.sub(r"[^\w\-]", "_", name.strip()) or "plugin"
        path = os.path.join(plugins_dir(), f"{safe}.py")
        code = self.editor.toPlainText()
        try:
            write_plugin_template(path, name.strip(), code)
        except OSError as e:
            QMessageBox.warning(self, tr("保存失败"), str(e))
            return
        self.log(tr("[插件] 已保存: {0}，请在菜单'插件->重载插件'后使用").format(path))
        QMessageBox.information(self, tr("已保存"),
                                tr("已保存:\n{0}\n\n请通过菜单 插件->重载插件 加载。").format(path))

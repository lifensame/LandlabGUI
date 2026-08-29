"""控制台面板：只读日志窗口（带行数上限，防内存膨胀）。"""

from PySide6.QtWidgets import (QPlainTextEdit, QWidget, QVBoxLayout)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

_MAX_BLOCKS = 5000


class ConsolePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(_MAX_BLOCKS)
        self.text.setFont(QFont("Consolas", 9))
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self.text)

    def log(self, msg: str):
        self.text.appendPlainText(str(msg))

    def clear(self):
        self.text.clear()

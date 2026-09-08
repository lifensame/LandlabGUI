"""控制台面板：只读日志窗口（带行数上限，防内存膨胀）。"""

from PySide6.QtWidgets import (QPlainTextEdit, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

from ..core.i18n import tr

_MAX_BLOCKS = 5000


class ConsolePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        hbar = QHBoxLayout()
        hbar.setContentsMargins(4, 2, 4, 2)
        lbl = QLabel("🖥️ " + tr("系统运行日志"))
        lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600;")
        btn_clear = QPushButton(tr("清空日志"))
        btn_clear.setFixedHeight(22)
        btn_clear.setStyleSheet("""
            QPushButton {
                background: #212530;
                color: #8b949e;
                border: 1px solid #2b303d;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #2b303d;
                color: #e6edf3;
            }
        """)
        btn_clear.clicked.connect(self.clear)
        hbar.addWidget(lbl)
        hbar.addStretch()
        hbar.addWidget(btn_clear)
        lay.addLayout(hbar)

        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(_MAX_BLOCKS)
        self.text.setFont(QFont("Consolas", 9))
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setStyleSheet("""
            QPlainTextEdit {
                background: #111317;
                color: #cbd5e1;
                border: 1px solid #232731;
                border-radius: 6px;
                padding: 6px;
                selection-background-color: #1d3b5e;
            }
        """)
        lay.addWidget(self.text)

    def log(self, msg: str):
        self.text.appendPlainText(str(msg))

    def clear(self):
        self.text.clear()

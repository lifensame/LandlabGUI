"""
深色主题：QSS 样式表 + matplotlib 深色配色。
main.py 启动时调用 apply(app) 一次即可。
"""

from __future__ import annotations

import matplotlib

# 与 QSS 协调的深色配色
BG        = "#232629"   # 窗口背景
BG_ALT    = "#2a2e32"   # 面板/输入框
BG_LIGHT  = "#31363b"   # 悬停/按钮
BORDER    = "#3d4349"
TEXT      = "#d8d9da"
TEXT_DIM  = "#9aa0a6"
ACCENT    = "#3daee9"   # 高亮蓝
SEL       = "#3d5a75"

DARK_QSS = f"""
QMainWindow, QDialog, QWidget {{ background: {BG}; color: {TEXT}; font-size: 12px; }}
QMenuBar {{ background: {BG_ALT}; color: {TEXT}; }}
QMenuBar::item:selected {{ background: {SEL}; }}
QMenu {{ background: {BG_ALT}; color: {TEXT}; border: 1px solid {BORDER}; }}
QMenu::item:selected {{ background: {SEL}; }}
QToolBar {{ background: {BG_ALT}; border: none; spacing: 4px; padding: 3px; }}
QToolButton {{ background: transparent; color: {TEXT}; border: 1px solid transparent;
              border-radius: 4px; padding: 4px 8px; }}
QToolButton:hover {{ background: {BG_LIGHT}; border-color: {ACCENT}; }}
QPushButton {{ background: {BG_LIGHT}; color: {TEXT}; border: 1px solid {BORDER};
              border-radius: 4px; padding: 5px 14px; }}
QPushButton:hover {{ border-color: {ACCENT}; background: #3a4046; }}
QPushButton:pressed {{ background: {SEL}; }}
QPushButton:disabled {{ color: {TEXT_DIM}; border-color: {BORDER}; background: {BG_ALT}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
  background: #1b1e20; color: {TEXT}; border: 1px solid {BORDER}; border-radius: 4px; padding: 3px; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox {{ background: {BG_LIGHT}; color: {TEXT}; border: 1px solid {BORDER};
            border-radius: 4px; padding: 3px 8px; }}
QComboBox QAbstractItemView {{ background: {BG_ALT}; color: {TEXT};
    selection-background-color: {SEL}; }}
QTreeWidget, QListWidget, QListView, QTableWidget {{
  background: #1e2124; color: {TEXT}; border: 1px solid {BORDER};
  alternate-background-color: #22262a; }}
QTreeWidget::item:selected, QListWidget::item:selected {{
  background: {SEL}; color: white; }}
QHeaderView::section {{ background: {BG_ALT}; color: {TEXT}; border: none;
  border-right: 1px solid {BORDER}; padding: 4px; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 6px; margin-top: 10px;
  color: {TEXT_DIM}; font-weight: bold; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 4px; }}
QTabBar::tab {{ background: {BG_ALT}; color: {TEXT_DIM}; padding: 6px 16px;
  border-top-left-radius: 4px; border-top-right-radius: 4px; }}
QTabBar::tab:selected {{ background: {BG_LIGHT}; color: white;
  border-bottom: 2px solid {ACCENT}; }}
QDockWidget {{ color: {TEXT}; titlebar-close-icon: none; }}
QDockWidget::title {{ background: {BG_ALT}; padding: 5px 10px; }}
QStatusBar {{ background: {BG_ALT}; color: {TEXT_DIM}; }}
QProgressBar {{ background: #1b1e20; border: 1px solid {BORDER}; border-radius: 4px;
  color: {TEXT}; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QToolTip {{ background: #111417; color: {TEXT}; border: 1px solid {ACCENT}; padding: 4px; }}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar:horizontal {{ background: {BG}; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QCheckBox {{ color: {TEXT}; spacing: 6px; }}
QLabel {{ color: {TEXT}; background: transparent; }}
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:hover {{ background: {ACCENT}; }}
"""


def apply(app):
    """应用深色主题到 QApplication。"""
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
    matplotlib.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor": BG_ALT,
        "savefig.facecolor": BG,
        "axes.edgecolor": BORDER,
        "axes.labelcolor": TEXT,
        "xtick.color": TEXT_DIM,
        "ytick.color": TEXT_DIM,
        "text.color": TEXT,
        "grid.color": "#3a4046",
        "font.sans-serif": ["Microsoft YaHei", "SimHei"],
        "axes.unicode_minus": False,
    })

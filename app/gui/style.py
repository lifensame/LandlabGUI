"""
深色主题：现代 Studio Dark QSS 样式表 + matplotlib 深度协调配色。
main.py 启动时调用 apply(app) 一次即可。
"""

from __future__ import annotations

import matplotlib

# =====================================================================
# 现代科学工作室深色调色板 (Studio Dark Palette - Slate & Zinc)
# =====================================================================
BG_ROOT      = "#13151a"   # 窗口最底层暗空背景
BG_PANEL     = "#1a1d24"   # 工作区、Docks、画布面板底色
BG_CARD      = "#212530"   # 分组容器卡片、对话框底色
BG_LIGHT     = "#282d39"   # 按钮默认底色、菜单悬停
BG_HOVER     = "#323846"   # 悬停强调
BG_INPUT     = "#15171e"   # 输入框、列表内部底色

BORDER       = "#2b303d"   # 极细边框
BORDER_LIGHT = "#383f50"   # 高亮边框、控件边缘
BORDER_FOCUS = "#3b82f6"   # 科技蓝焦点呼吸框

TEXT         = "#e6edf3"   # 主要文本（高对比净白）
TEXT_MUTED   = "#8b949e"   # 次要文本、参数标签、说明文字
TEXT_DIM     = "#646c7a"   # 极弱辅助文字

ACCENT       = "#3b82f6"   # 科技蓝（主选区、链接）
ACCENT_LIGHT = "#60a5fa"
ACCENT_GREEN = "#10b981"   # 翡翠绿（运行按钮、成功）
ACCENT_RED   = "#f43f5e"   # 珊瑚红（停止按钮、删除）
ACCENT_AMBER = "#f59e0b"   # 琥珀黄（告警、提示）
SEL          = "#1d3b5e"   # 柔和选中背景

DARK_QSS = f"""
/* 全局基础设置 */
QMainWindow, QDialog, QWidget {{
    background: {BG_ROOT};
    color: {TEXT};
    font-family: "Microsoft YaHei UI", "Segoe UI", -apple-system, sans-serif;
    font-size: 12px;
}}

/* 菜单栏与上下文菜单 */
QMenuBar {{
    background: {BG_PANEL};
    color: {TEXT};
    border-bottom: 1px solid {BORDER};
    padding: 2px 6px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {BG_LIGHT};
    color: #ffffff;
}}
QMenu {{
    background: #1d212a;
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: #ffffff;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER};
    margin: 4px 8px;
}}

/* 工具栏 */
QToolBar {{
    background: {BG_PANEL};
    border-bottom: 1px solid {BORDER};
    spacing: 6px;
    padding: 4px 8px;
}}
QToolButton {{
    background: transparent;
    color: {TEXT};
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 10px;
    font-weight: 500;
}}
QToolButton:hover {{
    background: {BG_LIGHT};
    border-color: {BORDER_LIGHT};
    color: #ffffff;
}}
QToolButton:pressed {{
    background: {SEL};
}}

/* 核心通用按钮 */
QPushButton {{
    background: {BG_LIGHT};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {BG_HOVER};
    border-color: {ACCENT};
    color: #ffffff;
}}
QPushButton:pressed {{
    background: {SEL};
}}
QPushButton:disabled {{
    background: {BG_PANEL};
    color: {TEXT_DIM};
    border-color: {BORDER};
}}

/* 输入框、下拉框、微调器 */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background: {BG_INPUT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {BORDER_FOCUS};
    background: #181b24;
}}
QComboBox {{
    background: {BG_LIGHT};
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 5px 10px;
}}
QComboBox:hover {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: #1d212a;
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    selection-background-color: {ACCENT};
    padding: 4px;
}}

/* 树列表与表格 */
QTreeWidget, QListWidget, QListView, QTableWidget {{
    background: {BG_INPUT};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
    outline: none;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 5px 8px;
    margin: 1px 0;
    border-radius: 4px;
}}
QTreeWidget::item:hover, QListWidget::item:hover {{
    background: {BG_CARD};
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {SEL};
    color: #ffffff;
}}
QHeaderView::section {{
    background: {BG_PANEL};
    color: {TEXT_MUTED};
    border: none;
    border-right: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    padding: 6px;
    font-weight: 600;
}}

/* 现代化卡片式 GroupBox (去穿透式老旧框) */
QGroupBox {{
    background: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
    color: {TEXT_MUTED};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 1px;
    padding: 2px 8px;
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 4px;
    color: {TEXT};
    font-size: 11px;
    font-weight: 600;
}}

/* 现代化胶囊 Tab 页 */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BG_PANEL};
    border-radius: 6px;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 7px 18px;
    border-radius: 6px 6px 0 0;
    margin: 2px 2px 0 2px;
    font-weight: 500;
}}
QTabBar::tab:hover {{
    background: {BG_LIGHT};
    color: {TEXT};
}}
QTabBar::tab:selected {{
    background: {BG_PANEL};
    color: #ffffff;
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}

/* 停靠面板 */
QDockWidget {{
    color: {TEXT};
    titlebar-close-icon: none;
}}
QDockWidget::title {{
    background: {BG_PANEL};
    padding: 7px 10px;
    border-bottom: 1px solid {BORDER};
    font-weight: 600;
}}

/* 状态栏与进度条 */
QStatusBar {{
    background: #101216;
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
    padding: 2px;
}}
QProgressBar {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 5px;
    color: #ffffff;
    text-align: center;
    font-size: 11px;
    height: 14px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 {ACCENT});
    border-radius: 4px;
}}

/* 浮动提示 */
QToolTip {{
    background: #181b22;
    color: {TEXT};
    border: 1px solid {BORDER_LIGHT};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* 极简现代化滚动条 */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: #373e4d;
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0px;
}}
QScrollBar::handle:horizontal {{
    background: #373e4d;
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}

/* 辅助控件 */
QCheckBox {{
    color: {TEXT};
    spacing: 7px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {BORDER_LIGHT};
    border-radius: 4px;
    background: {BG_INPUT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QLabel {{
    color: {TEXT};
    background: transparent;
}}
QSplitter::handle {{
    background: {BG_ROOT};
}}
QSplitter::handle:hover {{
    background: {ACCENT};
}}
"""


def apply(app):
    """应用深色主题到 QApplication。"""
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
    matplotlib.rcParams.update({
        "figure.facecolor": BG_PANEL,
        "axes.facecolor": BG_INPUT,
        "savefig.facecolor": BG_PANEL,
        "axes.edgecolor": BORDER,
        "axes.labelcolor": TEXT_MUTED,
        "xtick.color": TEXT_MUTED,
        "ytick.color": TEXT_MUTED,
        "text.color": TEXT,
        "grid.color": "#242834",
        "font.sans-serif": ["Microsoft YaHei UI", "Segoe UI", "SimHei"],
        "axes.unicode_minus": False,
    })

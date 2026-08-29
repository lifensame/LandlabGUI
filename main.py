"""
Landlab 地貌模拟工作台 —— 启动入口
==================================
运行:  python main.py
"""

import os
import sys

# 保证 app 包可导入（无论从哪里启动）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    # Windows 控制台中文输出保护
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("Landlab 地貌模拟工作台")
    app.setFont(QFont("Microsoft YaHei", 9))

    from app.gui.style import apply
    apply(app)                       # 深色主题（QSS + matplotlib 配色）

    from app.gui.main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

"""Landlab GUI 应用包。

分层结构：
- app.core  引擎层：自省、注册表、执行引擎、工作区、插件、导出（零 Qt 依赖）
- app.gui   界面层：PySide6 窗口与面板
- app.workers  后台线程：模拟执行、代码片段执行
"""

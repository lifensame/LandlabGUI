# Landlab 地貌模拟工作台 / Landlab Geomorphology Workbench

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Landlab](https://img.shields.io/badge/built%20on-landlab%202.x-blueviolet)
![Python](https://img.shields.io/badge/python-3.10%2B-informational)
![GUI](https://img.shields.io/badge/GUI-PySide6-green)

为 [Landlab](https://landlab.csdms.io/) 2.x 打造的可视化桌面工作台（PySide6，中文/English 双语界面）。
A visual desktop workbench for the [Landlab](https://landlab.csdms.io/) landscape evolution framework — no coding required: build workflows from 87 components, run real-time simulations, analyze and export GIS data.

> 社区开源项目，非 Landlab 官方出品 / Community project, not affiliated with the Landlab team.

不用写代码即可搭建地貌演化模拟工作流：**建网格 → 组合过程组件 → 时间循环 → 可视化 → 导出 GIS/3D 数据**。

## 核心特性

- **全量 87 个 landlab 组件**：自省引擎自动读取每个组件的构造参数、docstring 文档和
  字段依赖（单位/位置/必填），动态生成参数表单 —— 不需要为任何组件手写界面
- **场景预设**：内置教程全部 6 个场景（快速测试 / 稳态河道 / 青藏场景 / 硬岩 / 软岩 /
  非线性侵蚀），双击载入、一键运行
- **科研分析三件套**：
  - 参数扫描批量实验：一个参数取 N 个值批量模拟，坡度-面积曲线对比 + 统计表 + 地形缩略图，可导出 CSV/图组
  - 运行历史：每次运行自动存快照，任意两次 A/B 对比，可回滚到某快照继续演化
  - 一键实验报告：Markdown + 图组（地形/坡度-面积/剖面/统计表），作业/论文素材直接用
- **可视化交互**：六视图（地形/面积/坡度-面积/剖面/历史/3D）；缩放平移工具栏；
  点击查任意点数值；地形图上取两点画任意方向剖面；演化动画导出 GIF/MP4
- **插件系统**：`plugins/` 文件夹放一个装饰器函数即可扩展新功能（如自定义抬升模式），
  支持热重载；详见 [docs/插件开发指南.md](docs/插件开发指南.md)
- **代码编辑器**：GUI 内写 Python 片段直接运行（共享当前网格上下文），可另存为插件
- **后台运行**：模拟/导出/扫描全在独立线程，随时可停止
- **体验**：深色主题；布局与最近文件记忆（下次启动自动恢复）；
  新手引导向导（首次启动自动弹出，帮助菜单可重看）；独立导出菜单（随时导出当前状态）
- **DEM 导入**：ESRI ASCII (.asc)；**在线真实DEM**：按地名（如"Mount Hua"、富士山）
  或经纬度范围下载全球真实地形（SRTM/Copernicus，免密钥，可配代理），下载即建网格；
  **导出**：ASCII / NetCDF / VTK(ParaView) / OBJ(Blender)
  / 河网 GeoJSON+Shapefile+CSV（QGIS）

## 快速开始

```powershell
# 依赖（本机已装 Python 3.14 + landlab 2.11 可直接跳过）
pip install -r requirements.txt

# 启动
python main.py
```

三步上手：
1. 菜单 **网格 → 新建网格**（默认参数即可），或左侧双击载入预设
2. 左侧组件库双击添加步骤（推荐顺序：`构造抬升(4种模式)` → `PriorityFloodFlowRouter` →
   `FastscapeEroder` → `LinearDiffuser`），双击步骤可编辑参数（悬停见官方文档）
3. 点工具栏 **▶ 运行**（F5），右侧看实时地形，底部控制台看日志

## 工作流 JSON

`文件 → 保存/打开工作流` 读写 JSON，结构示例见 `presets/快速测试.json`。
预设就是工作流 JSON，放在 `presets/` 目录即出现在 GUI 左下列表。

## 目录结构

```
landlab_gui/
├── main.py               # 入口
├── app/
│   ├── core/             # 引擎层（零 Qt 依赖，可独立测试）
│   │   ├── introspection.py   # 87 组件自省引擎 + schema 缓存
│   │   ├── registry.py        # 内置组件+插件统一目录
│   │   ├── engine.py          # 工作流执行引擎（时间循环/自动建字段/边界）
│   │   ├── workspace.py       # 会话状态（网格/字段/历史）
│   │   ├── plugin_loader.py   # 插件扫描与热重载
│   │   ├── exporter.py        # DEM/河网导出（移植自教程 output_module.py）
│   │   ├── dem_fetch.py       # 在线真实DEM（地名搜索+高程瓦片下载）
│   │   ├── sweep.py           # 参数扫描批量实验
│   │   ├── report.py          # 一键实验报告
│   │   ├── animate.py         # 演化动画导出
│   │   ├── plots.py           # 纯 matplotlib 绘图（画布/报告共用）
│   │   └── api.py             # @plugin 装饰器
│   ├── gui/              # PySide6 界面层
│   │   ├── main_window.py     # 主窗口（菜单/工具栏/四区布局）
│   │   ├── workflow_panel.py  # 工作流编辑
│   │   ├── form_builder.py    # schema→动态参数表单
│   │   ├── grid_dialog.py     # 网格对话框（5 种网格+DEM导入）
│   │   ├── canvas_panel.py    # matplotlib 画布（5 个视图）
│   │   ├── code_editor.py     # 代码编辑器（高亮/运行/另存为插件）
│   │   └── console.py         # 控制台
│   └── workers/sim_worker.py  # QThread 后台执行
├── plugins/              # ← 你的插件放这里
├── presets/              # 场景预设 JSON
├── tests/                # 单元测试 (python tests/test_introspection.py)
└── docs/                 # 插件开发指南
```

## 打包 exe

```powershell
pip install pyinstaller
python build_exe.py
# 产物在 dist/LandlabGUI/，双击 LandlabGUI.exe
```

## 测试

```powershell
python tests/test_introspection.py
```

## 教程对应关系

| 教程文件 | GUI 中的对应 |
|---|---|
| `parameters.py` 的 6 个 PRESETS | 左下"场景预设"列表 |
| `erosion_model.py` 抬升模式 | 插件"构造抬升(4种模式)" |
| `output_module.py` 导出 | `app/core/exporter.py`（运行后导出 / 菜单） |
| 教程 02 的 DEM 导入 | 菜单"网格→新建网格→从DEM导入" |

"""
界面语言（i18n）：中文/English 全界面双语。
==============================================
- 组件目录: COMPONENT_ZH / PARAM_ZH (zh_catalog)，87 组件中文名+说明+常用参数释义
- 界面文字: tr() 查表，键=中文原文，英文模式返回英文；缺翻译回退中文
- 语言状态存 QSettings("LandlabGUI","main") 的 "lang"；切换后重启应用完全生效
"""

from __future__ import annotations

from .zh_catalog import COMPONENT_ZH, PARAM_ZH

_lang = "zh"          # "zh" | "en"


def set_lang(lang: str):
    global _lang
    _lang = "zh" if lang == "zh" else "en"


def get_lang() -> str:
    return _lang


def is_zh() -> bool:
    return _lang == "zh"


# ============================================================ 界面文字表
# 键 = 中文原文；en = 英文显示。翻译缺失时回退中文原文。
_STR_EN = {
    # ---- 通用 ----
    "确定": "OK", "取消": "Cancel", "关闭": "Close", "保存": "Save", "打开": "Open",
    "删除": "Delete", "清空": "Clear", "上移": "Move Up", "下移": "Move Down",
    "浏览...": "Browse...", "搜索": "Search", "提示": "Info", "错误": "Error",
    "忙碌": "Busy", "就绪 ": "Ready ", " 运行中... ": " Running... ",
    "（可选）": "(optional)", "组件": "Component", "插件": "Plugin",
    "每步": "Every step", "开始一次": "Once at start", "结束一次": "Once at end",
    # ---- 主窗口 ----
    "Landlab 地貌模拟工作台": "Landlab Geomorphology Workbench",
    "网格(&G)": "&Grid",
    "新建网格 / 导入DEM...": "New Grid / Import DEM...",
    "🌐 从在线地图下载真实DEM...": "🌐 Download Real DEM (online)...",
    "按地名或经纬度范围下载全球真实地形（SRTM/Copernicus，免密钥）":
        "Download real global terrain by place name or lat/lon box (SRTM/Copernicus, key-free)",
    "导出当前地形...": "Export Current Terrain...",
    "网格信息": "Grid Info",
    "文件(&F)": "&File",
    "打开工作流...": "Open Workflow...",
    "保存工作流...": "Save Workflow...",
    "最近打开": "Recent Files",
    "运行(&R)": "&Run",
    "▶ 运行工作流": "▶ Run Workflow",
    "■ 停止": "■ Stop",
    "工具(&T)": "&Tools",
    "参数扫描批量实验...": "Parameter Sweep...",
    "生成实验报告...": "Generate Experiment Report...",
    "导出演化动画...": "Export Evolution Animation...",
    "插件(&P)": "&Plugins",
    "重载插件": "Reload Plugins",
    "打开插件文件夹": "Open Plugins Folder",
    "帮助(&H)": "&Help",
    "新手引导": "Getting Started",
    "插件开发指南": "Plugin Developer Guide",
    "关于": "About",
    "🌐 组件显示语言 / Language": "🌐 Component language / 语言",
    "中文（组件中文名+中文说明）": "中文 (Chinese names & docs)",
    "组件与预设": "Components & Presets",
    "控制台": "Console",
    "工作流": "Workflow",
    "代码编辑器": "Code Editor",
    "组件库": "Components",
    "场景预设": "Presets",
    "运行历史": "Run History",
    "组件库（双击添加到工作流）": "Components (double-click to add to workflow)",
    "🔍 搜索组件 / 插件": "🔍 Search components / plugins",
    "双击载入预设，点运行即跑（自动建网格）":
        "Double-click to load a preset; ▶ Run builds the grid automatically",
    "Landlab 地貌模拟工作台已启动（深色主题）":
        "Landlab Workbench started (dark theme)",
    "快速上手: 双击左下【快速测试】预设 → 点 ▶ 运行；不熟悉可看 菜单[帮助→新手引导]":
        "Quick start: double-click the 'Quick Test' preset → ▶ Run; see Help → Getting Started",
    "已切换到中文显示": "Switched to Chinese display",
    "Switched to English display": "已切换到英文显示",
    "（参数表单的中文提示将在下次打开时生效）":
        "(Parameter form hints take effect when reopened)",
    "有任务正在后台运行，请等待完成": "A background task is running; please wait",
    "有任务正在后台运行，请等待或停止": "A background task is running; wait or stop it",
    "有任务仍在后台运行，确定退出？": "A background task is still running. Quit anyway?",
    "正在运行": "Running",
    "缺少网格": "No Grid",
    "请先 菜单[网格]->新建网格，或载入预设（运行时自动建网格）":
        "Create a grid first (menu Grid), or load a preset (grid is built on run)",
    "尚无网格": "No grid yet",
    "请先创建网格": "Create a grid first",
    "请先运行一次模拟": "Run a simulation first",
    "请至少选择一种格式或勾选河网导出": "Pick at least one format or enable river export",
    "尚未配置网格 —— 请 菜单[网格]->新建网格 或载入预设":
        "No grid configured — menu Grid→New Grid, or load a preset",
    "（沿用当前网格）": "(use current grid)",
    "运行结束": "Run finished", "运行失败": "Run failed",
    "已请求停止，等待当前步完成...": "Stop requested; waiting for current step...",
    "导出完成": "Export finished", "导出失败": "Export failed",
    "网格 {0} 节点": "Grid: {0} nodes",
    "真实DEM {1}×{0} 格": "Real DEM {1}×{0} cells",
    # ---- 工作流面板 ----
    "网格来源": "Grid Source",
    "运行时按下方配置重建网格": "Rebuild the grid from the config below on each run",
    "勾选后每次运行都会新建网格（预设场景用）；不勾选则沿用当前网格，可反复运行累积演化。":
        "Each run creates a fresh grid (for presets). Unchecked: reuse the current grid so runs accumulate evolution.",
    "时间循环": "Time Loop",
    "时间步长 dt (yr)": "Time step dt (yr)",
    "总步数": "Number of steps",
    "画面刷新间隔(步)": "Refresh interval (steps)",
    "运行后导出（可选）": "Export after run (optional)",
    "模拟结束后自动导出": "Auto export after the simulation ends",
    "输出目录": "Output directory",
    "DEM格式": "DEM formats",
    "ASCII(.asc)": "ASCII (.asc)",
    "NetCDF(.nc)": "NetCDF (.nc)",
    "VTK(.vtk)": "VTK (.vtk)",
    "OBJ(.obj)": "OBJ (.obj)",
    "GeoTIFF(.tif) — 需 rasterio": "GeoTIFF (.tif) — needs rasterio",
    "河网汇水阈值(m²)": "River threshold drainage area (m²)",
    "处理步骤（自上而下，每个时间步按顺序执行）":
        "Steps (executed top-to-bottom every time step)",
    "双击步骤编辑参数；分析类组件自动设为\"结束一次\"；在左侧组件库双击任意组件/插件即可添加步骤":
        "Double-click a step to edit. Analysis components default to 'once at end'. Double-click any component/plugin on the left to add a step.",
    "编辑参数": "Edit Parameters",
    "已添加步骤: {0} ({1})": "Step added: {0} ({1})",
    "找不到该功能的定义（组件或插件可能已移除）":
        "Definition not found (component/plugin may have been removed)",
    # ---- 表单 ----
    "浮点": "float", "整数": "int", "文本": "text", "开关": "toggle",
    "可留空": "optional", "字段引用": "field ref", "数组": "array",
    "JSON对象": "JSON object", "JSON": "JSON",
    "如 1e-5（留空=用组件默认值）": "e.g. 1e-5 (leave empty = component default)",
    "留空": "leave empty",
    "（可选当前网格已有字段，也可手输）": " (pick an existing grid field, or type one)",
    "（JSON 或逗号分隔）": " (JSON or comma-separated)",
    "（原样传给组件）": " (passed to the component as-is)",
    "参数 {0} 的值无法解析为数字": "Value of '{0}' is not a valid number",
    "参数错误": "Invalid Parameter",
    # ---- 网格对话框 ----
    "新建网格 / 导入DEM": "New Grid / Import DEM",
    "网格类型": "Grid Type",
    "类型": "Type",
    "网格行数(南北), 列数(东西)": "rows (N-S), cols (E-W)",
    "分辨率 m/格": "cell size (m)",
    "[行数, 每行节点数]": "[rows, nodes per row]",
    "节点间距 m": "node spacing (m)",
    "环数": "number of rings",
    "第一环节点数": "nodes in first ring",
    "环间距 m": "ring spacing (m)",
    "[行, 列]": "[rows, cols]",
    "平均间距 m": "mean spacing (m)",
    "随机点数（自动布点）": "random points (auto placed)",
    "区域宽度 m": "domain width (m)",
    "区域高度 m": "domain height (m)",
    "初始地形": "Initial Terrain",
    "模式": "Mode",
    "噪声/山峰幅度 (m)": "Noise/peak amplitude (m)",
    "整体坡度 (引导水流)": "Initial slope (drives drainage)",
    "出水口方向": "Outlet direction",
    "随机种子": "Random seed",
    "边界条件": "Boundary Conditions",
    "方案": "Scheme",
    "south_open (教程默认: 四周封闭+南缘出水口)":
        "south_open (closed edges + south outlet, tutorial default)",
    "all_closed (四周封闭)": "all_closed (all edges closed)",
    "default (landlab默认)": "default (landlab default)",
    "或从 DEM 文件导入（覆盖上面的网格/地形设置）":
        "Or import a DEM file (overrides grid/terrain above)",
    "选择 .asc 文件后留空...": "pick a .asc file...",
    # ---- 导出对话框 ----
    "导出当前地形与河网": "Export Current Terrain & River Network",
    "输出目录（DEM与河网）": "Output directory",
    "DEM 格式": "DEM Formats",
    "ASCII (.asc) — QGIS/ArcGIS": "ASCII (.asc) — QGIS/ArcGIS",
    "NetCDF (.nc) — ParaView，含全部字段": "NetCDF (.nc) — ParaView, all fields",
    "VTK (.vtk) — ParaView 3D": "VTK (.vtk) — ParaView 3D",
    "OBJ (.obj) — Blender 3D": "OBJ (.obj) — Blender 3D",
    "GeoTIFF (.tif) — 需 rasterio": "GeoTIFF (.tif) — needs rasterio",
    "河网水系": "River Network",
    "提取并导出河网 (GeoJSON/Shapefile/CSV)":
        "Extract & export river network (GeoJSON/Shapefile/CSV)",
    "汇水面积阈值 (m²)": "Drainage-area threshold (m²)",
    "未选择": "Nothing Selected",
    "后台导出到 {0} ...": "Exporting in background to {0} ...",
    # ---- 在线DEM ----
    "从在线地图下载真实DEM": "Download Real DEM (Online Map)",
    "在全球范围内选取真实地形（数据源: SRTM/Copernicus，免密钥）。\n搜索地名后自动填入范围，也可手动输入经纬度；下载后即可进行侵蚀分析。":
        "Pick real terrain worldwide (source: SRTM/Copernicus, key-free).\nSearch a place name to fill the box, or type lat/lon manually; then run erosion analysis on it.",
    "① 按地名搜索": "① Search by place name",
    "例: 华山 / Mount Hua / 富士山 / Grand Canyon（歧义名建议用英文）":
        "e.g. Mount Hua / Fuji / Grand Canyon (use English for ambiguous names)",
    "搜索中...": "Searching...",
    "② 区域范围（可手动修改）": "② Region (editable)",
    "南纬 (South)": "South lat",
    "北纬 (North)": "North lat",
    "西经 (West)": "West lon",
    "东经 (East)": "East lon",
    "③ 下载设置": "③ Download Settings",
    "缩放级别 (越大越精细)": "Zoom level (higher = finer)",
    "边界条件": "Boundary Conditions",
    "网络代理": "Network proxy",
    "留空=系统代理；直连失败可填 http://127.0.0.1:7890":
        "empty = system proxy; if direct fails try http://127.0.0.1:7890",
    "🌐 下载并建网格": "🌐 Download & Build Grid",
    "预计网格: {0} 格 | 分辨率≈{1} m/格": "Grid: {0} cells | ≈{1} m/cell",
    "  ⚠ 过大，建议降低缩放": "  ⚠ too large; lower the zoom",
    "区域过大": "Region Too Large",
    "预计 {0} 格超出处理能力，请缩小范围或降低缩放级别":
        "{0} cells exceeds capacity; shrink the region or lower the zoom",
    "搜索进行中": "Search in Progress",
    "地名搜索还在后台进行，请稍候再操作": "Place-name search is still running; try again shortly",
    "搜索失败": "Search Failed",
    "手动范围": "manual box",
    "开始下载在线DEM: {0} ...": "Downloading DEM: {0} ...",
    "DEM下载失败": "DEM Download Failed",
    "在线DEM建网格出错": "Online DEM grid error",
    "真实地形已就绪！推荐工作流: 构造抬升(可选) → PriorityFloodFlowRouter → FastscapeEroder → LinearDiffuser，点 ▶ 运行即可模拟河流切割真实山脉":
        "Real terrain ready! Suggested steps: tectonic uplift (optional) → PriorityFloodFlowRouter → FastscapeEroder → LinearDiffuser; hit ▶ Run to carve real mountains",
    # ---- 参数扫描 ----
    "参数扫描批量实验": "Parameter Sweep",
    "原理: 载入预设（或含网格配置的工作流）后，固定其他条件，\n仅让一个参数在范围内取值，逐一完整模拟并对比结果。\n建议先用小网格+少步数试跑一遍，再放大正式扫描。":
        "How it works: load a preset (any workflow with a grid config), vary ONE parameter across a range, run a full simulation per value and compare.\nTip: try a small grid / few steps first.",
    "扫描目标": "Sweep Target",
    "目标步骤": "Target step",
    "目标参数": "Target parameter",
    "取值范围": "Value Range",
    "起始值": "Start",
    "终止值": "End",
    "取值个数": "Count",
    "对数等比（适合 K_sp 等跨数量级参数）":
        "Logarithmic (for cross-decade params like K_sp)",
    "对数扫描要求参数值 > 0": "Log sweep requires values > 0",
    "输出": "Output",
    "结果目录": "Results directory",
    "开始扫描": "Start Sweep",
    "缺少参数": "No Parameter",
    "该步骤没有可扫描的数值参数": "This step has no numeric parameter to sweep",
    "范围无效": "Invalid Range",
    "起始值与终止值不能相同": "Start and end cannot be equal",
    "对数扫描要求两端 > 0（或改用线性）": "Log sweep requires both ends > 0 (or use linear)",
    "无法扫描": "Cannot Sweep",
    "当前工作流没有网格配置（沿用交互网格）。\n请先载入任意预设，再打开参数扫描。":
        "The workflow has no grid config (uses the interactive grid).\nLoad any preset first, then open the sweep.",
    "正在扫描...": "Sweeping...",
    "扫描完成": "Sweep finished", "扫描失败": "Sweep failed",
    "参数扫描中... ": "Parameter sweep... ",
    "参数扫描完成: {0}": "Sweep finished: {0}",
    "参数扫描失败: {0}": "Sweep failed: {0}",
    "统计表": "Statistics",
    "坡度-面积对比": "Slope-Area Comparison",
    "统计曲线": "Stat Curves",
    "地形缩略图": "Terrain Thumbnails",
    "平均高程": "Mean elev.", "最大高程": "Max elev.", "最小高程": "Min elev.",
    "起伏 (m)": "Relief (m)",
    "无坡度-面积数据（需运行含汇流步骤）":
        "No slope-area data (needs a flow-routing step)",
    "坡度-面积曲线对比（凹度差异一眼可见）":
        "Slope-area curves (concavity differences at a glance)",
    "形态指标随参数变化": "Morphometrics vs parameter",
    "导出统计 CSV": "Export CSV",
    "保存对比图组": "Save Figures",
    "扫描统计已导出: {0}": "Sweep stats exported: {0}",
    "已保存: {0}": "Saved: {0}",
    "扫描在第 {0}/{1} 组前被取消": "Sweep cancelled before group {0}/{1}",
    "扫描完成: {0} 共 {1} 组": "Sweep done: {0}, {1} groups",
    "参数扫描要求工作流包含网格配置（载入预设后即可扫描）；当前工作流沿用交互网格，无法复现建网格":
        "Sweep needs a workflow with grid config (load a preset); the current workflow reuses the interactive grid and cannot rebuild it",
    "找不到步骤 {0}": "Step {0} not found",
    "参数 {0} 不是数值，无法扫描": "'{0}' is not numeric; cannot sweep",
    "--- 扫描 {0}/{1}: {2} = {3} ---": "--- sweep {0}/{1}: {2} = {3} ---",
    # ---- 运行历史 ----
    "A/B 对比": "A/B Compare",
    "回滚到此快照": "Rollback to Snapshot",
    "每次运行结束自动记录；选中两条可A/B对比，选中一条可回滚":
        "Auto-recorded after each run; select two to compare, one to rollback",
    "请按住 Ctrl 选中恰好两条快照": "Select exactly two snapshots (Ctrl+click)",
    "请选中一条快照": "Select one snapshot",
    "无法回滚": "Cannot Rollback",
    "该快照没有网格配置（交互建的网格），无法重建。\n提示：载入预设运行后即可回滚。":
        "This snapshot has no grid config (interactive grid) and cannot be rebuilt.\nTip: rollback works after running a preset.",
    "已恢复该时刻的地形。\n注意：组件内部状态会重新实例化，直接点运行即可继续演化。":
        "Terrain restored. Note: component states are re-instantiated; hit Run to continue evolution.",
    "回滚成功": "Rolled Back",
    "回滚失败": "Rollback Failed",
    "已回滚到快照: {0}（可继续点运行演化）": "Rolled back to: {0} (hit Run to continue)",
    "终点高程均值 {0}m": "final mean {0} m",
    "两次运行网格不同，无法逐点求差": "Different grids — cannot diff pointwise",
    # ---- 代码编辑器 ----
    "▶ 运行代码 (Ctrl+R)": "▶ Run Code (Ctrl+R)",
    "另存为插件...": "Save as Plugin...",
    "插入模板": "Insert Template",
    "插件功能名称：": "Plugin name:",
    "我的自定义功能": "My custom feature",
    "保存失败": "Save Failed",
    "已保存": "Saved",
    "已保存:\n{0}\n\n请通过菜单 插件->重载插件 加载。":
        "Saved:\n{0}\n\nUse Plugins → Reload Plugins to load it.",
    "[插件] 已保存: {0}，请在菜单'插件->重载插件'后使用":
        "[plugin] saved: {0} — use Plugins→Reload Plugins",
    "[代码] 开始执行片段...": "[code] running snippet...",
    "[代码] {0}": "[code] {0}",
    "[代码] 出错: {0}": "[code] error: {0}",
    "上一次代码还在运行中": "Previous snippet is still running",
    "模拟正在运行中，代码片段会与它竞争同一网格，请先停止模拟":
        "The simulation is running; a snippet would race on the same grid. Stop it first.",
    # ---- 画布 ----
    "地形": "Terrain", "面积": "Area", "坡度-面积": "Slope-Area",
    "剖面": "Profile", "历史": "History", "3D地形": "3D Terrain",
    "地形高程 (m)": "Terrain elevation (m)",
    "汇水面积 log10(m²)": "Drainage area log10(m²)",
    "沿程距离 (m)": "Distance (m)", "高程 (m)": "Elevation (m)",
    "演化历史": "Evolution history", "步数": "Steps", "X (m)": "X (m)", "Y (m)": "Y (m)",
    "📏 取点剖面": "📏 Pick Profile",
    "勾选后在地形图上点两个点，即画出任意方向的地形剖面":
        "Check, then click two points on the terrain map to draw an arbitrary-direction profile",
    "点击第 1 个点...": "Click the first point...",
    "已选 A({0},{1})，点击第 2 个点...": "A({0},{1}) set; click the second point...",
    "剖面已画出（黄线），共 {0} 个采样点": "Profile drawn (yellow), {0} samples",
    "剖面{n}: A-B": "Profile {n}: A-B",
    "💡 点击地形/面积图可查看该点数值；工具栏可缩放平移":
        "💡 Click the terrain/area map to inspect values; toolbar zooms/pans",
    "运行含汇流组件后显示\n(阈值 A>1e3 m²)":
        "Shown after a flow-routing step\n(threshold A>1e3 m²)",
    "运行含汇流的组件后显示\n(最长河道纵剖面)":
        "Shown after flow routing\n(longest channel profile)",
    "运行模拟后显示": "Shown after a run",
    "无有效数据": "No valid data",
    "该网格类型暂不支持二维显示": "2D view unsupported for this grid type",
    "该网格类型暂不支持3D显示": "3D view unsupported for this grid type",
    "平均高程平均": "mean elevation",
    "节点 {0}  ({1}, {2})": "Node {0}  ({1}, {2})",
    "📍 ": "📍 ",
    # ---- 向导 ----
    "欢迎使用 Landlab 地貌模拟工作台 🌏":
        "Welcome to the Landlab Workbench 🌏",
    "这是一个可视化的地貌演化模拟器：不用写代码，点选组件就能\n搭建\"抬升→汇流→侵蚀→扩散\"的工作流并实时看到山脉长出来。\n\n本向导用 4 步带你走完基本流程。":
        "A visual landscape-evolution simulator: no coding needed — pick components\nto build an 'uplift → routing → erosion → diffusion' workflow and watch mountains grow.\n\nThis wizard walks you through the basics in 4 steps.",
    "第 1 步 · 建立网格": "Step 1 · Create a Grid",
    "菜单【网格 → 新建网格】。\n\n· 默认参数即可（80×100 格、100m 分辨率）\n· 或选\"从DEM导入\"加载真实地形 (.asc)\n· 边界条件建议保持默认（四周封闭+南缘出水口，教程同款）":
        "Menu【Grid → New Grid】.\n\n· Defaults are fine (80×100 cells, 100 m spacing)\n· Or import a real DEM (.asc)\n· Keep the default boundary (closed edges + south outlet)",
    "第 2 步 · 添加过程组件": "Step 2 · Add Process Components",
    "在左侧【组件库】双击任意组件即可加入工作流，推荐入门组合：\n\n  1. 构造抬升(4种模式)   —— 每步抬升（插件）\n  2. PriorityFloodFlowRouter —— 计算水流路径\n  3. FastscapeEroder        —— 河道下切\n  4. LinearDiffuser         —— 坡面扩散\n\n双击步骤列表中的条目可改参数（鼠标悬停看官方文档）。\n想偷懒？直接双击左下角【快速测试】预设，全部自动配好。":
        "Double-click components in the left library to add them. Suggested starter set:\n\n  1. Tectonic uplift (4 modes)  — per-step uplift (plugin)\n  2. PriorityFloodFlowRouter — flow routing\n  3. FastscapeEroder        — channel incision\n  4. LinearDiffuser         — hillslope diffusion\n\nDouble-click a step to edit parameters (hover for docs).\nShortcut: double-click the 'Quick Test' preset — fully preconfigured.",
    "第 3 步 · 运行并观察": "Step 3 · Run & Watch",
    "点工具栏【▶ 运行工作流】(F5)。\n\n· 右侧画布实时刷新：地形 / 汇水面积 / 坡度-面积 / 剖面 / 3D\n· 地形图上可缩放平移、点击查值、\"取点剖面\"画任意方向剖面\n· 底部控制台显示全部日志；随时可【■ 停止】":
        "Hit【▶ Run Workflow】(F5).\n\n· Right canvas live-updates: terrain / area / slope-area / profile / 3D\n· Zoom, pan, click-to-inspect, and pick two points for a profile\n· Console shows all logs; ■ Stop anytime",
    "第 4 步 · 分析与导出": "Step 4 · Analyse & Export",
    "科研三件套都在菜单里：\n\n· 【工具 → 参数扫描实验】批量跑参数对比（论文级图表）\n· 【工具 → 生成实验报告】一键产出 Markdown+图组\n· 【工具 → 导出当前地形】asc/nc/vtk/obj + 河网 GIS 数据\n· 左侧【运行历史】可 A/B 对比与回滚\n\n准备就绪，点击\"完成\"开始你的第一次模拟！":
        "Research toolkit in the menus:\n\n· Tools → Parameter Sweep (publication-grade comparison charts)\n· Tools → Generate Report (Markdown + figures in one click)\n· Tools → Export Terrain (asc/nc/vtk/obj + river GIS data)\n· Run History for A/B compare & rollback\n\nReady? Click Finish and run your first simulation!",
    "上一步": "Back", "下一步": "Next", "完成 🎉": "Finish 🎉",
    # ---- 控制台/日志（引擎与插件） ----
    "=== 开始运行工作流: {0} ===": "=== Run workflow: {0} ===",
    "步骤: 启动前 {0} | 循环 {1} | 结束 {2} | dt={3} x {4} 步":
        "Steps: pre {0} | loop {1} | post {2} | dt={3} × {4}",
    "用户中断于第 {0}/{1} 步": "Interrupted at step {0}/{1}",
    "=== 运行完成 ===": "=== Run complete ===",
    "最终地形: 平均 {0} m, 最大 {1} m": "Final terrain: mean {0} m, max {1} m",
    "运行出错": "Run error",
    "新网格: {0}, 节点数 {1}": "New grid: {0}, {1} nodes",
    "网格已建立: {0} {1}": "Grid created: {0} {1}",
    "边界: 四周封闭": "Boundary: all closed",
    "边界: 四周封闭 + 南缘开放出水口（教程默认）":
        "Boundary: closed edges + south outlet (tutorial default)",
    "初始地形: {0}, 幅度={1}, 坡度={2} 方向={3}":
        "Initial terrain: {0}, amp={1}, slope={2}, dir={3}",
    "自动创建字段: {0} (at={1}, dtype={2})":
        "Auto-created field: {0} (at={1}, dtype={2})",
    "实例化组件 {0} (id={1})": "Instantiated {0} (id={1})",
    "分析完成: {0}.{1}()": "Analysis done: {0}.{1}()",
    "分析完成: {0}.run_one_step()": "Analysis done: {0}.run_one_step()",
    "分析 {0}.{1}() 失败: {2}": "Analysis {0}.{1}() failed: {2}",
    "分析 {0} 运行失败: {1}": "Analysis {0} failed: {1}",
    "分析组件 {0} 无可用计算方法，已实例化（输出字段可直接查看）":
        "{0} has no calc method; instantiated (check output fields)",
    "DEM 已导入: {0} ({1} 节点)": "DEM imported: {0} ({1} nodes)",
    "导出到: {0}": "Export to: {0}",
    "导出完成! 文件在: {0}": "Export finished! Files in: {0}",
    "[插件] 已加载 {0}": "[plugin] loaded {0}",
    "[插件] 加载失败 {0}": "[plugin] failed to load {0}",
    "[插件] 共加载 {0} 个自定义功能": "[plugin] {0} custom feature(s) loaded",
    "[插件] 重名覆盖: {0} ({1})": "[plugin] duplicate name overrides: {0} ({1})",
    "组件库: {0} 个 landlab 组件 | 自定义插件: {1} 个":
        "Library: {0} landlab components | plugins: {1}",
    "=== 启动工作流: {0} ({1} 个步骤) ===": "=== Start workflow: {0} ({1} steps) ===",
    "工作流共 {0} 个步骤": "Workflow has {0} steps",
    "运行结束: {0}": "Run finished: {0}",
    "运行失败: {0}": "Run failed: {0}",
    "工作流已保存: {0}": "Workflow saved: {0}",
    "工作流已载入: {0}": "Workflow loaded: {0}",
    "已载入预设: {0} —— {1}": "Preset loaded: {0} — {1}",
    "点 ▶ 运行 即可（预设会自动建网格）": "Hit ▶ Run (the preset builds its grid automatically)",
    "插件已重载: 共 {0} 个自定义功能": "Plugins reloaded: {0} custom feature(s)",
    "打开失败": "Open Failed",
    "建网格失败": "Grid Creation Failed",
    "正在生成实验报告...": "Generating report...",
    "实验报告已生成: {0}（含 {1} 张图）": "Report generated: {0} ({1} figures)",
    "正在生成动画（{0} 帧）...": "Generating animation ({0} frames)...",
    "还没有动画帧：请先运行一次模拟": "No frames yet: run a simulation first",
    "还没有可用的动画帧（请先运行一次模拟并保持画面刷新≥1次）":
        "No animation frames (run a simulation with at least one refresh)",
    "未找到 ffmpeg，无法导出 MP4；请改用 .gif": "ffmpeg not found: use .gif instead of MP4",
    "尚无网格，无法生成报告": "No grid: cannot generate a report",
    "语言将在重启后完全生效，现在重启吗？":
        "The language fully applies after a restart. Restart now?",
    "重启应用": "Restart",
    "插件已重载: 共 {0} 个自定义功能": "Plugins reloaded: {0} custom feature(s)",
    "组件库: {0} 个 landlab 组件, {1} 个自定义插件":
        "Library: {0} landlab components, {1} plugins",
}

# 分类名英文
_CATEGORY_EN = {
    "水流与汇流": "Flow Routing", "洼地处理": "Depressions",
    "河道侵蚀与沉积": "Channel Erosion", "坡面过程": "Hillslope",
    "风化与土壤": "Weathering & Soil", "水文与气候": "Hydrology & Climate",
    "滑坡与块体运动": "Landslides", "构造与地质": "Tectonics & Geology",
    "生态与扰动": "Ecosystem", "海岸与海洋": "Coastal & Marine",
    "河网泥沙输运": "Network Sediment", "示踪与浓度": "Tracers",
    "泥沙粒径初始化": "Bed Parcel Init", "地形分析": "Terrain Analysis",
    "其他": "Other",
}


def tr(s: str) -> str:
    """界面文字翻译：英文模式查表，缺翻译回退中文原文。"""
    if is_zh():
        return s
    return _STR_EN.get(s) or s


def tr_cat(cat: str) -> str:
    if is_zh():
        return cat
    return _CATEGORY_EN.get(cat, cat)


def restart_command() -> list:
    """返回重启应用的命令行（dev: python main.py；打包: exe 自身）。"""
    import os
    import sys
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "main.py")]


# ============================================================ 组件目录
def display_name(comp: str) -> str:
    """组件显示名：中文模式返回 中文名(英文)，否则英文原名。"""
    if not is_zh():
        return comp
    zh = COMPONENT_ZH.get(comp, {}).get("name")
    return f"{zh} ({comp})" if zh else comp


def short_name(comp: str) -> str:
    return display_name(comp)


def doc(comp: str, english_doc: str = "") -> str:
    """组件说明文案。"""
    if not is_zh():
        return english_doc or COMPONENT_ZH.get(comp, {}).get("doc", "")
    zh = COMPONENT_ZH.get(comp, {}).get("doc")
    return zh or english_doc or ""


def param_doc(comp: str, pname: str, english_doc: str = "") -> str:
    """参数提示文案：优先中文释义，回退英文 docstring。"""
    if is_zh():
        zh = PARAM_ZH.get(comp, {}).get(pname)
        if zh:
            return zh
    return english_doc


def param_zh_label(comp: str, pname: str) -> str | None:
    """参数的中文短释义（用于表单标签后缀），无翻译返回 None。"""
    if not is_zh():
        return None
    return PARAM_ZH.get(comp, {}).get(pname)

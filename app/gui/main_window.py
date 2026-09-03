"""
主窗口：左侧[组件库/预设/运行历史] | 中间[工作流+代码编辑] | 右侧[六视图画布] | 底部控制台。
线程模型：模拟/导出/扫描/动画均在 QThread 中跑，绘图只在主线程。
"""

from __future__ import annotations

import json
import os
import traceback

import numpy as np
from PySide6.QtCore import QProcess, QSettings, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMenu,
                               QMessageBox, QProgressBar, QSplitter, QTabWidget,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ..core.engine import Engine
from ..core.plugin_loader import app_root as _app_root, plugins_dir
from ..core.registry import Registry
from ..core.workspace import Workspace
from ..workers.sim_worker import AnimWorker, FuncWorker, SimWorker, StopFlag
from .canvas_panel import CanvasPanel
from .code_editor import CodeEditorPanel
from .console import ConsolePanel
from .export_dialog import ExportDialog
from .grid_dialog import GridDialog
from .history_panel import HistoryPanel
from .workflow_panel import WorkflowPanel
from ..core.i18n import tr, tr_cat

APP_ROOT = _app_root()
PRESET_DIR = os.path.join(APP_ROOT, "presets")
ORG, APP_NAME = "LandlabGUI", "main"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(tr("Landlab 地貌模拟工作台"))
        self.resize(1500, 900)
        self.settings = QSettings(ORG, APP_NAME)
        from ..core import i18n
        i18n.set_lang(str(self.settings.value("lang", "zh") or "zh"))

        # ---- 核心对象 ----
        self.ws = Workspace()
        self._boot_queue: list[str] = []
        self.registry = Registry(APP_ROOT, log=self._boot_log)
        self.worker: SimWorker | None = None
        self.func_worker: FuncWorker | None = None
        self.anim_worker: AnimWorker | None = None
        self.sweep_worker = None
        self._frames: list = []           # 动画帧 [(z2d, vmin, vmax, title)]
        self._frame_vlims = [None, None]  # 全程稳定的色标范围
        self._frame_bytes = 0             # 帧内存占用（float32 字节数）
        self.recent_files: list[str] = []

        # ---- 面板 ----
        self.console = ConsolePanel()
        self.canvas = CanvasPanel()
        self.workflow_panel = WorkflowPanel(self.ws, self.registry)
        self.editor = CodeEditorPanel(self.ws, self.registry,
                                      on_snapshot=self._on_snapshot, log=self.log)
        self.editor.busy_check = self._busy
        self.history_panel = HistoryPanel(self)
        # 工作流面板顶部的大运行/停止按钮
        self.workflow_panel.btn_run_big.clicked.connect(self.run_workflow)
        self.workflow_panel.btn_stop_big.clicked.connect(self.stop_workflow)

        self._build_left_panel()
        self._build_layout()
        self._build_actions()
        self._restore_settings()

        self.ws.log_fn = self.log
        for m in self._boot_queue:
            self.console.log(m)
        self._boot_queue.clear()
        self.log(tr("Landlab 地貌模拟工作台已启动（深色主题）"))
        self.log(tr("组件库: {0} 个 landlab 组件, {1} 个自定义插件").format(len(self.registry.schemas), len(self.registry.plugins)))
        self.log(tr("快速上手: 双击左下【快速测试】预设 → 点 ▶ 运行；不熟悉可看 菜单[帮助→新手引导]"))

        if not self.settings.value("wizard_seen", False, bool):
            self.settings.setValue("wizard_seen", True)
            from .wizard import WelcomeWizard
            WelcomeWizard(self).exec()

    # ================================================== 日志
    def _boot_log(self, msg: str):
        if hasattr(self, "console"):
            self.console.log(str(msg))
        else:
            self._boot_queue.append(str(msg))

    def log(self, msg: str):
        self.console.log(msg)

    # ================================================== 左侧面板（三标签）
    def _build_left_panel(self):
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        # -- 组件库 --
        w1 = QWidget()
        v1 = QVBoxLayout(w1)
        v1.setContentsMargins(4, 4, 4, 4)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("🔍 搜索组件 / 插件"))
        self.search.textChanged.connect(self._filter_tree)
        v1.addWidget(self.search)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel(tr("组件库（双击添加到工作流）"))
        self.tree.itemDoubleClicked.connect(self._on_tree_double)
        v1.addWidget(self.tree)
        tabs.addTab(w1, tr("组件库"))
        self._fill_tree("")

        # -- 场景预设 --
        w2 = QWidget()
        v2 = QVBoxLayout(w2)
        v2.setContentsMargins(4, 4, 4, 4)
        tip = QLabel(tr("双击载入预设，点运行即跑（自动建网格）"))
        tip.setWordWrap(True)
        v2.addWidget(tip)
        self.preset_list = QListWidget()
        self.preset_list.itemDoubleClicked.connect(self._load_preset)
        v2.addWidget(self.preset_list)
        tabs.addTab(w2, tr("场景预设"))
        self._load_preset_files()

        # -- 运行历史 --
        tabs.addTab(self.history_panel, tr("运行历史"))

        dock = QDockWidget(tr("组件与预设"), self)
        dock.setWidget(tabs)
        dock.setFeatures(QDockWidget.DockWidgetMovable)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def _fill_tree(self, filter_text: str):
        from ..core import i18n
        self.tree.clear()
        f = (filter_text or "").strip().lower()
        for cat in self.registry.categories():
            entries = self.registry.entries_in(cat)
            if f:
                entries = [e for e in entries
                           if f in e.name.lower() or f in (e.doc or "").lower()
                           or f in i18n.display_name(e.name).lower()]
            if not entries:
                continue
            cat_item = QTreeWidgetItem([f"{tr_cat(cat)} ({len(entries)})"])
            for e in entries:
                it = QTreeWidgetItem([("🔌 " if e.kind == "plugin" else "")
                                      + i18n.display_name(e.name)])
                it.setData(0, Qt.UserRole, e.name)
                tip = i18n.doc(e.name, e.doc or "")
                if i18n.is_zh():
                    tip = f"英文原名: {e.name}\n\n{tip}" if tip else f"英文原名: {e.name}"
                it.setToolTip(0, tip[:600] if tip else "")
                cat_item.addChild(it)
            self.tree.addTopLevelItem(cat_item)
        self.tree.expandAll()

    def _filter_tree(self, text):
        self._fill_tree(text)

    def _load_preset_files(self):
        self.presets = {}
        os.makedirs(PRESET_DIR, exist_ok=True)
        for fn in sorted(os.listdir(PRESET_DIR)):
            if not fn.endswith(".json"):
                continue
            path = os.path.join(PRESET_DIR, fn)
            try:
                with open(path, "r", encoding="utf-8") as fp:
                    wf = json.load(fp)
                name = wf.get("name", fn[:-5])
                self.presets[name] = wf
                item = QListWidgetItem(name)
                item.setToolTip(wf.get("doc", ""))
                self.preset_list.addItem(item)
            except Exception as e:
                self._boot_log(f"预设加载失败 {fn}: {e}")

    # ================================================== 布局/动作
    def _build_layout(self):
        center_tabs = QTabWidget()
        center_tabs.addTab(self.workflow_panel, tr("工作流"))
        center_tabs.addTab(self.editor, tr("代码编辑器"))

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(center_tabs)
        splitter.addWidget(self.canvas)
        splitter.setSizes([680, 720])
        self.setCentralWidget(splitter)

        dock = QDockWidget(tr("控制台"), self)
        dock.setWidget(self.console)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        dock.setMinimumHeight(120)

    def _build_actions(self):
        # ---- 网格菜单 ----
        m_grid = self.menuBar().addMenu(tr("网格(&G)"))
        act_new = QAction(tr("新建网格 / 导入DEM..."), self)
        act_new.triggered.connect(self.new_grid)
        m_grid.addAction(act_new)
        act_dem = QAction(tr("🌐 从在线地图下载真实DEM..."), self)
        act_dem.setToolTip(tr("按地名或经纬度范围下载全球真实地形（SRTM/Copernicus，免密钥）"))
        act_dem.triggered.connect(self.download_dem_dialog)
        m_grid.addAction(act_dem)
        act_export = QAction(tr("导出当前地形..."), self)
        act_export.triggered.connect(self.export_current)
        m_grid.addAction(act_export)
        act_info = QAction(tr("网格信息"), self)
        act_info.triggered.connect(self.show_grid_info)
        m_grid.addAction(act_info)

        # ---- 文件菜单 ----
        m_file = self.menuBar().addMenu(tr("文件(&F)"))
        act_open = QAction(tr("打开工作流..."), self)
        act_open.triggered.connect(self.open_workflow)
        act_save = QAction(tr("保存工作流..."), self)
        act_save.triggered.connect(self.save_workflow)
        m_file.addAction(act_open)
        m_file.addAction(act_save)
        self.m_recent = m_file.addMenu(tr("最近打开"))
        self._rebuild_recent_menu()

        # ---- 运行菜单 ----
        m_run = self.menuBar().addMenu(tr("运行(&R)"))
        self.act_start = QAction(tr("▶ 运行工作流"), self)
        self.act_start.setShortcut(QKeySequence("F5"))
        self.act_start.triggered.connect(self.run_workflow)
        self.act_stop = QAction(tr("■ 停止"), self)
        self.act_stop.setEnabled(False)
        self.act_stop.triggered.connect(self.stop_workflow)
        m_run.addAction(self.act_start)
        m_run.addAction(self.act_stop)

        # ---- 工具菜单 ----
        m_tools = self.menuBar().addMenu(tr("工具(&T)"))
        act_sweep = QAction(tr("参数扫描批量实验..."), self)
        act_sweep.triggered.connect(self.open_sweep)
        m_tools.addAction(act_sweep)
        act_report = QAction(tr("生成实验报告..."), self)
        act_report.triggered.connect(self.generate_report)
        m_tools.addAction(act_report)
        self.act_anim = QAction(tr("导出演化动画..."), self)
        self.act_anim.setEnabled(False)
        self.act_anim.triggered.connect(self.export_animation)
        m_tools.addAction(self.act_anim)
        m_tools.addSeparator()
        m_tools.addAction(act_export)

        # ---- 插件菜单 ----
        m_plug = self.menuBar().addMenu(tr("插件(&P)"))
        act_reload = QAction(tr("重载插件"), self)
        act_reload.triggered.connect(self.reload_plugins)
        act_dir = QAction(tr("打开插件文件夹"), self)
        act_dir.triggered.connect(self.open_plugin_dir)
        m_plug.addAction(act_reload)
        m_plug.addAction(act_dir)

        # ---- 帮助菜单 ----
        m_help = self.menuBar().addMenu(tr("帮助(&H)"))
        act_wiz = QAction(tr("新手引导"), self)
        act_wiz.triggered.connect(lambda: self._show_wizard())
        m_help.addAction(act_wiz)
        act_doc = QAction(tr("插件开发指南"), self)
        act_doc.triggered.connect(self._open_plugin_doc)
        m_help.addAction(act_doc)
        act_about = QAction(tr("关于"), self)
        act_about.triggered.connect(lambda: QMessageBox.about(
            self, tr("关于"),
            "<b>Landlab Geomorphology Workbench</b><br>" + tr("Landlab 地貌模拟工作台") +
            "<br><br>87 components · plugins · parameter sweep · reports<br>"
            "PySide6 · Landlab 2.x"))
        m_help.addAction(act_about)

        # ---- 语言切换（组件名/说明 中文 <-> English）----
        m_lang = m_help.addMenu(tr("🌐 组件显示语言 / Language"))
        from ..core import i18n
        self.act_lang_zh = QAction(tr("中文（组件中文名+中文说明）"), self, checkable=True)
        self.act_lang_en = QAction("English (original names & docs)", self, checkable=True)
        self.act_lang_zh.triggered.connect(lambda: self.switch_language("zh"))
        self.act_lang_en.triggered.connect(lambda: self.switch_language("en"))
        grp_actions = (self.act_lang_zh, self.act_lang_en)
        for a in grp_actions:
            m_lang.addAction(a)
        self._sync_lang_actions()

        # ---- 工具栏 ----
        tb = self.addToolBar(tr("主工具栏"))
        for act in (act_new, self.act_start, self.act_stop, act_export, act_sweep,
                    act_report, act_reload):
            tb.addAction(act)

        self.status_label = QLabel(" " + tr("就绪 ").strip() + " " + tr("｜ F5=运行  ■=停止  "))
        self.statusBar().addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(280)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)

        # 快照节流：模拟高频快照信号合并到 ≥300ms 一次绘制，
        # 防止刷新淹没主线程（界面卡顿根源）
        self._pending_z = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(300)
        self._refresh_timer.timeout.connect(self._do_canvas_refresh)

    # ================================================== 设置记忆
    def _restore_settings(self):
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        state = self.settings.value("windowState")
        if state is not None and self.settings.value("winstate_ver", 0, int) == 2:
            self.restoreState(state)
        rf = self.settings.value("recent_files", []) or []
        if isinstance(rf, str):          # QSettings 单条目时可能返回纯字符串
            rf = [rf]
        self.recent_files = [str(p) for p in rf if p]
        self._rebuild_recent_menu()

    def closeEvent(self, ev):
        workers = [self.worker, self.func_worker, self.anim_worker,
                   getattr(self, "sweep_worker", None)]
        if any(w is not None and w.isRunning() for w in workers):
            r = QMessageBox.question(self, tr("正在运行"), tr("有任务仍在后台运行，确定退出？"),
                                     QMessageBox.Yes | QMessageBox.No)
            if r != QMessageBox.Yes:
                ev.ignore()
                return
            for w in workers:
                if w is not None and w.isRunning() and hasattr(w, "stop"):
                    w.stop()
            for w in workers:
                if w is not None:
                    w.wait(5000)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("winstate_ver", 2)
        self.settings.setValue("recent_files", self.recent_files)
        super().closeEvent(ev)

    # ================================================== 最近文件
    def _rebuild_recent_menu(self):
        self.m_recent.clear()
        self.m_recent.setEnabled(bool(self.recent_files))
        for p in self.recent_files[:8]:
            act = QAction(os.path.basename(p), self)
            act.setToolTip(p)
            act.triggered.connect(lambda _=False, path=p: self._open_workflow_path(path))
            self.m_recent.addAction(act)

    def _add_recent(self, path: str):
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:8]
        self._rebuild_recent_menu()

    # ================================================== 网格
    def _on_tree_double(self, item, col):
        name = item.data(0, Qt.UserRole)
        if not name:
            return
        entry = self.registry.get(name)
        if entry:
            self.workflow_panel.add_step(entry)

    def new_grid(self):
        dlg = GridDialog(self)
        if not dlg.exec():
            return
        cfg = dlg.result_config()
        try:
            engine = Engine(self.ws, self.registry.plugins, log=self.log)
            if cfg["grid"].get("dem_file"):
                engine._load_dem(cfg["grid"]["dem_file"])
            else:
                engine._build_grid(cfg["grid"])
                if cfg.get("boundary"):
                    engine._apply_boundary(cfg["boundary"])
                if cfg.get("terrain"):
                    self.ws.init_terrain(**cfg["terrain"])
            self.canvas.update_all(self.ws)
            self._set_status(tr("网格 {0} 节点").format(self.ws.grid.number_of_nodes))
            self.workflow_panel.set_grid_config(cfg["grid"], cfg.get("terrain"),
                                                cfg.get("boundary"), from_dialog=True)
            self._frames_clear()
        except Exception as e:
            QMessageBox.critical(self, tr("建网格失败"), f"{type(e).__name__}: {e}")
            self.log(tr("运行出错") + ":\n" + traceback.format_exc())

    def show_grid_info(self):
        if not self.ws.has_grid:
            QMessageBox.information(self, tr("网格信息"), tr("尚无网格"))
            return
        g = self.ws.grid
        fields = ", ".join(list(g.at_node.keys())[:12])
        QMessageBox.information(
            self, "网格信息",
            f"类型: {self.ws.grid_info.get('type')}\n"
            f"节点数: {g.number_of_nodes}\n"
            f"字段: {fields}{' ...' if len(g.at_node) > 12 else ''}")

    # ================================================== 在线DEM
    def download_dem_dialog(self):
        if self._busy():
            QMessageBox.warning(self, tr("忙碌"), tr("有任务正在后台运行，请等待完成"))
            return
        from .dem_dialog import DemDownloadDialog
        dlg = DemDownloadDialog(self.settings, self)
        if not dlg.exec():
            return
        cfg = dlg.config()
        self._dem_cfg = cfg
        self._dem_result = None
        self.log(tr("开始下载在线DEM: {0} ...").format(cfg["name"][:60]))
        from ..core import dem_fetch
        self.func_worker = FuncWorker(
            lambda: dem_fetch.fetch_dem(cfg["south"], cfg["north"], cfg["west"],
                                        cfg["east"], cfg["zoom"],
                                        proxies=cfg["proxy"],
                                        log=lambda s: print(s)))
        self.func_worker.sig_log.connect(self.log)
        self.func_worker.sig_result.connect(self._dem_ready)
        self.func_worker.sig_done.connect(self._on_dem_done)
        self.func_worker.start()

    def _dem_ready(self, result):
        self._dem_result = result

    def _on_dem_done(self, ok, msg):
        res = getattr(self, "_dem_result", None)
        cfg = getattr(self, "_dem_cfg", {})
        self.func_worker = None
        if not ok or not res:
            QMessageBox.critical(self, tr("DEM下载失败"), msg)
            return
        z2d, dx, meta = res
        try:
            from landlab import RasterModelGrid
            g = RasterModelGrid(tuple(z2d.shape), xy_spacing=dx)
            g.at_node["topographic__elevation"] = np.asarray(z2d, dtype=float).reshape(-1)
            self.ws.set_grid(g, {"type": "RasterModelGrid(在线DEM)",
                                 "params": {"分辨率": f"{dx:.1f} m",
                                            "区域": cfg.get("name", "")[:60],
                                            "shape": list(z2d.shape),
                                            "xy_spacing": dx}})
            Engine(self.ws, self.registry.plugins, log=self.log)._apply_boundary(
                cfg.get("boundary", "south_open"))
            self.canvas.update_all(self.ws)
            self.workflow_panel.set_grid_config(
                {"type": "RasterModelGrid", "params": {"shape": list(z2d.shape),
                                                       "xy_spacing": dx}},
                None, cfg.get("boundary"), from_dialog=True)
            self._frames_clear()
            self._set_status(tr("真实DEM {1}×{0} 格").format(z2d.shape[0], z2d.shape[1]))
            self.log(tr("真实地形已就绪！推荐工作流: 构造抬升(可选) → PriorityFloodFlowRouter "
                     "→ FastscapeEroder → LinearDiffuser，点 ▶ 运行即可模拟河流切割真实山脉"))
        except Exception as e:
            QMessageBox.critical(self, tr("建网格失败"), f"{type(e).__name__}: {e}")
            self.log(tr("运行出错") + ":\n" + traceback.format_exc())

    # ================================================== 运行
    def run_workflow(self):
        if self._busy():
            QMessageBox.warning(self, tr("忙碌"), tr("有任务正在后台运行，请等待或停止"))
            return
        if not self.workflow_panel.rebuild_check.isChecked() and not self.ws.has_grid:
            QMessageBox.warning(self, "缺少网格",
                                tr("请先 菜单[网格]->新建网格，或载入预设（运行时自动建网格）"))
            return
        if not self.workflow_panel.steps:
            QMessageBox.warning(self, tr("空工作流"),
                                tr("请在左侧组件库双击组件/插件添加步骤，或载入场景预设"))
            return
        wf = self.workflow_panel.to_workflow(tr("未命名"))
        # 预校验：所有步骤引用的组件/插件必须存在（避免建完网格才在中途失败）
        missing = sorted({(st.get("component") or st.get("plugin"))
                          for st in wf["steps"]
                          if self.registry.get(st.get("component") or st.get("plugin")) is None})
        if missing:
            QMessageBox.critical(
                self, tr("运行失败"),
                tr("以下功能不存在（插件被删除/改名？）：\n{0}\n\n请删除或修正这些步骤后重试").format(
                    "\n".join(missing)))
            return
        self.log(tr("=== 开始运行工作流: {0} ===").format(wf.get("name", "未命名")))
        self._frames_clear()
        self._current_wf = wf

        flag = StopFlag()
        engine = Engine(self.ws, self.registry.plugins, log=self.log,
                        progress=self._engine_progress, snapshot=self._engine_snapshot,
                        stop_flag=flag)
        self.worker = SimWorker(engine, wf)
        self.worker.flag = flag
        self._last_progress_pct = -1
        try:      # 优先级只是优化项：任何环境下都不允许它弄挂运行流程
            self.worker.setPriority(QThread.Priority.LowPriority)
        except Exception:
            pass
        self.worker.sig_log.connect(self.log)
        self.worker.sig_progress.connect(self._on_progress)
        self.worker.sig_snapshot.connect(self._on_snapshot)
        self.worker.sig_done.connect(self._on_done)
        self._set_running(True)
        self.worker.start()

    def _engine_progress(self, i, n):
        """进度节流：只在百分比变化时发信号（2000 步从 2000 次跨线程事件
        降到 ≤100 次），否则高频 emit 会淹没主线程造成界面卡顿。"""
        if not self.worker:
            return
        pct = (i * 100) // max(1, n)
        if pct != self._last_progress_pct:
            self._last_progress_pct = pct
            self.worker.sig_progress.emit(i, n)

    def _engine_snapshot(self):
        if self.worker and self.ws.has_grid and "topographic__elevation" in self.ws.at_node:
            z = np.array(self.ws.at_node["topographic__elevation"], copy=True)
            self.worker.sig_snapshot.emit(z)

    def stop_workflow(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.log(tr("已请求停止，等待当前步完成..."))

    def _set_running(self, running: bool):
        self.act_start.setEnabled(not running)
        self.act_stop.setEnabled(running)
        self.workflow_panel.set_running(running)
        self.progress.setVisible(running)
        if running:
            self.progress.setValue(0)
        self.status_label.setText(" " + (tr(" 运行中... ") if running else tr("就绪 ").strip()) + " ")

    def _on_progress(self, i, n):
        self.progress.setMaximum(n)
        self.progress.setValue(i)
        if i >= n:
            self._last_progress_pct = -1

    def _on_snapshot(self, z):
        """主线程入口（worker 信号）：只存最新帧并启动节流定时器，
        真正的绘制在 _do_canvas_refresh 里合并执行。"""
        self._pending_z = z
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def _do_canvas_refresh(self):
        """节流后的实际绘制（≤3.3 次/秒），期间被跳过的快照直接丢弃。"""
        if not self.ws.has_grid:
            self._pending_z = None
            return
        self.canvas.update_all(self.ws)
        if self._pending_z is not None:
            self._collect_frame(self._pending_z)
        self._pending_z = None

    def _collect_frame(self, z):
        shape = getattr(self.ws.grid, "shape", None)
        z2d = z.reshape(shape) if shape and len(shape) == 2 else None
        if z2d is None:
            return
        vmin, vmax = float(np.nanmin(z2d)), float(np.nanmax(z2d))
        self._frame_vlims[0] = vmin if self._frame_vlims[0] is None else min(self._frame_vlims[0], vmin)
        self._frame_vlims[1] = vmax if self._frame_vlims[1] is None else max(self._frame_vlims[1], vmax)
        step = self.ws.history[-1][0] if self.ws.history else len(self._frames)
        title = f"{self.ws.grid_info.get('type', '')}  第 {step} 步"
        z32 = np.asarray(z2d, dtype=np.float32)      # 动画精度足够，内存减半
        self._frames.append((z32, self._frame_vlims[0], self._frame_vlims[1], title))
        self._frame_bytes += z32.nbytes
        # 控制内存：超过 400 帧或 150MB 时等间隔抽稀
        if len(self._frames) > 400 or self._frame_bytes > 150_000_000:
            frames = self._frames[::2] + [self._frames[-1]]
            self._frames = frames
            self._frame_bytes = sum(f[0].nbytes for f in frames)
        self.act_anim.setEnabled(len(self._frames) >= 2)

    def _frames_clear(self):
        self._frames.clear()
        self._frame_vlims = [None, None]
        self._frame_bytes = 0
        self.act_anim.setEnabled(False)

    def _on_done(self, ok: bool, msg: str):
        self._set_running(False)
        self.log(tr("运行结束: {0}").format(msg) if ok else tr("运行失败: {0}").format(msg))
        if self.ws.has_grid:
            self.canvas.update_all(self.ws)
            if ok and "topographic__elevation" in self.ws.at_node:
                z = np.array(self.ws.at_node["topographic__elevation"], copy=True)
                self._collect_frame(z)
                wf = getattr(self, "_current_wf", {})
                self.history_panel.add_snapshot(
                    wf.get("name", "未命名"), z, self.ws.grid_info, wf, self.ws.history)
        self.worker = None

    # ================================================== 独立导出
    def export_current(self):
        if not self.ws.has_grid:
            QMessageBox.warning(self, tr("缺少网格"), tr("请先创建网格"))
            return
        if self._busy():
            QMessageBox.warning(self, tr("忙碌"), tr("有任务正在后台运行，请等待完成"))
            return
        dlg = ExportDialog(self, last_dir=os.getcwd())
        if not dlg.exec():
            return
        cfg = dlg.config()
        if not cfg["formats"] and not cfg["river"]:
            QMessageBox.warning(self, tr("未选择"), tr("请至少选择一种格式或勾选河网导出"))
            return
        grid = self.ws.grid
        river_min = cfg["river_min_area"] if cfg["river"] else 1e30

        def _do():
            from ..core.exporter import export_all
            export_all(grid, output_dir=cfg["dir"], dem_formats=cfg["formats"],
                       river_min_area=river_min)
            return cfg["dir"]

        self.func_worker = FuncWorker(_do)
        self.func_worker.sig_log.connect(self.log)
        self.func_worker.sig_done.connect(self._on_func_done)
        self.func_worker.start()
        self.log(tr("后台导出到 {0} ...").format(cfg["dir"]))

    def _on_func_done(self, ok, msg):
        self.log((tr("导出完成") + ": " + msg) if ok else (tr("导出失败") + ": " + msg))
        self.func_worker = None

    # ================================================== 动画导出
    def export_animation(self):
        if len(self._frames) < 2:
            QMessageBox.information(self, tr("导出演化动画..."), tr("还没有动画帧：请先运行一次模拟"))
            return
        from ..core.animate import ffmpeg_available
        flt = tr("动画 (*.gif)") + ";;" + ("MP4 (*.mp4);;" if ffmpeg_available() else tr("所有文件 (*)"))
        path, _ = QFileDialog.getSaveFileName(self, tr("导出演化动画"),
                                              "evolution.gif", flt)
        if not path:
            return
        self.anim_worker = AnimWorker(list(self._frames), path, fps=10)
        self.anim_worker.sig_log.connect(self.log)
        self.anim_worker.sig_done.connect(self._on_anim_done)
        self.log(tr("正在生成动画（{0} 帧）...").format(len(self._frames)))
        self.anim_worker.start()

    def _on_anim_done(self, ok, msg):
        self.log(msg if ok else tr("导出失败: {0}").format(msg))
        self.anim_worker = None

    # ================================================== 参数扫描
    def open_sweep(self):
        if self._busy():
            QMessageBox.warning(self, tr("忙碌"), tr("有任务正在后台运行，请等待完成"))
            return
        from .sweep_dialog import SweepDialog
        dlg = SweepDialog(self.workflow_panel, self)
        if not dlg.exec():
            return
        cfg = getattr(dlg, "sweep_config", None)
        if cfg:
            self.start_sweep(cfg)

    def start_sweep(self, cfg: dict):
        """在主窗口托管扫描线程（对话框关闭不影响运行与结果窗口生命周期）。"""
        from app.workers.sim_worker import SweepWorker
        self.sweep_worker = SweepWorker(cfg["wf"], cfg["step_id"], cfg["param_name"],
                                        cfg["values"], self.registry.plugins)
        self.sweep_worker.sig_log.connect(self.log)
        self.sweep_worker.sig_progress.connect(self._on_sweep_progress)
        self.sweep_worker.sig_done.connect(self._on_sweep_done)
        self.sweep_worker.sig_result.connect(
            lambda res: self._open_sweep_result(res, cfg))
        self.progress.setMaximum(0)          # 忙碌指示
        self.progress.show()
        self.status_label.setText(" " + tr(" 运行中... ").strip() + " ")
        self.sweep_worker.start()

    def _on_sweep_progress(self, i, n):
        self.progress.setMaximum(n)
        self.progress.setValue(i)

    def _on_sweep_done(self, ok, msg):
        self.progress.hide()
        self.status_label.setText(" 就绪 ")
        self.log((tr("扫描完成") + ": " + msg) if ok else (tr("扫描失败") + ": " + msg))

    def _open_sweep_result(self, results, cfg):
        if not results:
            return
        from .sweep_dialog import SweepResultWindow
        win = SweepResultWindow(results, cfg["param_name"], cfg["out_dir"],
                                log=self.log, parent=self)
        win.setAttribute(Qt.WA_DeleteOnClose)
        win.show()
        win.raise_()

    # ================================================== 实验报告
    def generate_report(self):
        if not self.ws.has_grid:
            QMessageBox.warning(self, tr("缺少网格"), tr("请先运行一次模拟"))
            return
        if self._busy():
            QMessageBox.warning(self, tr("忙碌"), tr("有任务正在后台运行，请等待完成"))
            return
        out = QFileDialog.getExistingDirectory(self, tr("选择报告输出目录"), os.getcwd())
        if not out:
            return
        wf = self.workflow_panel.to_workflow(tr("未命名"))
        self.func_worker = FuncWorker(lambda: self._report_job(wf, out))
        self.func_worker.sig_log.connect(self.log)
        self.func_worker.sig_done.connect(self._on_func_done)
        self.func_worker.start()
        self.log(tr("正在生成实验报告..."))

    def _report_job(self, wf, out):
        from ..core.report import generate_report
        return generate_report(self.ws, wf, out, log=lambda s: print(s))

    def _busy(self) -> bool:
        """是否有后台任务在跑（模拟/导出/报告/扫描/动画）。"""
        for w in (self.worker, self.func_worker, self.anim_worker,
                  getattr(self, "sweep_worker", None)):
            if w is not None and w.isRunning():
                return True
        return False

    # ================================================== 文件
    def save_workflow(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("保存工作流"), "my_workflow.json",
                                              tr("工作流 JSON (*.json)"))
        if not path:
            return
        wf = self.workflow_panel.to_workflow(tr("未命名"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(wf, f, ensure_ascii=False, indent=2)
        self.log(tr("工作流已保存: {0}").format(path))
        self._add_recent(path)

    def open_workflow(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("打开工作流"), PRESET_DIR,
                                              tr("工作流 JSON (*.json)"))
        if not path:
            return
        self._open_workflow_path(path)

    def _open_workflow_path(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                wf = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, tr("打开失败"), str(e))
            return
        self.workflow_panel.load_workflow(wf)
        self.log(tr("工作流已载入: {0}").format(path))
        self._add_recent(path)

    def _load_preset(self, item):
        wf = self.presets.get(item.text())
        if not wf:
            return
        self.workflow_panel.load_workflow(wf)
        self.log(tr("已载入预设: {0} —— {1}").format(item.text(), wf.get("doc", "")))
        self.log(tr("点 ▶ 运行 即可（预设会自动建网格）"))

    # ================================================== 插件/帮助
    def reload_plugins(self):
        self.registry.reload()
        self._fill_tree(self.search.text())
        self.log(tr("插件已重载: 共 {0} 个自定义功能").format(len(self.registry.plugins)))

    def open_plugin_dir(self):
        os.startfile(plugins_dir(APP_ROOT))

    def _show_wizard(self):
        from .wizard import WelcomeWizard
        WelcomeWizard(self).exec()

    # ================================================== 语言切换
    def _sync_lang_actions(self):
        from ..core import i18n
        self.act_lang_zh.setChecked(i18n.is_zh())
        self.act_lang_en.setChecked(not i18n.is_zh())

    def switch_language(self, lang: str):
        from ..core import i18n
        if i18n.get_lang() == lang:
            return
        i18n.set_lang(lang)
        self.settings.setValue("lang", lang)
        self._sync_lang_actions()
        # 组件目录即时切换；完整界面文字重启后生效
        self._fill_tree(self.search.text())
        self.workflow_panel._refresh_list()
        self.log("已切换到中文显示" if lang == "zh" else "Switched to English display")
        r = QMessageBox.question(self, tr("🌐 组件显示语言 / Language"),
                                 tr("语言将在重启后完全生效，现在重启吗？"),
                                 QMessageBox.Yes | QMessageBox.No)
        if r == QMessageBox.Yes:
            import sys as _sys
            from ..core.i18n import restart_command
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("windowState", self.saveState())
            self.settings.setValue("recent_files", self.recent_files)
            QProcess.startDetached(restart_command()[0], restart_command()[1:])
            _sys.exit(0)

    def _open_plugin_doc(self):
        doc = os.path.join(APP_ROOT, "docs", "插件开发指南.md")
        if os.path.exists(doc):
            os.startfile(doc)

    def _set_status(self, text: str):
        self.status_label.setText(f" {text} ")

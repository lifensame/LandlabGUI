"""新手引导向导：四步走完基本流程（首次启动自动弹出，帮助菜单可重看）。"""

from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QStackedWidget, QVBoxLayout)

from ..core.i18n import tr

_PAGES = [
    ("欢迎使用 Landlab 地貌模拟工作台 🌏",
     "这是一个可视化的地貌演化模拟器：不用写代码，点选组件就能\n"
     "搭建\"抬升→汇流→侵蚀→扩散\"的工作流并实时看到山脉长出来。\n\n"
     "本向导用 4 步带你走完基本流程。"),
    ("第 1 步 · 建立网格",
     "菜单【网格 → 新建网格】。\n\n"
     "· 默认参数即可（80×100 格、100m 分辨率）\n"
     "· 或选\"从DEM导入\"加载真实地形 (.asc)\n"
     "· 边界条件建议保持默认（四周封闭+南缘出水口，教程同款）"),
    ("第 2 步 · 添加过程组件",
     "在左侧【组件库】双击任意组件即可加入工作流，推荐入门组合：\n\n"
     "  1. 构造抬升(4种模式)   —— 每步抬升（插件）\n"
     "  2. PriorityFloodFlowRouter —— 计算水流路径\n"
     "  3. FastscapeEroder        —— 河道下切\n"
     "  4. LinearDiffuser         —— 坡面扩散\n\n"
     "双击步骤列表中的条目可改参数（鼠标悬停看官方文档）。\n"
     "想偷懒？直接双击左下角【快速测试】预设，全部自动配好。"),
    ("第 3 步 · 运行并观察",
     "点工具栏【▶ 运行工作流】(F5)。\n\n"
     "· 右侧画布实时刷新：地形 / 汇水面积 / 坡度-面积 / 剖面 / 3D\n"
     "· 地形图上可缩放平移、点击查值、\"取点剖面\"画任意方向剖面\n"
     "· 底部控制台显示全部日志；随时可【■ 停止】"),
    ("第 4 步 · 分析与导出",
     "科研三件套都在菜单里：\n\n"
     "· 【工具 → 参数扫描实验】批量跑参数对比（论文级图表）\n"
     "· 【工具 → 生成实验报告】一键产出 Markdown+图组\n"
     "· 【工具 → 导出当前地形】asc/nc/vtk/obj + 河网 GIS 数据\n"
     "· 左侧【运行历史】可 A/B 对比与回滚\n\n"
     "准备就绪，点击\"完成\"开始你的第一次模拟！"),
]


class WelcomeWizard(QDialog):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent or main_window)
        self.mw = main_window
        self.setWindowTitle(tr("新手引导"))
        self.setMinimumSize(560, 380)

        lay = QVBoxLayout(self)
        self.stack = QStackedWidget()
        for title, body in [(tr(t), tr(b)) for t, b in _PAGES]:
            page = QLabel(f"<h2>{title}</h2><pre style='font-size:13px; line-height:160%'>{body}</pre>")
            page.setWordWrap(True)
            self.stack.addWidget(page)
        lay.addWidget(self.stack, stretch=1)

        btns = QHBoxLayout()
        self.btn_prev = QPushButton(tr("上一步"))
        self.btn_prev.clicked.connect(self._go_prev)
        self.btn_next = QPushButton(tr("下一步"))
        self.btn_next.setDefault(True)
        self.btn_next.clicked.connect(self._go_next)
        btns.addStretch()
        btns.addWidget(self.btn_prev)
        btns.addWidget(self.btn_next)
        lay.addLayout(btns)
        self._sync()

    def _go_prev(self):
        i = max(0, self.stack.currentIndex() - 1)
        self.stack.setCurrentIndex(i)
        self._sync()

    def _go_next(self):
        if self.stack.currentIndex() == len(_PAGES) - 1:
            self._finish()
            return
        self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
        self._sync()

    def _sync(self):
        last = self.stack.currentIndex() == len(_PAGES) - 1
        self.btn_prev.setEnabled(self.stack.currentIndex() > 0)
        self.btn_next.setText(tr("完成 🎉") if last else tr("下一步"))

    def _finish(self):
        if self.mw is not None and self.stack.currentIndex() == len(_PAGES) - 1:
            # 完成时顺手载入快速测试预设，让用户立刻能跑
            try:
                lw = self.mw.preset_list
                for i in range(lw.count()):
                    if lw.item(i).text() == "快速测试":
                        lw.setCurrentRow(i)
                        self.mw._load_preset(lw.item(i))
                        break
            except Exception:
                pass
        self.accept()

"""课堂实验停靠条：河流怎么切开山地。

界面只采集勾选、预设、运行结果、看过的图、选择题和导出的记录。
能不能进入下一步由 app.core.classroom 决定。
"""

from __future__ import annotations

import os

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFileDialog, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QRadioButton, QVBoxLayout, QWidget)

from ..core.classroom import (PRESET_NAME, STEP_IDS, TAB_TERRAIN, current_step,
                              gate, quiz_correct, render_lab_note, workflow_steps)
from ..core.i18n import tr


class ClassroomLabPanel(QWidget):
    """嵌在主窗口停靠条里的一节课。"""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.mw = main_window
        self.acknowledged_goal = False
        self._quiz_index: int | None = None
        self.note_written = False
        self.exported_name = ""
        self.tab_sequence: list[int] = []
        self._views_armed = False
        self._in_refresh = False

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        title = QLabel(tr("河流怎么切开山地"))
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f0f6fc;")
        root.addWidget(title)

        intro = QLabel(tr("给上课的学生和带实验的老师。做完四步过程、看完两张图，再交一份记录。"))
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #8b949e;")
        root.addWidget(intro)

        self.progress = QLabel()
        self.progress.setStyleSheet("color: #58a6ff; font-weight: 600;")
        root.addWidget(self.progress)

        self.step_title = QLabel()
        self.step_title.setStyleSheet("font-size: 14px; font-weight: 600;")
        root.addWidget(self.step_title)

        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.body)

        self.reason = QLabel()
        self.reason.setWordWrap(True)
        self.reason.setStyleSheet("color: #f59e0b;")
        root.addWidget(self.reason)

        self.goal_box = QCheckBox(tr("我已阅读学习目标"))
        self.goal_box.toggled.connect(self._on_goal)
        root.addWidget(self.goal_box)

        self.quiz_box = QWidget()
        quiz_lay = QVBoxLayout(self.quiz_box)
        quiz_lay.setContentsMargins(0, 0, 0, 0)
        self.quiz_group = QButtonGroup(self)
        self._quiz_buttons = [
            QRadioButton(tr("汇水面积越大，河道坡度总体越缓")),
            QRadioButton(tr("汇水面积越大，河道坡度总体越陡")),
            QRadioButton(tr("坡度和汇水面积没有关系")),
        ]
        for index, button in enumerate(self._quiz_buttons):
            self.quiz_group.addButton(button, index)
            button.toggled.connect(lambda checked, i=index: self._on_quiz(i) if checked else None)
            quiz_lay.addWidget(button)
        root.addWidget(self.quiz_box)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(tr("学生姓名")))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("交给老师的名字"))
        self.name_edit.textChanged.connect(lambda _text: self.refresh())
        self.name_row_wrap = QWidget()
        self.name_row_wrap.setLayout(name_row)
        root.addWidget(self.name_row_wrap)

        actions = QHBoxLayout()
        self.btn_load = QPushButton(tr("载入课堂预设"))
        self.btn_load.clicked.connect(self._load_preset)
        self.btn_run = QPushButton(tr("开始运行"))
        self.btn_run.clicked.connect(self._start_run)
        self.btn_export = QPushButton(tr("导出实验记录"))
        self.btn_export.clicked.connect(self._export_clicked)
        self.btn_check = QPushButton(tr("检查进度"))
        self.btn_check.setDefault(True)
        self.btn_check.clicked.connect(self.refresh)
        actions.addWidget(self.btn_load)
        actions.addWidget(self.btn_run)
        actions.addWidget(self.btn_export)
        actions.addWidget(self.btn_check)
        root.addLayout(actions)

        extra = QHBoxLayout()
        self.btn_explore = QPushButton(tr("自己探索"))
        self.btn_explore.clicked.connect(self._explore)
        self.btn_doc = QPushButton(tr("打开老师讲义"))
        self.btn_doc.clicked.connect(self._open_doc)
        extra.addWidget(self.btn_explore)
        extra.addWidget(self.btn_doc)
        extra.addStretch(1)
        root.addLayout(extra)
        root.addStretch(1)

        self.mw.canvas.currentChanged.connect(self._on_tab)
        self.refresh()

    def snapshot(self) -> dict:
        panel = self.mw.workflow_panel
        return {
            "acknowledged_goal": self.acknowledged_goal,
            "workflow_name": panel.name_edit.text().strip(),
            "steps": workflow_steps(panel.steps),
            "steps_done": int(getattr(self.mw.ws, "steps_done", 0) or 0),
            "interrupted": bool(getattr(self.mw.ws, "interrupted", False)),
            "tab_sequence": list(self.tab_sequence),
            "quiz_index": self._quiz_index,
            "student_name": self.name_edit.text(),
            "note_written": self.note_written,
            "exported_name": self.exported_name,
        }

    def refresh(self):
        if self._in_refresh:
            return
        self._in_refresh = True
        try:
            snap = self.snapshot()
            step = current_step(snap)
            if step == 4 and not self._views_armed:
                self._views_armed = True
                self.tab_sequence = [TAB_TERRAIN]
                self.mw.canvas.setCurrentIndex(TAB_TERRAIN)
                snap = self.snapshot()
                step = current_step(snap)
            elif step < 4 and self._views_armed:
                self._views_armed = False
                self.tab_sequence = []
                snap = self.snapshot()
                step = current_step(snap)

            total = len(STEP_IDS)
            if step >= total:
                self.progress.setText(tr("课堂实验完成"))
                self.step_title.setText(tr("可以交作业了"))
                self.body.setText(tr(
                    "记录里已经有预设名、完成步数、平均高程、最大高程和你的选择。"
                    "把文件交给老师。想继续试参数，可以用左侧组件库。"))
                self.reason.setText("")
                self.mw.settings.setValue("classroom_seen", True)
            else:
                self.progress.setText(tr("第 {0} / {1} 步").format(step + 1, total))
                self.step_title.setText(self._title(step))
                self.body.setText(self._body(step))
                _ok, code = gate(STEP_IDS[step], snap)
                self.reason.setText("" if _ok else self._reason(code))

            self.goal_box.setVisible(step == 0)
            self.quiz_box.setVisible(step == 5)
            self.name_row_wrap.setVisible(step == 6)
            self.btn_load.setVisible(step == 1)
            self.btn_run.setVisible(step == 3)
            self.btn_export.setVisible(step == 6)
            self.btn_check.setVisible(step < total)
        finally:
            self._in_refresh = False

    def _on_goal(self, checked: bool):
        self.acknowledged_goal = bool(checked)
        self.refresh()

    def _on_quiz(self, index: int):
        self._quiz_index = int(index)
        self.refresh()

    def _on_tab(self, index: int):
        if self._in_refresh or not self._views_armed:
            return
        if not self.tab_sequence or self.tab_sequence[-1] != index:
            self.tab_sequence.append(int(index))
        self.refresh()

    def note_tab(self, index: int):
        """测试和画布切换共用的看图记录。"""
        self._on_tab(index)

    def _load_preset(self):
        self.mw.load_preset_by_name(PRESET_NAME)
        self.refresh()

    def _start_run(self):
        self.mw.run_workflow()

    def _export_clicked(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr("导出实验记录"), "课堂实验记录.md",
            tr("Markdown (*.md)"))
        if path:
            self.export_note(path)

    def export_note(self, path: str) -> str:
        student = self.name_edit.text().strip()
        if not student:
            self.refresh()
            return ""
        mean_z, max_z = self._elevation()
        answer = ""
        if self._quiz_index is not None and 0 <= self._quiz_index < len(self._quiz_buttons):
            answer = self._quiz_buttons[self._quiz_index].text()
        text = render_lab_note(
            student=student,
            preset=PRESET_NAME,
            steps_done=int(getattr(self.mw.ws, "steps_done", 0) or 0),
            mean_z=mean_z,
            max_z=max_z,
            answer=answer,
            correct=quiz_correct(self._quiz_index),
        )
        folder = os.path.dirname(os.path.abspath(path))
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        self.note_written = True
        self.exported_name = student
        self.mw.log(tr("实验记录已导出: {0}").format(path))
        self.refresh()
        return text

    def _elevation(self) -> tuple[float, float]:
        ws = self.mw.ws
        if not ws.has_grid or "topographic__elevation" not in ws.at_node:
            return 0.0, 0.0
        values = np.asarray(ws.at_node["topographic__elevation"], dtype=float)
        return float(np.nanmean(values)), float(np.nanmax(values))

    def _explore(self):
        self.mw.settings.setValue("classroom_seen", True)
        dock = getattr(self.mw, "lab_dock", None)
        if dock is not None:
            dock.hide()
        self.mw.log(tr("已离开课堂实验，下面是原来的新手引导。"))
        self.mw._show_wizard()

    def _open_doc(self):
        from ..core.plugin_loader import app_root
        path = os.path.join(app_root(), "docs", "课堂实验-河流下切.md")
        if not os.path.exists(path):
            QMessageBox.warning(self, tr("打开失败"), tr("找不到老师讲义。"))
            return
        self.mw.open_local_path(path)

    def _title(self, step: int) -> str:
        if step == 0:
            return tr("学习目标")
        if step == 1:
            return tr("载入预设")
        if step == 2:
            return tr("看懂四步")
        if step == 3:
            return tr("运行模拟")
        if step == 4:
            return tr("看图")
        if step == 5:
            return tr("选择题")
        return tr("实验记录")

    def _body(self, step: int) -> str:
        if step == 0:
            return tr(
                "这节课给地貌学或自然地理课的学生，也给带实验的老师。\n\n"
                "做完后你应该能说出四件事：\n"
                "· 构造抬升把地面抬高\n"
                "· 汇流算出水往哪流、汇水面积有多大\n"
                "· 河道下切沿水路切出河谷\n"
                "· 坡面扩散把陡坡变缓\n\n"
                "最后看坡度-面积图：河道段通常是汇水面积越大、坡度越缓。")
        if step == 1:
            return tr(
                "点「载入课堂预设」，或在左侧「场景预设」里双击「课堂实验-河流下切」。\n"
                "这个预设用小网格，一节课里几十秒可以跑完，并且不会自动导出文件。")
        if step == 2:
            return tr(
                "工作流里应依次是：\n"
                "1. 构造抬升(4种模式) — 每个时间步把地面抬高一点\n"
                "2. PriorityFloodFlowRouter — 算出水流路径和汇水面积\n"
                "3. FastscapeEroder — 沿着河道向下切\n"
                "4. LinearDiffuser — 坡面上的土石慢慢摊平")
        if step == 3:
            return tr(
                "点「开始运行」，或按 F5。等到控制台写出运行完成。\n"
                "中途停止的话，这步不算完成，需要再完整跑一次。")
        if step == 4:
            return tr(
                "右侧画布已经停在地形高程。先看山谷有没有被切出来，"
                "再点「坡度-面积」。先看地形、再看坡度-面积，这步才通过。")
        if step == 5:
            return tr("河道段在坡度-面积图上，大致是什么关系？")
        return tr(
            "写下你的姓名，导出 Markdown 实验记录。"
            "里面会有预设名、完成步数、平均和最大高程，以及你选的答案。")

    def _reason(self, code: str) -> str:
        if code == "goal":
            return tr("请先勾选「我已阅读学习目标」。")
        if code == "load":
            return tr("请先载入预设「课堂实验-河流下切」。")
        if code == "order":
            return tr(
                "四步顺序不对。应为：构造抬升 → PriorityFloodFlowRouter → "
                "FastscapeEroder → LinearDiffuser。")
        if code == "run_interrupted":
            return tr("这次运行被中断了。请再完整跑一次，不要中途停止。")
        if code == "run_none":
            return tr("还没有完整跑完。请运行工作流，并等到它结束。")
        if code == "views":
            return tr("请先打开地形高程，再打开坡度-面积。")
        if code == "quiz":
            return tr("请先选择一个答案。")
        if code == "name":
            return tr("请填写学生姓名。")
        if code == "note":
            return tr("请导出实验记录。改过姓名后要重新导出。")
        return tr("这一步还没完成。")

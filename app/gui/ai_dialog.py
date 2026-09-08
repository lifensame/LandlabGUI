"""AI 参数助手对话框：自然语言 → 工作流配置。"""

from __future__ import annotations

import json

from ..core.i18n import tr
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton,
                               QVBoxLayout)

from ..core import ai_assistant


class AiAssistantDialog(QDialog):
    """收集场景描述与 API 配置 → 后台调用 LLM → 产出工作流 JSON。

    self.workflow (dict|None)：成功解析的工作流，由主窗口接管。
    """

    def __init__(self, settings: QSettings, component_names: list, plugin_names: list,
                 parent=None):
        super().__init__(parent)
        self.settings = settings
        self.component_names = component_names
        self.plugin_names = plugin_names
        self.workflow = None
        self._worker = None
        self._known = set(component_names) | set(plugin_names)

        self.setWindowTitle(tr("AI 参数助手"))
        self.setMinimumSize(640, 620)

        root = QVBoxLayout(self)

        tip = QLabel(tr(
            "用一句自然语言描述想要的模拟场景，AI 自动配置整个工作流。\n"
            "兼容任意 OpenAI 风格接口（OpenAI / DeepSeek / Kimi / 本地 Ollama 等），"
            "Key 保存在本机，不上传。"))
        tip.setWordWrap(True)
        root.addWidget(tip)

        # ---- 场景描述 ----
        gb1 = QGroupBox(tr("① 场景描述"))
        v1 = QVBoxLayout(gb1)
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText(tr(
            "例：我想要一个青藏高原式的场景：北缘快速隆升（1e-3 m/yr）南缘缓慢，\n"
            "基岩较硬（K=2e-6），网格 100×120，模拟 50 万年，最后输出 χ 和 ksn 分析"))
        self.desc_edit.setMinimumHeight(96)
        v1.addWidget(self.desc_edit)
        root.addWidget(gb1)

        # ---- API 配置 ----
        gb2 = QGroupBox(tr("② 接口配置"))
        f2 = QFormLayout(gb2)
        presets = [
            ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
            ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
            ("Kimi (Moonshot)", "https://api.moonshot.cn/v1", "moonshot-v1-8k"),
            ("本地 Ollama", "http://127.0.0.1:11434/v1", "qwen2.5:7b"),
        ]
        self.preset_combo = QComboBox()
        self.preset_combo.addItem(tr("— 选择服务商预设 —"), None)
        for label, url, model in presets:
            self.preset_combo.addItem(label, (url, model))
        self.preset_combo.currentIndexChanged.connect(self._apply_preset)
        f2.addRow(tr("服务商预设"), self.preset_combo)
        self.url_edit = QLineEdit(str(self.settings.value("ai_base_url", "") or ""))
        self.url_edit.setPlaceholderText("https://api.deepseek.com/v1")
        f2.addRow(tr("API 地址"), self.url_edit)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setText(str(self.settings.value("ai_api_key", "") or ""))
        self.key_edit.setPlaceholderText(tr("留空=无需鉴权（本地 Ollama）"))
        f2.addRow(tr("API Key"), self.key_edit)
        self.model_edit = QLineEdit(str(self.settings.value("ai_model", "") or ""))
        self.model_edit.setPlaceholderText("deepseek-chat")
        f2.addRow(tr("模型名"), self.model_edit)
        self.proxy_edit = QLineEdit(str(self.settings.value("ai_proxy", "") or ""))
        self.proxy_edit.setPlaceholderText(tr("留空=系统代理；如 http://127.0.0.1:7890"))
        f2.addRow(tr("网络代理"), self.proxy_edit)
        root.addWidget(gb2)

        # ---- 原始回复（折叠查看） ----
        self.raw_view = QPlainTextEdit()
        self.raw_view.setReadOnly(True)
        self.raw_view.setMaximumHeight(90)
        self.raw_view.setPlaceholderText(tr("AI 原始回复（出错时用于排查）"))
        self.raw_view.hide()
        self.btn_raw = QPushButton(tr("查看原始回复"))
        self.btn_raw.setFlat(True)
        self.btn_raw.hide()
        self.btn_raw.clicked.connect(self.raw_view.show)
        root.addWidget(self.btn_raw)
        root.addWidget(self.raw_view)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#9aa0a6;")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.btn_generate = bb.button(QDialogButtonBox.Ok)
        self.btn_generate.setText(tr("生成工作流"))
        self.btn_generate.setDefault(True)
        bb.accepted.connect(self._on_ok)          # 唯一入口：校验+启动生成
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    # ------------------------------------------------ UI 行为
    def _apply_preset(self, idx):
        cfg = self.preset_combo.currentData()
        if cfg:
            url, model = cfg
            self.url_edit.setText(url)
            self.model_edit.setText(model)

    def reject(self):
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, tr("AI 参数助手"), tr("正在生成中，请等待完成"))
            return
        super().reject()

    # ------------------------------------------------ 生成
    def _on_ok(self):
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(self, tr("AI 参数助手"), tr("正在生成中，请等待完成"))
            return
        self._generate()

    def _generate(self):
        desc = self.desc_edit.toPlainText().strip()
        if not desc:
            QMessageBox.warning(self, tr("AI 参数助手"), tr("请先描述场景"))
            return
        base_url = self.url_edit.text().strip()
        if not base_url:
            QMessageBox.warning(self, tr("AI 参数助手"), tr("请填写 API 地址（或选择服务商预设）"))
            return
        for key, val in [("ai_base_url", base_url), ("ai_api_key", self.key_edit.text()),
                         ("ai_model", self.model_edit.text()),
                         ("ai_proxy", self.proxy_edit.text())]:
            self.settings.setValue(key, val)

        from app.workers.sim_worker import FuncWorker
        # Qt 控件只能在主线程访问：先把全部值捕获为字符串再交给工作线程
        args = (self.desc_edit.toPlainText().strip(),
                base_url, self.key_edit.text().strip(),
                self.model_edit.text().strip(),
                self.proxy_edit.text().strip() or None)
        self._worker = FuncWorker(self._call_llm, *args)
        self._worker.sig_result.connect(self._on_result)
        self._worker.sig_done.connect(self._on_done)
        self._worker.sig_log.connect(self.status.setText)
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText(tr("生成中…"))
        self.status.setText(tr("正在请求 AI（可能需要 10~60 秒）…"))
        self._worker.start()

    def _call_llm(self, desc, base_url, api_key, model, proxy):
        proxies = {"http": proxy, "https": proxy} if proxy else None
        system = ai_assistant.build_system_prompt(self.component_names, self.plugin_names)
        text = ai_assistant.ask_llm(system, ai_assistant.build_user_prompt(desc),
                                    base_url, api_key, model, proxies=proxies)
        self._raw_text = text
        return ai_assistant.extract_workflow_json(text)

    def _on_result(self, wf):
        self.workflow = wf

    def _on_done(self, ok, msg):
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText(tr("生成工作流"))
        raw = getattr(self, "_raw_text", "")
        if raw:
            self.raw_view.setPlainText(raw[:3000])
            self.btn_raw.show()
            self.raw_view.show()
        if not ok:
            self.status.setText(tr("生成失败") + ": " + msg)
            return
        # 校验步骤引用
        missing = ai_assistant.validate_workflow(self.workflow or {}, self._known)
        if missing:
            self.status.setText(tr("以下名称 AI 编造了或不存在，已自动移除这些步骤") + ": "
                                + ", ".join(missing))
            wf = self.workflow
            wf["steps"] = [s for s in wf["steps"]
                           if (s.get("component") or s.get("plugin")) not in missing]
            if not wf["steps"]:
                QMessageBox.warning(self, tr("AI 参数助手"),
                                    tr("AI 生成的步骤全部无效，请换一种描述或更强的模型"))
                return
        else:
            self.status.setText(tr("生成成功") + f": {len(self.workflow['steps'])} 个步骤")
        self.accept()

    # ------------------------------------------------ 结果
    @staticmethod
    def tr_static(s):
        return s

    def result_workflow(self):
        return self.workflow


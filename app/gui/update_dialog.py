"""
检查更新结果对话框：展示新版本信息、更新说明、直达下载与直链复制。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QTextEdit, QVBoxLayout, QWidget)

from ..core.i18n import tr


class UpdateDialog(QDialog):
    """现代化 Titanium Dark 风格的检查更新反馈对话框。"""

    def __init__(self, info: dict, parent=None):
        super().__init__(parent)
        self.info = info or {}
        has_update = self.info.get("has_update", False)
        latest_ver = self.info.get("latest_version", "")
        current_ver = self.info.get("current_version", "")
        rel_name = self.info.get("release_name", "")
        notes = self.info.get("release_notes", "")
        pub_at = self.info.get("published_at", "")[:10]
        html_url = self.info.get("html_url", "")
        download_url = self.info.get("download_url", "")
        asset_size = self.info.get("asset_size")

        self.setWindowTitle(tr("检查更新") + (" - " + tr("发现新版本") if has_update else ""))
        self.resize(580, 440 if has_update else 240)
        self.setMinimumWidth(500)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 16)
        root.setSpacing(14)

        if has_update:
            # ---- 发现新版本 ----
            head_lay = QVBoxLayout()
            head_lay.setSpacing(6)

            badge_row = QHBoxLayout()
            badge_row.setSpacing(8)
            badge = QLabel(tr("发现新版本可用"))
            badge.setStyleSheet("""
                background: #142820;
                color: #34d399;
                border: 1px solid #1e4a36;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 12px;
                font-weight: 600;
            """)
            badge_row.addWidget(badge)
            ver_lbl = QLabel(f"{current_ver}  ➔  <b style='color:#58a6ff; font-size:14px'>{latest_ver}</b>")
            ver_lbl.setStyleSheet("font-size: 12px; color: #8b949e;")
            badge_row.addWidget(ver_lbl)
            badge_row.addStretch()
            head_lay.addLayout(badge_row)

            title_lbl = QLabel(f"<b>{rel_name}</b>")
            title_lbl.setStyleSheet("font-size: 14px; color: #f0f6fc;")
            title_lbl.setWordWrap(True)
            head_lay.addWidget(title_lbl)

            meta_parts = []
            if pub_at:
                meta_parts.append(tr("发布日期: ") + pub_at)
            if asset_size:
                size_mb = asset_size / (1024 * 1024)
                meta_parts.append(tr("绿色包大小: ") + f"{size_mb:.1f} MB")
            if meta_parts:
                meta_lbl = QLabel("  •  ".join(meta_parts))
                meta_lbl.setStyleSheet("color: #8b949e; font-size: 11px;")
                head_lay.addWidget(meta_lbl)

            root.addLayout(head_lay)

            # 更新说明
            notes_box = QTextEdit()
            notes_box.setReadOnly(True)
            notes_box.setMarkdown(notes if notes.strip() else tr("（该版本暂无详细更新说明）"))
            notes_box.setStyleSheet("""
                QTextEdit {
                    background: #0f131a;
                    color: #cbd5e1;
                    border: 1px solid #262c37;
                    border-radius: 6px;
                    padding: 8px 10px;
                    font-size: 12px;
                    line-height: 140%;
                }
            """)
            root.addWidget(notes_box, stretch=1)

            # 操作按钮栏
            btn_row = QHBoxLayout()
            btn_row.setSpacing(10)

            self.btn_copy = QPushButton(tr("复制下载链接"))
            self.btn_copy.setToolTip(download_url)
            self.btn_copy.clicked.connect(lambda: self._copy_url(download_url))
            btn_row.addWidget(self.btn_copy)

            btn_row.addStretch()

            btn_later = QPushButton(tr("稍后再说"))
            btn_later.clicked.connect(self.reject)
            btn_row.addWidget(btn_later)

            btn_download = QPushButton(tr("前往 GitHub 下载"))
            btn_download.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10b981, stop:1 #059669);
                    color: #ffffff;
                    border: 1px solid #34d399;
                    border-radius: 6px;
                    font-weight: 600;
                    padding: 6px 18px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #059669, stop:1 #047857);
                    border-color: #6ee7b7;
                }
            """)
            target_url = download_url if download_url else html_url
            btn_download.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(target_url)))
            btn_row.addWidget(btn_download)

            root.addLayout(btn_row)

        else:
            # ---- 当前已是最新版本 ----
            center_lay = QVBoxLayout()
            center_lay.setSpacing(10)

            badge_row = QHBoxLayout()
            badge = QLabel(tr("当前已是最新版本"))
            badge.setStyleSheet("""
                background: #142820;
                color: #34d399;
                border: 1px solid #1e4a36;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 13px;
                font-weight: 600;
            """)
            badge_row.addWidget(badge)
            badge_row.addStretch()
            center_lay.addLayout(badge_row)

            msg_lbl = QLabel(tr("您当前运行的是最新版本 Landlab 地貌模拟工作台 (") + f"<b>{current_ver}</b>)。\n" +
                             tr("暂无更高版本发布。"))
            msg_lbl.setStyleSheet("color: #e6edf3; font-size: 12px; line-height: 150%;")
            msg_lbl.setWordWrap(True)
            center_lay.addWidget(msg_lbl)

            if rel_name:
                rel_lbl = QLabel(tr("最新发行版: ") + f"<span style='color:#8b949e'>{rel_name}</span>")
                rel_lbl.setStyleSheet("font-size: 11px; color: #8b949e;")
                center_lay.addWidget(rel_lbl)

            root.addLayout(center_lay)
            root.addStretch(1)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(10)

            btn_releases = QPushButton(tr("查看版本历史"))
            btn_releases.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(html_url or "https://github.com/lifensame/LandlabGUI/releases")))
            btn_row.addWidget(btn_releases)

            btn_row.addStretch()

            btn_ok = QPushButton(tr("确定"))
            btn_ok.setDefault(True)
            btn_ok.clicked.connect(self.accept)
            btn_row.addWidget(btn_ok)

            root.addLayout(btn_row)

    def _copy_url(self, url: str):
        if url:
            cb = QGuiApplication.clipboard()
            cb.setText(url)
            self.btn_copy.setText(tr("已复制下载链接"))

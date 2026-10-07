# -*- coding: utf-8 -*-
"""
更新检查与版本比对单元测试。
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.version import __version__, parse_version, is_newer
from app.core.updater import check_for_updates


class TestVersionUtils(unittest.TestCase):

    def test_parse_version(self):
        self.assertEqual(parse_version("v2.1.0"), (2, 1, 0))
        self.assertEqual(parse_version("2.1.0"), (2, 1, 0))
        self.assertEqual(parse_version("v2.2"), (2, 2, 0))
        self.assertEqual(parse_version("v3.0.0-alpha"), (3, 0, 0))
        self.assertEqual(parse_version(""), (0, 0, 0))
        self.assertEqual(parse_version("invalid"), (0, 0, 0))

    def test_is_newer(self):
        self.assertTrue(is_newer("v2.2.0", "v2.1.0"))
        self.assertTrue(is_newer("v2.1.1", "v2.1.0"))
        self.assertTrue(is_newer("v3.0.0", "v2.1.0"))
        self.assertFalse(is_newer("v2.1.0", "v2.1.0"))
        self.assertFalse(is_newer("v2.0.9", "v2.1.0"))
        self.assertFalse(is_newer("v1.9.9", "v2.1.0"))


class TestUpdaterAPI(unittest.TestCase):

    @patch("requests.get")
    def test_check_for_updates_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v2.2.0",
            "name": "v2.2.0 新版本发布",
            "body": "## 升级日志\n- 支持更多地貌组件",
            "published_at": "2026-09-08T18:00:00Z",
            "html_url": "https://github.com/lifensame/LandlabGUI/releases/tag/v2.2.0",
            "assets": [
                {
                    "name": "LandlabGUI-v2.2.0-win64.zip",
                    "browser_download_url": "https://github.com/lifensame/LandlabGUI/releases/download/v2.2.0/LandlabGUI-v2.2.0-win64.zip",
                    "size": 180000000,
                }
            ],
        }
        mock_get.return_value = mock_resp

        res = check_for_updates(current_version="2.1.0")
        self.assertTrue(res["has_update"])
        self.assertEqual(res["latest_version"], "v2.2.0")
        self.assertEqual(res["current_version"], "v2.1.0")
        self.assertIn("LandlabGUI-v2.2.0-win64.zip", res["download_url"])
        self.assertEqual(res["asset_size"], 180000000)

    @patch("requests.get")
    def test_check_for_updates_already_latest(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v2.1.0",
            "name": "v2.1.0 最新版",
            "body": "无更新",
            "published_at": "2026-09-08T18:00:00Z",
            "html_url": "https://github.com/lifensame/LandlabGUI/releases/tag/v2.1.0",
            "assets": [],
        }
        mock_get.return_value = mock_resp

        res = check_for_updates(current_version="2.1.0")
        self.assertFalse(res["has_update"])
        self.assertEqual(res["latest_version"], "v2.1.0")


if __name__ == "__main__":
    unittest.main()

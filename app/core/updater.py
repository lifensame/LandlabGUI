"""
在线更新检查模块：对接 GitHub Releases API 获取最新发布信息。
零 Qt 依赖，可在子线程中直接调用。
"""

from __future__ import annotations

import requests
from .version import __version__, is_newer
from .dem_fetch import make_proxies

GITHUB_REPO = "lifensame/LandlabGUI"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASE_PAGE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


def check_for_updates(current_version: str = __version__,
                      proxy: str | None = None,
                      timeout: int = 15) -> dict:
    """
    检查是否有新版本发布。
    返回结构:
    {
        "has_update": bool,
        "latest_version": str,      # 如 'v2.2.0'
        "current_version": str,     # 如 'v2.1.0'
        "release_name": str,        # 标题
        "release_notes": str,       # 更新日志 (Markdown)
        "published_at": str,        # ISO时间字符串
        "html_url": str,            # 网页查看地址
        "download_url": str | None, # win64 zip 直链
        "asset_name": str | None,
        "asset_size": int | None,   # 字节
    }
    """
    headers = {
        "User-Agent": f"LandlabGUI/{current_version}",
        "Accept": "application/vnd.github.v3+json",
    }
    try:
        resp = requests.get(
            LATEST_RELEASE_API,
            headers=headers,
            proxies=make_proxies(proxy),
            timeout=timeout,
        )
        if resp.status_code == 404:
            raise RuntimeError(f"仓库或发布版本不存在 ({GITHUB_REPO})")
        if resp.status_code == 403:
            raise RuntimeError("GitHub API 访问速率受限，请稍候再试或配置代理")
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout as e:
        raise ConnectionError("连接 GitHub 检查更新超时，请检查网络或配置代理") from e
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"检查更新网络请求失败: {e}") from e
    except ValueError as e:
        raise ConnectionError("GitHub 返回了非 JSON 响应") from e

    latest_tag = data.get("tag_name", "")
    release_name = data.get("name") or latest_tag
    body = data.get("body", "")
    published_at = data.get("published_at", "")
    html_url = data.get("html_url") or RELEASE_PAGE_URL

    download_url = None
    asset_name = None
    asset_size = None

    assets = data.get("assets", [])
    for a in assets:
        name = a.get("name", "")
        if "win" in name.lower() and name.endswith(".zip"):
            download_url = a.get("browser_download_url")
            asset_name = name
            asset_size = a.get("size")
            break

    if not download_url and assets:
        download_url = assets[0].get("browser_download_url")
        asset_name = assets[0].get("name")
        asset_size = assets[0].get("size")

    if not download_url:
        download_url = html_url

    has_up = is_newer(latest_tag, current_version)

    return {
        "has_update": has_up,
        "latest_version": latest_tag,
        "current_version": f"v{current_version}" if not current_version.startswith("v") else current_version,
        "release_name": release_name,
        "release_notes": body,
        "published_at": published_at,
        "html_url": html_url,
        "download_url": download_url,
        "asset_name": asset_name,
        "asset_size": asset_size,
    }

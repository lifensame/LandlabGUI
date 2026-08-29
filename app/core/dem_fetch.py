"""
在线真实 DEM 获取：地名搜索 + 全球高程瓦片下载拼接。
====================================================
- 地名搜索: OpenStreetMap Nominatim（免费无密钥）
- 高程数据: AWS Open Data 的 Terrarium 高程瓦片（含 SRTM/Copernicus/GMTED 等来源，
  免密钥），Web Mercator 瓦片，高程编码 elev = (R*256 + G + B/256) - 32768

所有函数均为纯 Python（无 Qt），可独立测试。网络失败抛带中文说明的异常。
"""

from __future__ import annotations

import io
import math

import numpy as np
import requests

_UA = {"User-Agent": "LandlabGUI/1.0 (local educational tool)"}
_TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def make_proxies(proxy: str | None) -> dict | None:
    """用户填了代理则用之；留空返回 None（requests 自动用系统/环境代理）。"""
    if proxy and proxy.strip():
        p = proxy.strip()
        return {"http": p, "https": p}
    return None


# ============================================================ 地名搜索
# 自然地貌类型优先（避免"华山"匹配到某村庄而不是山峰）
_TERRAIN_TYPES = {"peak", "volcano", "mountain_range", "ridge", "hill", "mountain",
                  "valley", "canyon", "gorge", "glacier", "cliff", "plateau",
                  "island", "islet", "water", "river", "lake", "bay", "desert"}


def geocode(query: str, proxies=None, limit: int = 8) -> list[dict]:
    """地名 -> 候选列表 [{name, south, north, west, east}]，地貌类结果排前。"""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": limit,
                    "accept-language": "zh"},
            headers=_UA, proxies=make_proxies(proxies), timeout=20)
        r.raise_for_status()
        items = r.json()
    except requests.exceptions.Timeout as e:
        raise ConnectionError("地名搜索超时（可能需要配置代理，如 http://127.0.0.1:7890）") from e
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"地名搜索失败: {e}（检查网络/代理设置）") from e
    except ValueError as e:
        raise ConnectionError("地名搜索返回了非 JSON 响应（代理/网关异常？）") from e
    out = []
    for it in items:
        bb = it.get("boundingbox")            # [南, 北, 西, 东] 字符串
        if not bb or len(bb) != 4:
            continue
        out.append({"name": it.get("display_name", query),
                    "type": it.get("type", ""),
                    "terrain": it.get("type", "") in _TERRAIN_TYPES,
                    "south": float(bb[0]), "north": float(bb[1]),
                    "west": float(bb[2]), "east": float(bb[3])})
    if not out:
        raise ValueError(f"未找到地名: {query}（试试更通用的写法，或手动输入经纬度范围）")
    out.sort(key=lambda d: not d["terrain"])   # 地貌类排前，稳定排序保持原次序
    return out


# ============================================================ 瓦片坐标
def _ll2global_px(lat: float, lon: float, z: int) -> tuple[float, float]:
    """经纬度 -> Web Mercator 全局像素坐标（y 向南增大）。"""
    n = 2 ** z * 256
    px = (lon + 180.0) / 360.0 * n
    lat = max(-85.0511, min(85.0511, lat))
    lat_r = math.radians(lat)
    py = (1 - math.asinh(math.tan(lat_r)) / math.pi) / 2 * n
    return px, py


def suggest_zoom(south, north, west, east, max_px=1000, zmin=9, zmax=13) -> int:
    """按包围盒自动推荐缩放级别（输出不超过 max_px 像素的最精细级别）。"""
    for z in range(zmax, zmin - 1, -1):
        px0, py0 = _ll2global_px(north, west, z)
        px1, py1 = _ll2global_px(south, east, z)
        if max(abs(px1 - px0), abs(py1 - py0)) <= max_px:
            return z
    return zmin


def dem_info(south, north, west, east, zoom) -> dict:
    """预计的网格规模与分辨率（下载前给用户看）。"""
    latc = (south + north) / 2
    px0, py0 = _ll2global_px(north, west, zoom)
    px1, py1 = _ll2global_px(south, east, zoom)
    w, h = int(abs(px1 - px0)), int(abs(py1 - py0))
    dx = 156543.03392 * math.cos(math.radians(latc)) / (2 ** zoom)
    return {"nodes": (w, h), "dx": dx, "tiles": None}


# ============================================================ 下载拼接
def fetch_dem(south: float, north: float, west: float, east: float, zoom: int,
              proxies=None, log=print) -> tuple[np.ndarray, float, dict]:
    """
    下载包围盒内的真实高程，返回 (z2d, dx_m, meta)。

    z2d: 二维高程数组(m)，行 0 = 南（与 landlab/imshow origin=lower 一致）
    dx_m: 网格分辨率（按中心纬度近似的米/格）
    """
    south, north = sorted((float(south), float(north)))
    west, east = sorted((float(west), float(east)))
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("经纬度范围无效（要求 南<北, 西<东）")
    zoom = int(zoom)

    # 全局像素范围
    px0, py0 = _ll2global_px(north, west, zoom)     # 西北角
    px1, py1 = _ll2global_px(south, east, zoom)     # 东南角
    px0, px1 = sorted((px0, px1))
    py0, py1 = sorted((py0, py1))
    w, h = int(px1 - px0), int(py1 - py0)
    if w * h > 1_600_000:
        raise ValueError(f"区域太大: {w}x{h} 格。请缩小范围或降低缩放级别（建议 ≤ 1265x1265）")
    if w < 16 or h < 16:
        raise ValueError(f"区域太小: {w}x{h} 格。请扩大范围或提高缩放级别")

    # 涉及的瓦片
    n = 2 ** zoom
    tx0, tx1 = int(px0 // 256), min(int(px1 // 256), n - 1)
    ty0, ty1 = int(py0 // 256), min(int(py1 // 256), n - 1)
    tiles = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    log(f"下载高程: {w}x{h} 格, {tiles} 个瓦片 (zoom={zoom}) ...")

    canvas = np.full((256 * (ty1 - ty0 + 1), 256 * (tx1 - tx0 + 1)), np.nan)
    proxies = make_proxies(proxies)
    fetched = 0
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            try:
                r = requests.get(_TILE_URL.format(z=zoom, x=tx, y=ty),
                                 proxies=proxies, timeout=25)
                r.raise_for_status()
            except requests.exceptions.Timeout as e:
                raise ConnectionError("高程下载超时（可配置代理，如 http://127.0.0.1:7890）") from e
            except requests.exceptions.RequestException as e:
                raise ConnectionError(f"高程下载失败: {e}") from e
            from PIL import Image
            img = np.asarray(Image.open(io.BytesIO(r.content)).convert("RGB"),
                             dtype=np.float64)
            elev = img[..., 0] * 256 + img[..., 1] + img[..., 2] / 256 - 32768
            canvas[(ty - ty0) * 256:(ty - ty0 + 1) * 256,
                   (tx - tx0) * 256:(tx - tx0 + 1) * 256] = elev
            fetched += 1
            if fetched % 6 == 0:
                log(f"  已下载 {fetched}/{tiles} 个瓦片")

    # 按 bbox 裁剪（全局像素 -> 画布内偏移）
    ox, oy = px0 - tx0 * 256, py0 - ty0 * 256
    z2d = canvas[int(oy):int(oy) + h, int(ox):int(ox) + w].copy()
    if np.isnan(z2d).all():
        raise ConnectionError("下载区域无高程数据（可能全部是海洋）")
    nan_ratio = float(np.isnan(z2d).mean())
    if nan_ratio > 0:
        med = np.nanmedian(z2d)
        z2d = np.where(np.isnan(z2d), med, z2d)     # 少量空洞用中位数填补
        log(f"  已填补 {nan_ratio * 100:.1f}% 的空洞（海洋/无数据）")

    z2d = np.flipud(z2d)          # 行 0 = 南，与 landlab 一致
    latc = (south + north) / 2
    dx = 156543.03392 * math.cos(math.radians(latc)) / n
    meta = {"south": south, "north": north, "west": west, "east": east,
            "zoom": zoom, "dx_m": dx, "shape": [h, w],
            "source": "AWS Terrarium (SRTM/Copernicus)"}
    log(f"高程就绪: {h}x{w} 格, 分辨率≈{dx:.1f} m/格, "
        f"高程 {np.nanmin(z2d):.0f}~{np.nanmax(z2d):.0f} m")
    return z2d, float(dx), meta

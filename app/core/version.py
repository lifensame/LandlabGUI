"""
版本定义与语义化版本比对工具。
"""

from __future__ import annotations
import re

__version__ = "2.1.0"


def parse_version(v_str: str) -> tuple[int, ...]:
    """
    将版本字符串 (如 'v2.1.0', '2.0.1-beta', 'v3.0') 解析为整数元组以供比较。
    """
    if not v_str:
        return (0, 0, 0)
    cleaned = v_str.strip().lstrip("vV")
    nums = re.findall(r"\d+", cleaned)
    if not nums:
        return (0, 0, 0)
    parts = [int(n) for n in nums[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer(remote_v: str, local_v: str = __version__) -> bool:
    """判断 remote_v 是否比 local_v 更新。"""
    return parse_version(remote_v) > parse_version(local_v)

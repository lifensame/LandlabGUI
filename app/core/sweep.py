"""
参数扫描批量实验：固定其他条件，对一个组件参数取一系列值分别完整跑一遍，
收集每次的最终统计与坡度-面积分箱曲线，供 GUI 对比绘图与导出 CSV。
"""

from __future__ import annotations

import copy

import numpy as np

from .engine import Engine
from .i18n import tr
from .workspace import Workspace


def find_numeric_param(base_wf: dict, step_id: str, param_name: str):
    """校验 step/param 存在且为数值类型，返回其当前值。"""
    for s in base_wf.get("steps", []):
        if s.get("id") == step_id:
            v = (s.get("params") or {}).get(param_name)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise ValueError(f"参数 {param_name} 不是数值，无法扫描")
            return v
    raise ValueError(f"找不到步骤 {step_id}")


def make_values(lo: float, hi: float, n: int, log_scale: bool = False) -> list:
    """生成扫描值序列（线性/对数）。"""
    n = max(2, int(n))
    if log_scale:
        if lo <= 0 or hi <= 0:
            raise ValueError("对数扫描要求参数值 > 0")
        return list(np.geomspace(lo, hi, n))
    return list(np.linspace(lo, hi, n))


def run_sweep(base_wf: dict, step_id: str, param_name: str, values: list,
              plugins: dict, log=print, progress=None, stop=None) -> list:
    """
    对每个 value 深拷贝工作流并完整运行，返回结果列表::

        [{"value": v, "mean": .., "max": .., "min": .., "relief": ..,
          "z2d": 降采样二维数组(缩略图), "sa": (面积, 坡度) 分箱曲线或 None}]

    stop: callable() -> bool，返回 True 时中断扫描（已完成的结果照常返回）。
    """
    import logging
    logging.disable(logging.WARNING)
    try:
        find_numeric_param(base_wf, step_id, param_name)
        if not base_wf.get("grid"):
            raise ValueError("参数扫描要求工作流包含网格配置（载入预设后即可扫描）；"
                             "当前工作流沿用交互网格，无法复现建网格")
        results = []
        total = len(values)
        for i, val in enumerate(values):
            if progress:
                progress(i, total)
            if stop is not None and stop():
                log(tr("扫描在第 {0}/{1} 组前被取消").format(i + 1, total))
                break
            log(tr("--- 扫描 {0}/{1}: {2} = {3} ---").format(i + 1, total, param_name, f"{val:.4g}"))
            try:
                wf = copy.deepcopy(base_wf)
                wf.pop("outputs", None)            # 扫描过程不落盘导出
                wf["name"] = f"扫描[{param_name}={val:.4g}]"
                base_val = find_numeric_param(base_wf, step_id, param_name)
                typed_val = float(val) if isinstance(base_val, float) else \
                    (int(round(val)) if isinstance(base_val, int) else val)
                for s in wf.get("steps", []):
                    if s.get("id") == step_id:
                        s.setdefault("params", {})[param_name] = typed_val

                ws = Workspace()
                ws.log_fn = lambda *_: None        # 静默
                quiet_log = lambda *_: None
                eng = Engine(ws, plugins, log=quiet_log)
                eng.run(wf)

                z = np.asarray(ws.at_node["topographic__elevation"], dtype=float)
                if not np.isfinite(z).all():
                    raise ValueError("高程场出现 NaN/Inf（参数组合不稳定）")
                from .plots import slope_area_binned
                shape = getattr(ws.grid, "shape", None)
                if shape and len(shape) == 2:
                    step = max(1, int(np.ceil(max(shape) / 120)))
                    z2d = z.reshape(shape)[::step, ::step]
                else:
                    z2d = z[: 120 * 120].reshape(120, -1) if z.size >= 14400 else \
                        z.reshape(1, -1)
                results.append({
                    "value": float(val),
                    "mean": float(np.nanmean(z)),
                    "max": float(np.nanmax(z)),
                    "min": float(np.nanmin(z)),
                    "relief": float(np.nanmax(z) - np.nanmin(z)),
                    "z2d": z2d.astype(np.float32),
                    "sa": slope_area_binned(ws),
                })
            except Exception as e:
                # 单组失败不中止扫描：记录并继续（结果列表里少一组）
                log(tr("扫描 {0} = {1} 失败，已跳过: {2}").format(
                    param_name, f"{val:.4g}", f"{type(e).__name__}: {e}"))
        if progress:
            progress(total, total)
        log(tr("扫描完成: {0} 共 {1} 组").format(param_name, total))
        return results
    finally:
        logging.disable(logging.NOTSET)

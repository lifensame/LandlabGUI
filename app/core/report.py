"""
一键实验报告：把当前状态（网格/字段/工作流参数/统计）输出为
Markdown + PNG 图组，可直接预览或贴进论文/作业。
"""

from __future__ import annotations

import datetime
import os

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure

import numpy as np

from . import plots
from .workspace import Workspace

matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False


def _fig():
    f = Figure(figsize=(7, 5.2), dpi=120)
    f.add_subplot(111)
    return f


def generate_report(ws: Workspace, wf: dict, out_dir: str, log=print) -> str:
    """生成 实验报告.md + 一组 PNG，返回 md 路径。"""
    if not ws.has_grid:
        raise RuntimeError("尚无网格，无法生成报告")
    os.makedirs(out_dir, exist_ok=True)
    g = ws.grid
    z = ws.at_node.get("topographic__elevation")

    # ---- 图组 ----
    imgs = []
    if z is not None:
        f = _fig()
        plots.draw_field(f.axes[0], g, z, colorbar_fig=f)
        f.axes[0].set_title("最终地形")
        p = os.path.join(out_dir, "report_terrain.png")
        f.savefig(p, bbox_inches="tight")
        imgs.append(("最终地形", "report_terrain.png"))
        del f

    f = _fig()
    plots.draw_slope_area(f.axes[0], ws)
    p = os.path.join(out_dir, "report_slope_area.png")
    f.savefig(p, bbox_inches="tight")
    imgs.append(("坡度-面积", "report_slope_area.png"))
    del f

    f = _fig()
    plots.draw_river_profile(f.axes[0], ws)
    p = os.path.join(out_dir, "report_profile.png")
    f.savefig(p, bbox_inches="tight")
    imgs.append(("河道纵剖面", "report_profile.png"))
    del f

    if ws.history:
        f = _fig()
        plots.draw_history(f.axes[0], ws)
        p = os.path.join(out_dir, "report_history.png")
        f.savefig(p, bbox_inches="tight")
        imgs.append(("演化历史", "report_history.png"))
        del f

    # ---- 统计表 ----
    lines = [f"# Landlab 模拟实验报告",
             "",
             f"> 生成时间：{datetime.datetime.now():%Y-%m-%d %H:%M:%S}",
             "",
             "## 工作流配置",
             ""]
    lines.append(f"- 工作流名称: {wf.get('name', '未命名')}")
    if wf.get("grid"):
        lines.append(f"- 网格: {wf['grid'].get('type')} {wf['grid'].get('params', '')}")
    if wf.get("terrain"):
        lines.append(f"- 初始地形: {wf['terrain']}")
    if wf.get("time"):
        lines.append(f"- 时间: dt={wf['time'].get('dt')} yr × "
                     f"{wf['time'].get('n_steps')} 步 "
                     f"(共 {wf['time'].get('dt', 0) * wf['time'].get('n_steps', 0):.3g} yr)")
    lines.append("")
    lines.append("## 处理步骤")
    lines.append("")
    lines.append("| # | 类型 | 名称 | 执行时机 | 关键参数 |")
    lines.append("|---|------|------|----------|----------|")
    for i, s in enumerate(wf.get("steps", []), 1):
        name = s.get("component") or s.get("plugin")
        params = s.get("params", {})
        ptxt = ", ".join(f"{k}={_fmt(v)}" for k, v in list(params.items())[:6])
        if len(params) > 6:
            ptxt += ", ..."
        when = {"every_step": "每步", "once_at_start": "开始", "once_at_end": "结束"}.get(
            s.get("when", "every_step"))
        kind = "组件" if s.get("kind") == "component" else "插件"
        lines.append(f"| {i} | {kind} | {name} | {when} | {ptxt} |")

    lines += ["", "## 结果统计", ""]
    if z is not None:
        lines.append("| 指标 | 数值 |")
        lines.append("|---|---|")
        lines.append(f"| 节点数 | {g.number_of_nodes} |")
        lines.append(f"| 平均高程 | {np.nanmean(z):.2f} m |")
        lines.append(f"| 最大高程 | {np.nanmax(z):.2f} m |")
        lines.append(f"| 最小高程 | {np.nanmin(z):.2f} m |")
        lines.append(f"| 地形起伏 | {np.nanmax(z) - np.nanmin(z):.2f} m |")
        if "drainage_area" in ws.at_node:
            a = ws.at_node["drainage_area"]
            lines.append(f"| 最大汇水面积 | {np.nanmax(a):.3g} m² |")
        if "channel__chi_index" in ws.at_node:
            lines.append(f"| χ 指数最大值 | {np.nanmax(ws.at_node['channel__chi_index']):.3g} |")
    if ws.history:
        lines.append("")
        lines.append(f"- 实际运行 {ws.history[-1][0]} 步（含中断）")

    lines += ["", "## 图件", ""]
    for title, fn in imgs:
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"![{title}]({fn})")
        lines.append("")

    md_path = os.path.join(out_dir, "实验报告.md")
    with open(md_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))
    log(f"实验报告已生成: {md_path}（含 {len(imgs)} 张图）")
    return md_path


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)

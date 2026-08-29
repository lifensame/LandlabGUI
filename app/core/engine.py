"""
执行引擎：把工作流 JSON 变成一次真实的 landlab 模拟。
====================================================

工作流 JSON 结构（version 1）::

    {
      "version": 1,
      "name": "青藏场景",
      "grid":  {"type": "RasterModelGrid", "params": {...}},     # 可省略=沿用当前网格
      "terrain": {"mode": "noise", "amplitude": 10, "slope": 0.01, "slope_dir": "S", "seed": 42},
      "boundary": "south_open" | "all_closed" | "default",
      "time": {"dt": 250.0, "n_steps": 800, "refresh_every": 10, "history_every": 5},
      "steps": [
        {"id": "s1", "kind": "component", "component": "FastscapeEroder",
         "params": {...}, "when": "every_step"},     # every_step | once_at_start | once_at_end
        {"id": "p1", "kind": "plugin", "plugin": "青藏高原式抬升",
         "params": {...}, "when": "every_step"}
      ],
      "outputs": {"dir": "results", "formats": ["ascii", "netcdf"], "river_min_area": 1e5}
    }

引擎职责：
1. 建网格 / 初始地形 / 边界条件（或沿用 Workspace 现有网格）
2. 实例化组件前按 _info 自动补齐必填字段
3. 时间循环：every_step 步骤按列表顺序逐步执行，进度/日志/高程快照通过回调抛出
4. 循环结束跑 once_at_end（分析类组件），再按需导出
5. stop_flag 置真则安全中断
"""

from __future__ import annotations

import os
import traceback

import numpy as np

import landlab.components as llc
from landlab import (RasterModelGrid, HexModelGrid, VoronoiDelaunayGrid,
                     RadialModelGrid, FramedVoronoiGrid, IcosphereGlobalGrid)
from landlab.io import esri_ascii

from .i18n import tr
from .introspection import _json_safe

_GRID_CLASSES = {
    "RasterModelGrid": RasterModelGrid,
    "HexModelGrid": HexModelGrid,
    "VoronoiDelaunayGrid": VoronoiDelaunayGrid,
    "RadialModelGrid": RadialModelGrid,
    "FramedVoronoiGrid": FramedVoronoiGrid,
    "IcosphereGlobalGrid": IcosphereGlobalGrid,
}


class Engine:
    """无状态执行器：run(workflow, workspace, callbacks) 一次调用完成一次模拟。"""

    def __init__(self, workspace, plugins: dict, log=print, progress=None,
                 snapshot=None, stop_flag=None):
        """
        workspace : Workspace（提供 grid 与日志）
        plugins   : {插件名: PluginSpec}
        progress  : callable(当前步, 总步数)
        snapshot  : callable() 每次刷新时取高程数组副本回调（worker 里发信号）
        stop_flag : 有 .stop 属性的对象或 callable，返回 bool
        """
        self.ws = workspace
        self.plugins = plugins
        self._log = log
        self._progress = progress or (lambda i, n: None)
        self._snapshot = snapshot or (lambda: None)
        self._stop = stop_flag or (lambda: False)

    # -------------------------------------------------- 工具
    def _stopped(self) -> bool:
        v = self._stop
        return v() if callable(v) else bool(getattr(v, "stop", False))

    def log(self, msg: str):
        self._log(msg)

    # -------------------------------------------------- 主入口
    def run(self, wf: dict):
        log = self.log
        ws = self.ws
        log(tr("=== 开始运行工作流: {0} ===").format(wf.get("name", "未命名")))

        # 1) 网格
        if wf.get("grid"):
            self._build_grid(wf["grid"])
        if not ws.has_grid:
            raise RuntimeError("尚无网格：请先新建网格或在工作流中包含 grid 配置")
        if wf.get("boundary"):
            self._apply_boundary(wf["boundary"])
        if wf.get("terrain"):
            ws.init_terrain(**wf["terrain"])

        # 2) 解析步骤
        steps = wf.get("steps", [])
        time_cfg = wf.get("time", {})
        dt = float(time_cfg.get("dt", 1.0))
        n_steps = int(time_cfg.get("n_steps", 1))
        refresh_every = max(1, int(time_cfg.get("refresh_every", 10)))
        history_every = max(1, int(time_cfg.get("history_every", 5)))

        start_steps = [s for s in steps if s.get("when") == "once_at_start"]
        loop_steps = [s for s in steps if s.get("when", "every_step") == "every_step"]
        end_steps = [s for s in steps if s.get("when") == "once_at_end"]
        log(tr("步骤: 启动前 {0} | 循环 {1} | 结束 {2} | dt={3} x {4} 步").format(
            len(start_steps), len(loop_steps), len(end_steps), dt, n_steps))

        comps = {}
        try:
            # 3) 启动前一次性步骤
            for s in start_steps:
                self._exec_step(s, comps)

            # 4) 时间循环
            z0 = ws.at_node["topographic__elevation"]
            for i in range(n_steps):
                if self._stopped():
                    log(tr("用户中断于第 {0}/{1} 步").format(i + 1, n_steps))
                    break
                for s in loop_steps:
                    self._exec_step(s, comps, dt=dt)
                if (i + 1) % history_every == 0 or i == 0:
                    z = ws.at_node["topographic__elevation"]
                    ws.history.append((i + 1, float(np.nanmean(z)), float(np.nanmax(z))))
                if (i + 1) % refresh_every == 0 or i == n_steps - 1:
                    self._snapshot()
                self._progress(i + 1, n_steps)

            # 5) 结束分析步骤
            for s in end_steps:
                self._exec_step(s, comps)

            if not self._stopped():
                log(tr("=== 运行完成 ==="))
            z = ws.at_node["topographic__elevation"]
            log(tr("最终地形: 平均 {0} m, 最大 {1} m").format(f"{np.nanmean(z):.1f}", f"{np.nanmax(z):.1f}"))
            self._snapshot()

            # 6) 导出
            if wf.get("outputs", {}).get("dir") and not self._stopped():
                self._export(wf["outputs"])
        except Exception:
            log(tr("运行出错") + ":\n" + traceback.format_exc())
            raise
        finally:
            ws.components = comps

    # -------------------------------------------------- 网格与边界
    def _build_grid(self, cfg: dict):
        gtype = cfg.get("type", "RasterModelGrid")
        params = dict(cfg.get("params", {}))
        if cfg.get("dem_file"):
            self._load_dem(cfg["dem_file"])
            return
        # VoronoiDelaunayGrid：由 GUI 传来的抽象参数展开为随机 x/y 点位
        if "__npts__" in params:
            import numpy as _np
            npts = int(params.pop("__npts__", 400))
            width = float(params.pop("__width__", 10000.0))
            height = float(params.pop("__height__", 8000.0))
            rng = _np.random.default_rng(42)
            params["x"] = rng.uniform(0, width, npts)
            params["y"] = rng.uniform(0, height, npts)
        cls = _GRID_CLASSES.get(gtype)
        if cls is None:
            raise ValueError(f"未知网格类型: {gtype}")
        grid = cls(**params)
        grid.add_zeros("topographic__elevation", at="node")
        shown = {k: (f"<数组 {len(v)} 点>" if isinstance(v, np.ndarray) else v)
                 for k, v in params.items()}
        self.ws.set_grid(grid, {"type": gtype, "params": shown})
        self.log(tr("新网格: {0}, 节点数 {1}").format(gtype, grid.number_of_nodes))

    def _load_dem(self, path: str):
        with open(path) as f:
            grid = esri_ascii.load(f, at="node", name="topographic__elevation")
        self.ws.set_grid(grid, {"type": "RasterModelGrid(来自DEM)", "params": {"dem": path}})
        self.log(tr("DEM 已导入: {0} ({1} 节点)").format(path, grid.number_of_nodes))

    def _apply_boundary(self, mode: str):
        g = self.ws.grid
        if not hasattr(g, "status_at_node") or not hasattr(g, "set_closed_boundaries_at_grid_edges"):
            self.log("  (skip boundary: unsupported grid)")
            return
        if mode == "all_closed":
            g.set_closed_boundaries_at_grid_edges(True, True, True, True)
            self.log(tr("边界: 四周封闭"))
        elif mode == "south_open":
            g.set_closed_boundaries_at_grid_edges(True, True, True, True)
            bottom = np.where(g.node_y == g.node_y.min())[0]
            g.status_at_node[bottom] = 1        # 1=固定值(开放出水口)
            self.log(tr("边界: 四周封闭 + 南缘开放出水口（教程默认）"))

    # -------------------------------------------------- 步骤执行
    def _exec_step(self, step: dict, comps: dict, dt: float = None):
        kind = step.get("kind", "component")
        if kind == "component":
            self._run_component(step, comps, dt)
        elif kind == "plugin":
            self._run_plugin(step)

    def _run_component(self, step: dict, comps: dict, dt: float = None):
        name = step["component"]
        sid = step.get("id", name)
        params = step.get("params", {}) or {}
        cls = getattr(llc, name, None)
        if cls is None:
            raise ValueError(f"landlab 中找不到组件: {name}")

        # 自动补必填输入字段（_info 的键即字段名）
        for fname, finfo in getattr(cls, "_info", {}).items():
            if ("in" in finfo.get("intent", "") and not finfo.get("optional", False)
                    and finfo.get("mapping", "node") == "node"):
                dtype = finfo.get("dtype", float)
                if fname not in self.ws.grid.at_node:
                    self.ws.ensure_field(fname, "node", dtype)

        if sid not in comps:
            comps[sid] = cls(self.ws.grid, **params)
            self.log(tr("实例化组件 {0} (id={1})").format(name, sid))

        style = step.get("step_style") or self._detect_style(cls)
        comp = comps[sid]
        if style == "analysis":
            self._run_analysis(comp, name)
            return
        method = getattr(comp, style, None)
        if method is None:
            raise RuntimeError(f"组件 {name} 缺少步进方法 {style}")
        # 有的组件 run_one_step() 不接收 dt（如 PriorityFloodFlowRouter），按签名分派
        import inspect as _inspect
        try:
            sig = _inspect.signature(method)
            accepts_dt = ("dt" in sig.parameters or
                          any(p.kind == p.VAR_POSITIONAL for p in sig.parameters.values()))
        except (TypeError, ValueError):
            accepts_dt = True
        if style == "run_one_step_basic" or accepts_dt:
            method(dt)
        else:
            method()

    @staticmethod
    def _detect_style(cls) -> str:
        import inspect
        if hasattr(cls, "run_one_step_basic"):
            return "run_one_step_basic"
        if hasattr(cls, "run_one_step"):
            return "run_one_step"
        if hasattr(cls, "update"):
            return "update"
        return "analysis"

    def _run_analysis(self, comp, name: str):
        """分析类组件：依次尝试 calculate_* / calc_* 方法，再回退 run_one_step()。"""
        candidates = [m for m in dir(comp) if m.startswith(("calculate_", "calc_"))]
        for m in candidates:
            try:
                getattr(comp, m)()
                self.log(tr("分析完成: {0}.{1}()").format(name, m))
                return
            except TypeError:
                continue          # 需要参数的方法跳过
            except Exception as e:
                self.log(tr("分析 {0}.{1}() 失败: {2}").format(name, m, e))
                return
        if hasattr(comp, "run_one_step"):        # 如 ChannelProfiler
            try:
                comp.run_one_step()
                self.log(tr("分析完成: {0}.run_one_step()").format(name))
                return
            except Exception as e:
                self.log(tr("分析 {0} 运行失败: {1}").format(name, e))
                return
        self.log(tr("分析组件 {0} 无可用计算方法，已实例化（输出字段可直接查看）").format(name))

    def _run_plugin(self, step: dict):
        pname = step["plugin"]
        spec = self.plugins.get(pname)
        if spec is None:
            raise ValueError(f"找不到插件功能: {pname}（是否忘记重载插件？）")
        spec.fn(self.ws, step.get("params", {}) or {})

    # -------------------------------------------------- 导出
    def _export(self, cfg: dict):
        from .exporter import export_all
        from .plugin_loader import app_root
        out_dir = cfg.get("dir", "results")
        if not os.path.isabs(out_dir):
            out_dir = os.path.join(app_root(), out_dir)
        export_all(self.ws.grid, output_dir=out_dir,
                   dem_formats=cfg.get("formats", ["ascii"]),
                   river_min_area=cfg.get("river_min_area", 1e5), log=self.log)


def sanitize_workflow_params(params: dict, schema_params: list = None) -> dict:
    """把 GUI 表单收集的参数转成 landlab 可接受的类型（str数字转数字等）。"""
    out = {}
    typed = {p["name"]: p.get("type") for p in (schema_params or [])}
    for k, v in params.items():
        t = typed.get(k)
        if t in ("float",) and isinstance(v, str):
            out[k] = float(v)
        elif t in ("int",) and isinstance(v, str) and v.strip():
            out[k] = int(float(v))
        else:
            out[k] = v
    return out

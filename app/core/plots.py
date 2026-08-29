"""
纯 matplotlib 绘图函数：画布面板与实验报告共用（不依赖 Qt）。
所有函数接收 Axes/Figure，按当前主题配色绘制。
"""

from __future__ import annotations

import numpy as np

from .i18n import tr


# ---------------------------------------------------------------- 字段渲染
def draw_field(ax, grid, values, cmap="terrain", colorbar_fig=None):
    """
    在 ax 上渲染节点字段（规则网格用 imshow，非规则网格用三角剖分）。
    colorbar_fig 传 Figure 时自动附加 colorbar；返回 mappable 或 None。
    """
    vals = np.asarray(values, dtype=float)
    finite = np.isfinite(vals)
    if not finite.any():
        ax.text(0.5, 0.5, tr("无有效数据"), transform=ax.transAxes,
                ha="center", va="center", color="gray")
        return None
    vmin, vmax = np.nanmin(vals[finite]), np.nanmax(vals[finite])
    shape = getattr(grid, "shape", None)
    m = None
    if shape is not None and len(shape) == 2 and grid.number_of_nodes == shape[0] * shape[1]:
        dx = grid.dx if hasattr(grid, "dx") else 1
        m = ax.imshow(vals.reshape(shape), origin="lower", cmap=cmap,
                      vmin=vmin, vmax=vmax, extent=[0, shape[1] * dx, 0, shape[0] * dx],
                      interpolation="nearest")
    else:
        try:
            x, y = grid.x_of_node, grid.y_of_node
            m = ax.tricontourf(x, y, vals, levels=24, cmap=cmap, vmin=vmin, vmax=vmax)
            ax.set_aspect("equal")
        except Exception:
            ax.text(0.5, 0.5, tr("该网格类型暂不支持二维显示"), transform=ax.transAxes,
                    ha="center", va="center", color="gray")
            return None
    if colorbar_fig is not None and m is not None:
        colorbar_fig.colorbar(m, ax=ax, shrink=0.8)
    return m


def draw_slope_area(ax, ws, color="#3daee9"):
    """坡度-面积散点（对数坐标）。返回 True 表示有数据。"""
    ok = False
    if ws.has_grid and "drainage_area" in ws.at_node \
            and "topographic__elevation" in ws.at_node:
        try:
            slope = ws.grid.calc_slope_at_node()
            a = ws.at_node["drainage_area"]
            m = (a > 1e3) & np.isfinite(slope) & (slope > 0)
            if m.sum() > 10:
                ax.loglog(a[m], slope[m], ".", ms=1.5, alpha=0.35, color=color)
                ax.set_xlabel(tr("汇水面积 A (m²)"))
                ax.set_ylabel(tr("坡度 S"))
                ok = True
        except Exception:
            ok = False
    if not ok:
        ax.text(0.5, 0.5, tr("运行含汇流的组件后显示\n(阈值 A>1e3 m²)"),
                transform=ax.transAxes, ha="center", va="center", color="gray")
    return ok


def slope_area_binned(ws, n_bins=24, a_min=1e3):
    """分箱坡度-面积曲线（用于参数扫描对比）。返回 (面积中位数, 坡度中位数) 或 None。"""
    if not ws.has_grid or "drainage_area" not in ws.at_node:
        return None
    try:
        slope = ws.grid.calc_slope_at_node()
        a = ws.at_node["drainage_area"]
        m = (a > a_min) & np.isfinite(slope) & (slope > 0)
        if m.sum() < 20:
            return None
        edges = np.logspace(np.log10(a_min), np.log10(a[m].max()), n_bins + 1)
        idx = np.digitize(a[m], edges) - 1
        a_med, s_med = [], []
        for b in range(n_bins):
            sel = idx == b
            if sel.sum() >= 3:
                a_med.append(np.sqrt(edges[b] * edges[b + 1]))
                s_med.append(np.median(slope[m][sel]))
        if len(a_med) < 3:
            return None
        return np.array(a_med), np.array(s_med)
    except Exception:
        return None


def draw_river_profile(ax, ws, color="#e05c5c"):
    """最长河道纵剖面（沿 flow__receiver_node 链）。返回 True 表示有数据。"""
    ok = False
    if ws.has_grid and "flow__receiver_node" in ws.at_node \
            and "topographic__elevation" in ws.at_node:
        try:
            g = ws.grid
            z = ws.at_node["topographic__elevation"]
            rec = ws.at_node["flow__receiver_node"]
            if "drainage_area" in ws.at_node:
                a = ws.at_node["drainage_area"].copy()
                if hasattr(g, "status_at_node"):
                    a[np.asarray(g.status_at_node) != 0] = -1.0
                start = int(np.argmax(a))
                path, dist, cur = [start], 0.0, start
                for _ in range(g.number_of_nodes):
                    nxt = int(rec[cur])
                    if nxt == cur:
                        break
                    dist += float(np.hypot(g.x_of_node[nxt] - g.x_of_node[cur],
                                           g.y_of_node[nxt] - g.y_of_node[cur]))
                    path.append(nxt)
                    cur = nxt
                if len(path) > 5:
                    prof = z[path]
                    s = np.linspace(0, dist, len(path))
                    ax.plot(s, prof, lw=1.6, color=color)
                    ax.fill_between(s, prof.min() - 1, prof, alpha=0.12, color=color)
                    ax.set_xlabel(tr("沿程距离 (m)"))
                    ax.set_ylabel(tr("高程 (m)"))
                    ok = True
        except Exception:
            ok = False
    if not ok:
        ax.text(0.5, 0.5, "运行含汇流的组件后显示\n(最长河道纵剖面)",
                transform=ax.transAxes, ha="center", va="center", color="gray")
    return ok


def sample_profile(grid, z, p0, p1, n=300):
    """沿任意两点直线采样高程。返回 (距离数组, 高程数组)。"""
    (x0, y0), (x1, y1) = p0, p1
    length = float(np.hypot(x1 - x0, y1 - y0))
    ts = np.linspace(0, 1, n)
    dists, elevs = [], []
    for t in ts:
        x, y = x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        try:
            node = grid.find_nearest_node((x, y))
        except Exception:
            node = int(np.argmin((grid.x_of_node - x) ** 2 + (grid.y_of_node - y) ** 2))
        dists.append(t * length)
        elevs.append(float(z[node]))
    return np.array(dists), np.array(elevs)


def draw_history(ax, ws):
    """平均/最大高程随步数演化。"""
    if ws.history:
        steps = [h[0] for h in ws.history]
        ax.plot(steps, [h[1] for h in ws.history], lw=1.6, color="#3daee9", label=tr("平均高程"))
        ax.plot(steps, [h[2] for h in ws.history], lw=1.2, ls="--", color="#e05c5c", label=tr("最大高程"))
        ax.set_xlabel(tr("步数"))
        ax.set_ylabel(tr("高程 (m)"))
        ax.legend()
    else:
        ax.text(0.5, 0.5, tr("运行模拟后显示"), transform=ax.transAxes,
                ha="center", va="center", color="gray")


def draw_3d(ax, grid, z, downsample=180):
    """3D 地形曲面（规则网格降采样；非规则网格三角面）。"""
    z = np.asarray(z, dtype=float)
    shape = getattr(grid, "shape", None)
    if shape is not None and len(shape) == 2 and grid.number_of_nodes == shape[0] * shape[1]:
        ny, nx = shape
        step = max(1, int(np.ceil(max(ny, nx) / downsample)))
        zz = z.reshape(shape)[::step, ::step]
        dx = (grid.dx if hasattr(grid, "dx") else 1) * step
        xs = np.arange(zz.shape[1]) * dx
        ys = np.arange(zz.shape[0]) * dx
        X, Y = np.meshgrid(xs, ys)
        surf = ax.plot_surface(X, Y, zz, cmap="terrain", rstride=1, cstride=1,
                               linewidth=0, antialiased=True)
        ax.set_box_aspect((1, ys.max() / max(xs.max(), 1), 0.35))
        return surf
    try:
        x, y = grid.x_of_node, grid.y_of_node
        tri = ax.plot_trisurf(x, y, z, cmap="terrain", linewidth=0, antialiased=True)
        return tri
    except Exception:
        ax.text2D(0.5, 0.5, tr("该网格类型暂不支持3D显示"), transform=ax.transAxes,
                  ha="center", va="center", color="gray")
        return None

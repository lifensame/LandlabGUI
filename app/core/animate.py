"""
演化动画导出：帧序列 -> GIF（Pillow，无额外依赖）或 MP4（需系统 ffmpeg）。
frames: [(z_array_2d, vmin, vmax, 标题str), ...]
"""

from __future__ import annotations

import os
import shutil

import numpy as np
from matplotlib import animation
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def write_animation(frames, path: str, fps: float = 10):
    """
    frames: [(z2d, vmin, vmax, title), ...]
    按 path 后缀选择 GIF / MP4；仅保存部分关键帧以控制文件大小。
    """
    if not frames:
        raise ValueError("没有可用的动画帧（请先运行一次模拟并保持画面刷新≥1次）")
    path = os.path.abspath(path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".mp4" and not ffmpeg_available():
        raise RuntimeError("未找到 ffmpeg，无法导出 MP4；请改用 .gif")

    # 帧数过多时等间隔抽稀到 <=300 帧
    if len(frames) > 300:
        idx = np.linspace(0, len(frames) - 1, 300).astype(int)
        frames = [frames[i] for i in idx]

    fig = Figure(figsize=(6.4, 5.2))
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    z0, vmin, vmax, title0 = frames[0]
    im = ax.imshow(z0, origin="lower", cmap="terrain", vmin=vmin, vmax=vmax,
                   interpolation="nearest")
    ax.set_title(title0)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.colorbar(im, ax=ax, shrink=0.85)
    fig.tight_layout()

    def _update(i):
        z, _, _, title = frames[i]
        im.set_data(z)
        ax.set_title(title)
        return (im,)

    if ext == ".gif":
        writer = animation.PillowWriter(fps=fps)
    else:
        writer = animation.FFMpegWriter(fps=fps, bitrate=4000)
    anim = animation.FuncAnimation(fig, _update, frames=len(frames), blit=False)
    anim.save(path, writer=writer, dpi=110)
    return path

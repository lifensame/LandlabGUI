"""
插件加载器：扫描 plugins/ 文件夹下的 *.py，收集所有 @plugin 标记的函数。
支持热重载（重新扫描并重新导入）。
"""

from __future__ import annotations

import importlib.util
import os
import sys
import traceback

from .api import PluginSpec
from .i18n import tr


def app_root() -> str:
    """应用根目录：开发态=landlab_gui/；打包态=exe 所在目录（插件/预设就在旁边）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def plugins_dir(base: str = None) -> str:
    """返回插件目录的绝对路径（landlab_gui/plugins 或 exe旁/plugins）。"""
    if base is None:
        base = app_root()
    d = os.path.join(base, "plugins")
    os.makedirs(d, exist_ok=True)
    return d


def load_plugins(app_root: str = None, log=print) -> dict:
    """
    扫描并导入插件目录下的所有 .py 文件。

    返回 {插件名: PluginSpec}。单个文件出错不影响其他插件。
    """
    specs: dict[str, PluginSpec] = {}
    d = plugins_dir(app_root)
    for fname in sorted(os.listdir(d)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(d, fname)
        mod_name = f"llg_plugin_{fname[:-3]}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module          # 注册后热重载才能覆盖
            spec.loader.exec_module(module)
            for attr in vars(module).values():
                pspec = getattr(attr, "_llg_plugin_spec", None)
                if isinstance(pspec, PluginSpec):
                    pspec.source_file = path
                    if pspec.name in specs:
                        log(tr("[插件] 重名覆盖: {0} ({1})").format(pspec.name, fname))
                    specs[pspec.name] = pspec
            log(tr("[插件] 已加载 {0}").format(fname))
        except Exception:
            log(tr("[插件] 加载失败 {0}").format(fname) + "\n" + traceback.format_exc(limit=3))
    log(tr("[插件] 共加载 {0} 个自定义功能").format(len(specs)))
    return specs


def write_plugin_template(path: str, name: str, code: str):
    """把代码编辑器中的片段另存为插件文件。

    编辑器运行上下文提供 grid/at_node/np 等顶层变量，但插件函数只收到
    (workspace, params)，因此模板在函数体内注入等价的初始化行。
    """
    body = code if "def " in code else None
    if body:
        # 用户自己定义了函数：原样保留，仅补 import 提示
        template = f'''# 由 Landlab GUI 代码编辑器生成
import numpy as np

from app.core.api import plugin


@plugin(name="{name}", category="自定义", params={{}})
{body}
'''
    else:
        indented = "\n".join(("    " + line) if line.strip() else ""
                             for line in code.strip().splitlines())
        template = f'''# 由 Landlab GUI 代码编辑器生成
import numpy as np

from app.core.api import plugin


@plugin(name="{name}", category="自定义", params={{}})
def run(workspace, params):
    # 与代码编辑器相同的上下文
    grid = workspace.grid
    at_node = grid.at_node if grid is not None else None
{indented}
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(template)

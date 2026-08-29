"""
插件 API：用户插件通过此装饰器把一个函数注册为 GUI 可用功能。
============================================================

示例（保存到 landlab_gui/plugins/ 目录下即可被自动发现）::

    from app.core.api import plugin

    @plugin(name="青藏高原式抬升", category="自定义抬升",
            params={
                "south": {"type": "float", "default": 1e-4, "doc": "南侧抬升速率 m/yr"},
                "north": {"type": "float", "default": 1e-3, "doc": "北侧抬升速率 m/yr"},
            })
    def tibet_uplift(workspace, params):
        z = workspace.grid.at_node["topographic__elevation"]
        ...

函数签名固定为 fn(workspace, params)：
- workspace: app.core.workspace.Workspace，可访问 .grid / .at_node / .log()
- params:    GUI 表单收集的参数 dict

params 中每个参数支持: type(float/int/str/bool/field_ref/array)、default、doc、choices
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PluginSpec:
    """一个插件功能的完整描述。"""
    name: str
    fn: callable
    category: str = "自定义"
    doc: str = ""
    params: dict = field(default_factory=dict)
    source_file: str = ""
    run_in_loop: bool = True      # True=放进时间循环每步执行；False=仅手动执行一次

    def to_dict(self):
        return {"name": self.name, "category": self.category, "doc": self.doc,
                "params": self.params, "source_file": self.source_file,
                "run_in_loop": self.run_in_loop, "kind": "plugin"}


def plugin(name: str = None, category: str = "自定义", params: dict = None,
           doc: str = "", run_in_loop: bool = True):
    """装饰器：把函数标记为 Landlab GUI 插件功能。"""
    def decorator(fn):
        fn._llg_plugin_spec = PluginSpec(
            name=name or fn.__name__,
            fn=fn,
            category=category or "自定义",
            doc=doc or (fn.__doc__ or "").strip(),
            params=params or {},
            run_in_loop=run_in_loop,
        )
        return fn
    return decorator

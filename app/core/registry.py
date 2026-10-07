"""
注册表：内置 landlab 组件 + 用户插件 统一目录。
GUI 左侧组件树与工作流引擎都从这里取条目。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import introspection, plugin_loader


@dataclass
class Entry:
    """目录中的一个可执行功能（内置组件或插件）。"""
    kind: str                    # "component" | "plugin"
    name: str                    # 组件类名 或 插件名
    category: str
    doc: str
    params_def: list = field(default_factory=list)   # 表单定义（component: schema.params）
    schema: dict = None          # component 的完整 schema
    plugin_spec: object = None   # plugin 的 PluginSpec

    @property
    def is_analysis(self) -> bool:
        if self.kind == "plugin":
            return not self.plugin_spec.run_in_loop
        return self.schema and self.schema.get("step_style") == "analysis"


class Registry:
    """启动时扫描一次，"重载插件"时刷新插件部分。"""

    def __init__(self, app_root: str = None, log=print):
        self.log = log
        self.schemas: dict = {}
        self.plugins: dict = {}
        self.entries: dict[str, Entry] = {}
        self.app_root = app_root
        self.reload()

    def reload(self, force_rescan: bool = False):
        self.schemas = introspection.scan_all_components(force=force_rescan)
        self.plugins = plugin_loader.load_plugins(self.app_root, log=self.log)
        self._rebuild()

    def _rebuild(self):
        self.entries = {}
        for name, schema in self.schemas.items():
            self.entries[name] = Entry(
                kind="component", name=name, category=schema.get("category", "其他"),
                doc=schema.get("doc", ""), params_def=schema.get("params", []),
                schema=schema)
        for pname, spec in self.plugins.items():
            params_def = []
            for k, v in (spec.params or {}).items():
                d = dict(v)
                d.setdefault("name", k)
                d.setdefault("type", "float" if isinstance(d.get("default"), float)
                             else "int" if isinstance(d.get("default"), int)
                             else "str")
                params_def.append(d)
            self.entries[pname] = Entry(
                kind="plugin", name=pname, category=spec.category,
                doc=spec.doc, params_def=params_def, plugin_spec=spec)

    def categories(self) -> list:
        cats = list(introspection.categories_of(self.schemas))
        for pname, spec in self.plugins.items():
            if spec.category not in cats:
                cats.append(spec.category)
        return cats

    def entries_in(self, category: str) -> list:
        return sorted([e for e in self.entries.values() if e.category == category],
                      key=lambda e: e.name)

    def get(self, name: str) -> Entry:
        return self.entries.get(name)

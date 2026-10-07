"""
自省引擎：扫描 landlab 全部组件，生成机器可读的参数 schema。
=========================================================

原理（对 landlab 2.11.0 实测验证）：
1. 全部 87 个组件类的构造签名 100% 统一：第一个参数是 grid，其余是带默认值 kwargs
   -> 用 inspect.signature 一次提取所有参数
2. 每个组件有官方元数据 _info：字段名 -> {dtype, intent(in/out), optional, units, mapping, doc}
   -> 用于"输入/输出字段"展示与自动建字段
3. 参数的中文/英文描述在 __init__ 的 numpydoc docstring 里 -> 用 numpydoc 解析

生成的 schema 是纯 JSON 结构，缓存到磁盘（components_cache.json），
GUI 启动时直接读缓存，秒开；landlab 升级或缓存缺失时自动重建。
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import re

import numpy as np

# landlab 的导入较慢（约数秒），在此模块内一次性完成
import landlab.components as _ll_components
from landlab import Component as _Component

# ---------------------------------------------------------------
# 分类：按组件所在模块名映射到中文分类
# ---------------------------------------------------------------
_CATEGORY_RULES = [
    ("flow_accumulator", "水流与汇流"),
    ("flow_director", "水流与汇流"),
    ("lossy_flow", "水流与汇流"),
    ("depression", "洼地处理"),
    ("lake_mapper", "洼地处理"),
    ("sink_filler", "洼地处理"),
    ("priority_flood", "洼地处理"),
    ("stream_power", "河道侵蚀与沉积"),
    ("space", "河道侵蚀与沉积"),
    ("erosion_deposition", "河道侵蚀与沉积"),
    ("sed_dep", "河道侵蚀与沉积"),
    ("shared_stream_power", "河道侵蚀与沉积"),
    ("gravel", "河道侵蚀与沉积"),
    ("area_slope", "河道侵蚀与沉积"),
    ("lateral_erosion", "河道侵蚀与沉积"),
    ("bedrock_landslider", "滑坡与块体运动"),
    ("mass_wasting", "滑坡与块体运动"),
    ("landslide", "滑坡与块体运动"),
    ("hillslope", "坡面过程"),
    ("diffusion", "坡面过程"),
    ("diffuser", "坡面过程"),
    ("detachment", "坡面过程"),
    ("weathering", "风化与土壤"),
    ("soil", "风化与土壤"),
    ("infiltration", "水文与气候"),
    ("overland", "水文与气候"),
    ("kinwave", "水文与气候"),
    ("groundwater", "水文与气候"),
    ("river_flow", "水文与气候"),
    ("discharge", "水文与气候"),
    ("evapotranspiration", "水文与气候"),
    ("precipitation", "水文与气候"),
    ("radiation", "水文与气候"),
    ("soil_moisture", "水文与气候"),
    ("flexure", "构造与地质"),
    ("normal_fault", "构造与地质"),
    ("listric", "构造与地质"),
    ("lithology", "构造与地质"),
    ("carbonate", "构造与地质"),
    ("fracture", "构造与地质"),
    ("vegetation", "生态与扰动"),
    ("fire", "生态与扰动"),
    ("species", "生态与扰动"),
    ("vegca", "生态与扰动"),
    ("submarine", "海岸与海洋"),
    ("tidal", "海岸与海洋"),
    ("chi_finder", "地形分析"),
    ("steepness", "地形分析"),
    ("profiler", "地形分析"),
    ("hack", "地形分析"),
    ("height_above", "地形分析"),
    ("drainage_density", "地形分析"),
    ("parcel", "泥沙粒径初始化"),
    ("network_sediment", "河网泥沙输运"),
    ("concentration_tracker", "示踪与浓度"),
    ("depth_slope", "坡面过程"),
]

# 已知字符串枚举参数的选择项（常用组件的常用枚举，硬编码提升体验）
_KNOWN_CHOICES = {
    "flow_director": ["FlowDirectorSteepest", "FlowDirectorD8",
                      "FlowDirectorMFD", "FlowDirectorDINF"],
    "flow_metric": ["D8", "D4", "MFD", "DINF"],
    "depression_handler": ["fill", "breach", "route"],
    "routing": ["D8", "D4", "MFD", "DINF"],
    "method": ["simple", "complex"],
    "uplift_mode": ["uniform", "tibet", "gradient", "two_block"],
    "dtype": ["float", "int"],
}

# 组件名 -> 中文说明（精选常用组件，未列出的显示官方英文 docstring）
_ZH_DOC = {
    "FastscapeEroder": "快速基岩河道侵蚀（BMP模型，教程默认，需先运行汇流）",
    "StreamPowerEroder": "河流功率侵蚀 E=K·A^m·S^n（经典实现）",
    "StreamPowerSmoothThresholdEroder": "带平滑阈值的河流功率侵蚀（阈值附近可导，数值稳定）",
    "Space": "SPACE 基岩-沉积耦合侵蚀模型（Shobe 2017，教程v1）",
    "SpaceLargeScaleEroder": "SPACE 大尺度加速版（教程v2，配合 PriorityFloodFlowRouter）",
    "ErosionDeposition": "侵蚀-沉积模型（ErosionDeposition，含沉积再搬运）",
    "LinearDiffuser": "线性坡面扩散（土壤蠕动夷平，教程全程使用）",
    "DepthDependentDiffuser": "深度依赖坡面扩散（土壤层厚度相关）",
    "PriorityFloodFlowRouter": "优先洪水汇流路由（自动填洼，教程v2核心，一步完成汇流）",
    "FlowAccumulator": "汇流累积器（可选拦截洼地，最常用的水流组件）",
    "DepressionFinderAndRouter": "洼地查找与路由（经典填洼方法）",
    "ChiFinder": "χ 指数计算（河道不平衡分析）",
    "SteepnessFinder": "陡峭指数 ksn 计算",
    "ChannelProfiler": "河道纵剖面提取",
    "Profiler": "任意轨迹剖面（沿最小坡度路径）",
    "NormalFault": "正断层（块状抬升/下降）",
    "Flexure": "岩石圈挠曲（3D荷载响应）",
    "Lithology": "岩性层管理（多层岩石性质）",
    "PrecipitationDistribution": "降水事件生成器（随机暴雨序列）",
    "OverlandFlow": "二维运动波地表径流",
    "GroundwaterDupuitPercolator": "Dupuit 地下水渗流",
    "SoilInfiltrationGreenAmpt": "Green-Ampt 入渗模型",
    "LandslideProbability": "滑坡概率（ infinite slope 安全系数）",
    "GravelBedrockEroder": "砾石-基岩侵蚀（含砾石输运）",
    "GravelRiverTransporter": "砾石河流输运",
    "BedrockLandslider": "基岩滑坡（随机滑坡事件）",
    "ExponentialWeatherer": "指数风化（土壤生产函数）",
}

_VAR_KW_EXTRA = {
    # FlowAccumulator 家族的 **kwargs 实际是 flow_director/depression_finder 选项，
    # 硬编码成二级选项页，让表单体验和其他组件一致
    "FlowAccumulator": [
        {"name": "flow_director", "type": "str", "default": "FlowDirectorSteepest",
         "choices": _KNOWN_CHOICES["flow_director"], "doc": "流向算法"},
        {"name": "depression_finder", "type": "str", "default": "DepressionFinderAndRouter",
         "doc": "洼地处理器（留空则不处理洼地）", "optional": True},
    ],
    "LossyFlowAccumulator": [
        {"name": "flow_director", "type": "str", "default": "FlowDirectorSteepest",
         "choices": _KNOWN_CHOICES["flow_director"], "doc": "流向算法"},
    ],
}


def _iter_component_classes():
    """枚举 landlab.components 命名空间下的全部组件类（CLI `landlab list` 同款做法）。"""
    for name in dir(_ll_components):
        obj = getattr(_ll_components, name)
        if (inspect.isclass(obj) and issubclass(obj, _Component)
                and obj is not _Component and obj.__module__.startswith("landlab")):
            yield name, obj


def _categorize(cls) -> str:
    module = cls.__module__.lower()
    for key, cat in _CATEGORY_RULES:
        if key in module:
            return cat
    return "其他"


def _json_safe(default):
    """把默认值转成可 JSON 序列化的形式（函数/numpy类型等特殊值转字符串标记）。"""
    if default is None or isinstance(default, (bool, int, float, str)):
        return default
    if isinstance(default, (list, tuple)):
        return [_json_safe(v) for v in default]
    if isinstance(default, np.ndarray):
        return default.tolist()
    if isinstance(default, dict):
        return {str(k): _json_safe(v) for k, v in default.items()}
    if callable(default):
        return "__callable__"
    if isinstance(default, (np.integer,)):
        return int(default)
    if isinstance(default, (np.floating,)):
        return float(default)
    return f"__{type(default).__name__}__"


def _infer_type(default):
    """从默认值推断表单控件类型。"""
    if default is None:
        return "none"          # 可为空，渲染为"可留空"文本框
    if isinstance(default, bool):
        return "bool"
    if isinstance(default, int):
        return "int"
    if isinstance(default, float):
        return "float"
    if isinstance(default, str):
        return "str"
    if isinstance(default, (list, tuple, np.ndarray)):
        return "array"
    if isinstance(default, dict):
        return "dict"
    return "json"              # callable / 对象等，回退 JSON 文本框


def _parse_param_docs(cls):
    """用 numpydoc 解析 __init__ docstring，返回 {参数名: 描述}。"""
    import warnings
    docs = {}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from numpydoc.docscrape import NumpyDocString
            doc = NumpyDocString(inspect.getdoc(cls.__init__) or "")
            for pname, *desc_lines in doc.get("Parameters", []):
                desc = " ".join(s.strip() for s in desc_lines if s.strip())
                docs[pname.strip()] = desc
    except Exception:
        pass
    # 回退：类 docstring 的 Parameters 段（部分组件写在类上）
    if not docs:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from numpydoc.docscrape import NumpyDocString
                doc = NumpyDocString(inspect.getdoc(cls) or "")
                for pname, *desc_lines in doc.get("Parameters", []):
                    desc = " ".join(s.strip() for s in desc_lines if s.strip())
                    docs[pname.strip()] = desc
        except Exception:
            pass
    return docs


def _detect_step_style(cls) -> str:
    """判定步进方式：run_one_step / update / run_one_step_basic / analysis(一次性)。"""
    if "run_one_step" in cls.__dict__ or any(
            "run_one_step" == m for m in dir(cls)):
        for m in ("run_one_step", "run_one_step_basic"):
            fn = getattr(cls, m, None)
            if fn is not None and getattr(fn, "__module__", "").startswith("landlab"):
                return m
    if hasattr(cls, "update") and "update" in cls.__dict__:
        return "update"
    # 没有时间步进 -> 分析类，一次性计算
    return "analysis"


def _clean_doc(text: str) -> str:
    """截断 docstring，去掉多余换行。"""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300]


def build_schema(cls, name: str) -> dict:
    """为单个组件类生成完整 schema（纯 JSON 可序列化）。"""
    param_docs = _parse_param_docs(cls)

    params = []
    sig = inspect.signature(cls.__init__)
    for pname, p in list(sig.parameters.items())[1:]:  # 跳过 self / grid
        if p.kind in (p.VAR_POSITIONAL,):
            continue
        if p.kind == p.VAR_KEYWORD:
            # **kwargs 组件：如有硬编码二级选项则展开，否则留"额外JSON"入口
            # （先跳过签名里已具名出现的参数，避免重复注入 FlowAccumulator 等）
            seen = {q["name"] for q in params}
            for extra in _VAR_KW_EXTRA.get(name, []):
                if extra["name"] not in seen:
                    params.append(extra)
            if name not in _VAR_KW_EXTRA:
                params.append({"name": "__extra_kwargs__", "type": "dict",
                               "default": {}, "doc": "额外关键字参数(JSON)"})
            continue
        if pname == "grid":
            continue
        default = p.default if p.default is not inspect._empty else None
        ftype = _infer_type(default)
        entry = {"name": pname, "type": ftype, "default": _json_safe(default),
                 "doc": _clean_doc(param_docs.get(pname, ""))}
        if pname in _KNOWN_CHOICES and ftype in ("str", "none"):
            entry["choices"] = _KNOWN_CHOICES[pname]
        # 字段引用参数：名字以 _field/_fields 结尾的字符串参数
        if ftype in ("str", "none") and pname.endswith(("_field", "_fields")):
            entry["type"] = "field_ref"
        params.append(entry)

    fields_in, fields_out = [], []
    info = getattr(cls, "_info", {}) or {}
    for fname, meta in info.items():
        item = {"name": fname,
                "dtype": getattr(meta.get("dtype"), "__name__", str(meta.get("dtype"))),
                "intent": meta.get("intent", ""),
                "optional": bool(meta.get("optional", False)),
                "units": meta.get("units", "") or "",
                "mapping": meta.get("mapping", "node"),
                "doc": _clean_doc(meta.get("doc", ""))}
        if "in" in item["intent"]:
            fields_in.append(item)
        if "out" in item["intent"]:
            fields_out.append(item)

    doc_attr = _ZH_DOC.get(name, "")
    summary = _clean_doc(inspect.getdoc(cls) or "")
    if doc_attr:
        summary = doc_attr + (" ｜ " + summary if summary else "")

    return {
        "name": name,
        "module": cls.__module__,
        "category": _categorize(cls),
        "doc": summary,
        "params": params,
        "input_fields": fields_in,
        "output_fields": fields_out,
        "step_style": _detect_step_style(cls),
        "cite_as": getattr(cls, "cite_as", "") or "",
        "unit_agnostic": bool(getattr(cls, "unit_agnostic", True)),
    }


def scan_all_components(force: bool = False) -> dict:
    """扫描全部组件，返回 {组件名: schema}；带磁盘缓存。

    缓存文件结构: {"_meta": {"landlab_version": ...}, "components": {...}}；
    landlab 版本不一致时视为过期自动重建（否则升级后表单与真实签名不符）。
    """
    cache_path = os.path.join(os.path.dirname(__file__), "components_cache.json")
    this_version = getattr(_ll_components, "__landlab_version__", None) or         getattr(importlib.import_module("landlab"), "__version__", "unknown")
    if not force and os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            comps = cache.get("components", {})
            meta_ok = cache.get("_meta", {}).get("landlab_version") == this_version
            if meta_ok and len(comps) >= 80:
                return comps
        except Exception:
            pass
    schemas = {}
    for name, cls in _iter_component_classes():
        try:
            schemas[name] = build_schema(cls, name)
        except Exception as e:    # 单个组件失败不阻塞整体
            schemas[name] = {"name": name, "module": cls.__module__,
                             "category": "其他", "doc": f"schema生成失败: {e}",
                             "params": [], "input_fields": [], "output_fields": [],
                             "step_style": "analysis", "cite_as": "",
                             "unit_agnostic": True, "broken": True}
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"_meta": {"landlab_version": this_version,
                                  "generated": __import__("time").strftime("%Y-%m-%d")},
                       "components": schemas},
                      f, ensure_ascii=False, indent=1)
    except OSError:
        pass
    return schemas


def categories_of(schemas: dict) -> list:
    """按固定顺序返回出现过的分类列表。"""
    order = ["水流与汇流", "洼地处理", "河道侵蚀与沉积", "坡面过程", "风化与土壤",
             "水文与气候", "滑坡与块体运动", "构造与地质", "生态与扰动", "海岸与海洋",
             "河网泥沙输运", "示踪与浓度", "泥沙粒径初始化", "地形分析", "其他"]
    seen = {s.get("category", "其他") for s in schemas.values()}
    return [c for c in order if c in seen] + sorted(seen - set(order))


if __name__ == "__main__":
    ss = scan_all_components(force=True)
    print(f"共生成 {len(ss)} 个组件 schema")
    from collections import Counter
    print(Counter(s["category"] for s in ss.values()))
    print(Counter(s["step_style"] for s in ss.values()))

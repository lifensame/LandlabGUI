"""
自省引擎单元测试：断言全部 landlab 组件都能生成有效 schema。
运行:  python -m pytest tests/ -v    或    python tests/test_introspection.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.introspection import (build_schema, categories_of,  # noqa: E402
                                    scan_all_components)


def test_all_components_have_schema():
    schemas = scan_all_components()
    assert len(schemas) >= 80, f"组件数异常: {len(schemas)}"
    for name, s in schemas.items():
        assert s["name"] == name
        assert s["category"], f"{name} 缺分类"
        assert s["step_style"] in ("run_one_step", "update", "run_one_step_basic", "analysis")
        assert isinstance(s["params"], list)
        assert isinstance(s["input_fields"], list)


def test_key_components_schema_detail():
    schemas = scan_all_components()
    # 教程核心组件必须有参数和字段信息
    for name in ["FastscapeEroder", "LinearDiffuser", "PriorityFloodFlowRouter", "ChiFinder"]:
        assert name in schemas, f"缺教程核心组件 {name}"
        s = schemas[name]
        assert len(s["params"]) > 0, f"{name} 未提取到参数"
        assert s["input_fields"], f"{name} 未提取到输入字段"
    # FastscapeEroder 的 K_sp 应有默认值与文档
    k = [p for p in schemas["FastscapeEroder"]["params"] if p["name"] == "K_sp"][0]
    assert k["type"] == "float"
    assert k["default"] is not None


def test_schema_json_serializable():
    import json
    schemas = scan_all_components()
    text = json.dumps(schemas, ensure_ascii=False)   # 不抛异常即通过
    assert len(text) > 10000


def test_categories_covered():
    schemas = scan_all_components()
    cats = categories_of(schemas)
    assert "河道侵蚀与沉积" in cats
    assert "水流与汇流" in cats


def test_cache_speeds_up():
    from time import perf_counter
    t0 = perf_counter()
    scan_all_components()          # 第二次调用应读缓存
    assert perf_counter() - t0 < 2.0, "缓存读取应秒级返回"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"共 {len(fns)} 项测试全部通过")

"""
AI 参数助手核心：自然语言 → LandlabGUI 工作流 JSON。
==================================================
对接任意 OpenAI 兼容接口（OpenAI / DeepSeek / Kimi / Ollama 本地等）。
纯 Python 无 Qt，网络失败抛带中文说明的异常。
"""

from __future__ import annotations

import json
import re

import requests

_UA = {"User-Agent": "LandlabGUI/2.0 (AI assistant)"}

_DEFAULT_TIMEOUT = 120


# ============================================================ Prompt
def build_system_prompt(component_names: list, plugin_names: list) -> str:
    """构造系统提示词：注入当前可用的组件/插件名与工作流 JSON 规范。"""
    schema_example = {
        "version": 1,
        "name": "场景名",
        "grid": {"type": "RasterModelGrid",
                 "params": {"shape": [80, 100], "xy_spacing": 100.0}},
        "boundary": "south_open",
        "terrain": {"mode": "noise", "amplitude": 10.0, "slope": 0.01,
                    "slope_dir": "S", "seed": 42},
        "time": {"dt": 250.0, "n_steps": 500,
                 "refresh_every": 20, "history_every": 10},
        "steps": [
            {"id": "u1", "kind": "plugin", "plugin": "构造抬升(4种模式)",
             "params": {"mode": "uniform", "rate": 5e-4}, "when": "every_step"},
            {"id": "f1", "kind": "component", "component": "PriorityFloodFlowRouter",
             "params": {}, "when": "every_step"},
            {"id": "e1", "kind": "component", "component": "FastscapeEroder",
             "params": {"K_sp": 1e-5, "m_sp": 0.5, "n_sp": 1.0},
             "when": "every_step", "step_style": "run_one_step"},
        ],
        "outputs": {"dir": "ai_results", "formats": ["ascii"],
                    "river_min_area": 100000.0},
    }
    return f"""你是地貌演化模拟助手。用户会用自然语言描述想要的模拟场景，
你只输出一个 JSON 工作流（不输出任何解释文字、不输出 markdown 代码围栏之外的内容）。

## 工作流 JSON 规范（严格遵守字段名）
{json.dumps(schema_example, ensure_ascii=False, indent=1)}

## 硬性约束
1. component 只能用这些名字（逐字精确）: {json.dumps(component_names, ensure_ascii=False)}
2. plugin 只能用这些名字: {json.dumps(plugin_names, ensure_ascii=False)}
3. steps 顺序必须是: 抬升类 plugin → PriorityFloodFlowRouter(或 FlowAccumulator) →
   侵蚀组件(FastscapeEroder/Space等) → LinearDiffuser → 分析类(ChiFinder/SteepnessFinder,
   when 设为 "once_at_end")
4. 抬升量级: 稳定地台 1e-5, 造山带 5e-4~1e-3 m/yr; K_sp: 硬岩 1e-6, 软岩 1e-4
5. 网格 30~120 格/边; dt 100~500 yr; n_steps 使总时长达到用户要求
   (总时长 = dt × n_steps, 稳态通常需要 5e5~1e6 yr)
6. "构造抬升(4种模式)" 的 mode 可选: uniform/tibet/gradient/two_block
7. boundary 用 "south_open"(默认) 或 "all_closed"
8. 用户没提的参数保持模板默认值, 不要编造组件名或参数名

只输出 JSON。"""


def build_user_prompt(description: str) -> str:
    return f"场景描述：{description}\n请输出工作流 JSON。"


# ============================================================ 调用
def ask_llm(system: str, user: str, base_url: str, api_key: str, model: str,
            proxies=None, timeout: int = _DEFAULT_TIMEOUT) -> str:
    """调用 OpenAI 兼容 /chat/completions，返回助手文本。"""
    base_url = (base_url or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("API 地址为空")
    if base_url.endswith("/chat/completions"):
        url = base_url
    else:
        url = base_url + "/chat/completions"
    payload = {
        "model": model or "gpt-4o-mini",
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {api_key}", **_UA} if api_key else dict(_UA)
    # 本地端点（127.0.0.1/localhost）绝不走系统代理：代理进程接管后连接会挂死
    from urllib.parse import urlparse
    host = (urlparse(base_url).hostname or "").lower()
    if host in ("127.0.0.1", "localhost", "::1"):
        proxies = {"http": None, "https": None}
        timeout = min(timeout, 15)   # 本地端点响应快，避免防火墙 DROP 时干等 2 分钟
    try:
        r = requests.post(url, json=payload, headers=headers,
                          proxies=proxies, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.Timeout as e:
        raise ConnectionError("AI 请求超时（可到 工具→AI 参数助手 里检查地址/代理）") from e
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"AI 请求失败: {e}") from e
    except ValueError as e:
        raise ConnectionError("AI 返回了非 JSON 响应（检查 API 地址是否正确）") from e
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise ConnectionError(f"AI 响应格式异常: {json.dumps(data)[:200]}") from e


# ============================================================ 解析
def extract_workflow_json(text: str) -> dict:
    """从模型回复中提取工作流 JSON（容忍 ```json 围栏/前后杂文）。"""
    if not text or not text.strip():
        raise ValueError("AI 返回了空内容")
    # 1) 围栏优先
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = [m.group(1)] if m else []
    # 2) 裸 JSON（首个 { 到最后一个 }）
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        candidates.append(text[i:j + 1])
    for c in candidates:
        try:
            wf = json.loads(c)
        except Exception:
            continue
        if isinstance(wf, dict) and isinstance(wf.get("steps"), list) and wf["steps"]:
            wf.setdefault("version", 1)
            wf.setdefault("name", "AI 场景")
            if wf.get("grid") and "grid_rebuild" not in wf:
                wf["grid_rebuild"] = True
            return wf
    raise ValueError("未能从 AI 回复中解析出有效的工作流 JSON")


def validate_workflow(wf: dict, known_names: set) -> list:
    """校验步骤引用，返回缺失的功能名列表（空=全部可用）。"""
    missing = []
    for s in wf.get("steps", []):
        name = s.get("component") or s.get("plugin")
        if name and name not in known_names:
            missing.append(name)
    return missing

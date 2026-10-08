"""课堂实验的进度规则。

界面只负责采集学生做到了哪一步；能不能进入下一步由这里判断，
不依赖 Qt，便于单测。
"""

from __future__ import annotations

from .i18n import tr

PRESET_NAME = "课堂实验-河流下切"

# 课堂预设里四个过程步骤的顺序。分析类组件可以跟在后面，但不能插到它们前面打乱顺序。
PROCESS_STEPS = (
    ("plugin", "构造抬升(4种模式)"),
    ("component", "PriorityFloodFlowRouter"),
    ("component", "FastscapeEroder"),
    ("component", "LinearDiffuser"),
)

STEP_IDS = ("goal", "load", "order", "run", "views", "quiz", "note")

QUIZ = (
    {"id": "gentler", "correct": True},
    {"id": "steeper", "correct": False},
    {"id": "unrelated", "correct": False},
)

TAB_TERRAIN = 0
TAB_SLOPE_AREA = 2


def workflow_steps(steps: list | None) -> list[tuple[str, str]]:
    """把工作流步骤收成 (kind, name)，供顺序检查使用。"""
    out = []
    for step in steps or []:
        kind = step.get("kind", "component")
        if kind == "plugin":
            out.append(("plugin", step.get("plugin") or ""))
        else:
            out.append(("component", step.get("component") or ""))
    return out


def order_ok(steps: list[tuple[str, str]]) -> bool:
    """四个过程步骤按抬升、汇流、下切、扩散的顺序出现即可。"""
    want = list(PROCESS_STEPS)
    index = 0
    for item in steps:
        if index < len(want) and item == want[index]:
            index += 1
    return index == len(want)


def views_ok(sequence: list[int] | None) -> bool:
    """先出现地形标签，之后才出现坡度-面积标签。"""
    seq = list(sequence or [])
    if TAB_TERRAIN not in seq or TAB_SLOPE_AREA not in seq:
        return False
    return seq.index(TAB_TERRAIN) < seq.index(TAB_SLOPE_AREA)


def gate(step_id: str, snap: dict) -> tuple[bool, str]:
    """返回 (是否通过, 原因代码)。原因代码由界面翻成一句人话。"""
    name = (snap.get("workflow_name") or "").strip()
    steps = snap.get("steps") or []
    loaded = name == PRESET_NAME
    ordered = loaded and order_ok(steps)

    if step_id == "goal":
        if snap.get("acknowledged_goal"):
            return True, ""
        return False, "goal"
    if step_id == "load":
        if loaded:
            return True, ""
        return False, "load"
    if step_id == "order":
        if ordered:
            return True, ""
        return False, "order"
    if step_id == "run":
        done = int(snap.get("steps_done") or 0) > 0 and not snap.get("interrupted")
        completed = (snap.get("completed_name") or "").strip()
        if ordered and done and completed == PRESET_NAME:
            return True, ""
        if snap.get("interrupted"):
            return False, "run_interrupted"
        if ordered and done and completed and completed != PRESET_NAME:
            return False, "run_other"
        return False, "run_none"
    if step_id == "views":
        if views_ok(snap.get("tab_sequence")):
            return True, ""
        return False, "views"
    if step_id == "quiz":
        idx = snap.get("quiz_index")
        if isinstance(idx, int) and 0 <= idx < len(QUIZ):
            return True, ""
        return False, "quiz"
    if step_id == "note":
        student = (snap.get("student_name") or "").strip()
        exported = (snap.get("exported_name") or "").strip()
        if student and snap.get("note_written") and exported == student:
            return True, ""
        if not student:
            return False, "name"
        return False, "note"
    return False, "unknown"


def current_step(snap: dict) -> int:
    """第一个还没通过的步骤下标；全部通过时等于步骤总数。"""
    for index, step_id in enumerate(STEP_IDS):
        ok, _reason = gate(step_id, snap)
        if not ok:
            return index
    return len(STEP_IDS)


def quiz_correct(index: int | None) -> bool:
    if not isinstance(index, int) or not (0 <= index < len(QUIZ)):
        return False
    return bool(QUIZ[index]["correct"])


def render_lab_note(*, student: str, preset: str, steps_done: int,
                    mean_z: float, max_z: float, answer: str, correct: bool) -> str:
    """导出给学生交作业的 Markdown。"""
    verdict = tr("回答正确") if correct else tr("留待课堂讲评")
    return "\n".join([
        "# " + tr("课堂实验记录"),
        "",
        "- " + tr("学生: {0}").format(student),
        "- " + tr("预设: {0}").format(preset),
        "- " + tr("完成步数: {0}").format(steps_done),
        "- " + tr("平均高程: {0} m").format(f"{mean_z:.1f}"),
        "- " + tr("最大高程: {0} m").format(f"{max_z:.1f}"),
        "- " + tr("选择题: {0}").format(answer),
        "- " + tr("判断: {0}").format(verdict),
        "",
        tr("把这份记录交给老师。地形图和坡度-面积图可以在软件里截图附上。"),
        "",
    ])

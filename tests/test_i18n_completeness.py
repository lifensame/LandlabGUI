# -*- coding: utf-8 -*-
"""
回归测试：英文模式的翻译完整性与语言初始化顺序。
运行: QT_QPA_PLATFORM=offscreen python tests/test_i18n_completeness.py

背景：tr() 在英文模式下查不到译文就原样返回中文，所以"漏翻"不会报错、只会静默
显示中文。本测试把三件事钉死：
1. 静态：源码里每个 tr("中文") 字面量都必须有英文译文（新增界面文字漏翻会失败）
2. 静态：不允许把 f-string 传给 tr()（插值后无法查表，等于永远不翻译）
3. 动态：英文模式启动后，窗口标题必须是英文，且运行期未记录任何未翻译条目
   例外：语言切换菜单按设计保持双语（"Component language / 语言"），便于在
   任何语言下都能找到它
"""
import ast
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import app.core.i18n as i18n  # noqa: E402
from app.core.i18n import _STR_EN, tr, set_lang  # noqa: E402

# 这两个是随本次修复一起加的，缺失说明版本过旧 —— 用占位实现让其余用例仍能跑出结论
reset_untranslated = getattr(i18n, "reset_untranslated", lambda: None)
untranslated_seen = getattr(i18n, "untranslated_seen", lambda: set())

CJK = re.compile(r"[\u4e00-\u9fff]")

# 语言菜单：按设计保持双语，允许出现中文
BILINGUAL_OK = {
    "组件显示语言 / Language",
    "中文（组件中文名+中文说明）",
}


def _iter_app_files():
    for base, dirs, files in os.walk(os.path.join(APP_DIR, "app")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in sorted(files):
            if fn.endswith(".py"):
                yield os.path.join(base, fn)


def _parse(path):
    with open(path, encoding="utf-8-sig") as f:
        return ast.parse(f.read(), filename=path)


# --------------------------------------------------------------------------
def test_1_every_chinese_tr_literal_has_translation():
    """静态：所有 tr("中文…") 字面量都必须有英文译文。"""
    missing, total = [], 0
    for path in _iter_app_files():
        rel = os.path.relpath(path, APP_DIR).replace("\\", "/")
        for n in ast.walk(_parse(path)):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            if (getattr(f, "id", None) or getattr(f, "attr", None)) != "tr":
                continue
            for a in n.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    if not CJK.search(a.value):
                        continue
                    total += 1
                    if a.value not in _STR_EN and a.value not in BILINGUAL_OK:
                        missing.append(f"{rel}:{n.lineno}  {a.value[:60]!r}")

    assert total > 300, f"扫描到的 tr() 中文串只有 {total} 条，解析可能出错"
    assert not missing, (
        f"{len(missing)} 条界面文字缺英文译文（英文模式下会显示中文）：\n  "
        + "\n  ".join(missing[:20]))


def test_2_no_fstring_passed_to_tr():
    """静态：tr() 不能收到 f-string，否则插值后查不到译文。"""
    bad = []
    for path in _iter_app_files():
        rel = os.path.relpath(path, APP_DIR).replace("\\", "/")
        for n in ast.walk(_parse(path)):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            if (getattr(f, "id", None) or getattr(f, "attr", None)) != "tr":
                continue
            for a in n.args:
                if isinstance(a, ast.JoinedStr):
                    has_interp = any(isinstance(v, ast.FormattedValue) for v in a.values)
                    lit = "".join(str(v.value) for v in a.values
                                  if isinstance(v, ast.Constant))
                    if has_interp and CJK.search(lit):
                        bad.append(f"{rel}:{n.lineno}  {lit[:60]!r}")

    assert not bad, ("tr() 收到了 f-string，插值后无法查表（应改用 tr(\"…{0}…\").format(...)）：\n  "
                     + "\n  ".join(bad))


def test_3_no_module_level_translation_calls():
    """静态：模块顶层不能调用 tr()，否则会早于 set_lang 执行。"""
    tr_funcs = {"tr", "tr_cat", "display_name", "short_name", "doc"}
    bad = []
    for path in _iter_app_files():
        rel = os.path.relpath(path, APP_DIR).replace("\\", "/")
        tree = _parse(path)
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Call):
                    f = sub.func
                    if (getattr(f, "id", None) or getattr(f, "attr", None)) in tr_funcs:
                        bad.append(f"{rel}:{sub.lineno}")

    assert not bad, ("模块顶层调用了翻译函数（会早于语言初始化）：\n  " + "\n  ".join(bad))


def test_4_tr_falls_back_and_records():
    """动态：缺译文时回退中文，并记入 untranslated_seen()。"""
    set_lang("en")
    try:
        reset_untranslated()
        assert tr("这是一个未翻译的测试串") == "这是一个未翻译的测试串"
        assert "这是一个未翻译的测试串" in untranslated_seen()

        reset_untranslated()
        assert tr("确定") == "OK"          # 已翻译
        assert not untranslated_seen()      # 不该被记录
    finally:
        set_lang("zh")


def test_5_english_mode_ui_has_no_untranslated():
    """动态：英文模式启动主窗口，标题须英文，且运行期无未翻译条目。"""
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QSettings

    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QSettings("LandlabGUI", "main").setValue("wizard_seen", True)
    QSettings("LandlabGUI", "main").setValue("lang", "en")

    from app.gui.style import apply
    apply(app)

    reset_untranslated()
    from app.gui.main_window import MainWindow
    win = MainWindow()
    try:
        assert not CJK.search(win.windowTitle()), (
            f"英文模式下窗口标题仍是中文: {win.windowTitle()!r}"
            "（setWindowTitle 必须晚于 i18n.set_lang）")

        seen = untranslated_seen() - BILINGUAL_OK
        assert not seen, (
            "英文模式下以下文本回退成了中文（缺译文）：\n  "
            + "\n  ".join(repr(s[:70]) for s in sorted(seen)[:20]))
    finally:
        win.close()
        set_lang("zh")


if __name__ == "__main__":
    tests = [test_1_every_chinese_tr_literal_has_translation,
             test_2_no_fstring_passed_to_tr,
             test_3_no_module_level_translation_calls,
             test_4_tr_falls_back_and_records,
             test_5_english_mode_ui_has_no_untranslated]
    for fn in tests:
        fn()
        print("PASS", fn.__name__, flush=True)
    print("\n界面翻译完整性: 全部通过", flush=True)

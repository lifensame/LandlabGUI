"""
PyInstaller 打包脚本：python build_exe.py
产物 dist/LandlabGUI/（onedir 模式，landlab 体积大，onefile 启动会极慢）。
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    subprocess.check_call([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "LandlabGUI",
        "--windowed",
        # landlab/matplotlib/scipy 的隐藏导入
        "--hidden-import", "landlab",
        "--hidden-import", "landlab.components",
        "--hidden-import", "landlab.io",
        "--hidden-import", "landlab.plot",
        "--collect-all", "landlab",
        "--collect-data", "matplotlib",
        os.path.join(ROOT, "main.py"),
    ])
    # 插件/预设/文档放到 exe 旁边，方便直接编辑与热加载
    import shutil
    dist = os.path.join(ROOT, "dist", "LandlabGUI")
    for folder in ("plugins", "presets", "docs"):
        src = os.path.join(ROOT, folder)
        dst = os.path.join(dist, folder)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
            print(f"已复制 {folder}/ -> dist/LandlabGUI/{folder}/")
    print("\n打包完成: dist/LandlabGUI/LandlabGUI.exe")
    print("结构: LandlabGUI.exe + plugins/ + presets/ + docs/（均可在旁直接编辑）")


if __name__ == "__main__":
    main()

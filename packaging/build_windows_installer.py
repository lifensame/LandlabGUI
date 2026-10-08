"""Build a Windows installer for LandlabGUI from Linux or Windows.

The result is dist/LandlabGUI-2.2.0-win64-setup.exe. It bundles CPython 3.12
and the Windows wheels for PySide6, landlab, and their runtime dependencies.
On Windows, double-click the installer, then open LandlabGUI from the Start menu.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHEEL_DIR = os.path.join(ROOT, "packaging", "wheels")
INSTALLER = os.path.join(ROOT, "dist", "LandlabGUI-2.2.0-win64-setup.exe")

REQUIREMENTS = [
    "landlab==2.11.0",
    "PySide6-Essentials==6.11.2",
    "shiboken6==6.11.2",
    "netCDF4==1.7.4",
    "requests==2.33.1",
    "numpydoc==1.11.0",
    "py-richdem==2.2.0rc3",
]


def download_wheels() -> None:
    os.makedirs(WHEEL_DIR, exist_ok=True)
    if glob.glob(os.path.join(WHEEL_DIR, "*.whl")):
        print("使用已有的 packaging/wheels/")
        return
    subprocess.check_call([
        sys.executable, "-m", "pip", "download",
        "-d", WHEEL_DIR,
        "--only-binary=:all:",
        "--platform", "win_amd64",
        "--python-version", "312",
        "--implementation", "cp",
        *REQUIREMENTS,
    ])


def build() -> None:
    os.chdir(ROOT)
    download_wheels()
    subprocess.check_call([sys.executable, "-m", "nsist", "packaging/installer.cfg"])
    built = os.path.join(ROOT, "build", "pynsist", "LandlabGUI-2.2.0-win64-setup.exe")
    os.makedirs(os.path.dirname(INSTALLER), exist_ok=True)
    shutil.copy2(built, INSTALLER)
    print("\n安装包:", INSTALLER)


if __name__ == "__main__":
    build()

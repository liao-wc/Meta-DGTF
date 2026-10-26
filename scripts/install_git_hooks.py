# -*- coding: utf-8 -*-
"""安装仓库 Git 钩子：把 .githooks/pre-commit 复制到 .git/hooks。"""
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parent.parent
src = ROOT / ".githooks" / "pre-commit"
dst = ROOT / ".git" / "hooks" / "pre-commit"
if not src.is_file():
    raise SystemExit("missing .githooks/pre-commit")
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)
print("installed", dst)

# -*- coding: utf-8 -*-
"""诊断：谁在冒烟里调 `_save_bandit`（写生产 dgtf_memory/bandit.json）。

做法：包一层 spy，打印调用栈（+ cfg），并把写入**重定向到临时目录**
（避免诊断本身再污染生产记忆库）。跑完后 `git status dgtf_memory/` 应干净。
"""
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import smoke_test as S  # noqa: E402

_orig = S.mod._save_bandit
_TMP = Path(tempfile.mkdtemp(prefix="diag_bandit_"))


def spy(bb, cfg):
    sys.stdout.flush()
    print("\n!!!! _save_bandit 被调用 cfg=%r  (重定向-> %s)" % (cfg, _TMP))
    traceback.print_stack(file=sys.stdout)
    sys.stdout.flush()
    c = dict(cfg or {})
    c["dir"] = str(_TMP)
    return _orig(bb, c)


S.mod._save_bandit = spy
rc = S.main()
print("\n==== smoke main() rc=%r ====" % (rc,))
sys.exit(rc)

# -*- coding: utf-8 -*-
"""隔离验证：check_v12315 的两条红是否为并行线干扰（而非本版回归）。

做法：把 outputs/*.md **冻结复制**到一个临时目录（保 mtime），
再对副本跑 `_auto_history`，读数稳定即证明「活目录竞态」。
"""
import os
import sys
import glob
import shutil
import tempfile
import importlib.util
from pathlib import Path

os.environ.setdefault("DGTF_API_KEY", "sk-probe")

SRC = "元DGTF-V1.23.27.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("m27probe", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["m27probe"] = m          # ★ 必须先注册再 exec
    spec.loader.exec_module(m)
    return m


def main():
    m = load_mod()
    cfg = m.load_config("")

    print("=== ① 活目录连读两次（复现竞态） ===")
    for i in (1, 2):
        b = m._auto_history("outputs", 300, cfg=cfg)
        print("  第%d次: n=%s tri_n=%s" % (i, b["n"], b.get("tri_n")))

    print("\n=== ② 冻结副本（时点快照） ===")
    md = sorted(glob.glob("outputs/*.md"))
    with tempfile.TemporaryDirectory() as td:
        snap = []
        for p in md:
            try:
                st = os.stat(p)
                dst = Path(td) / Path(p).name
                shutil.copy2(p, dst)
                os.utime(dst, (st.st_mtime, st.st_mtime))
                snap.append(p)
            except Exception:
                pass
        print("  快照 %d 份 md" % len(snap))
        for i in (1, 2):
            b = m._auto_history(td, 300, cfg=cfg)
            print("  第%d次: n=%s tri_n=%s tri_p10=%s"
                  % (i, b["n"], b.get("tri_n"), b.get("tri_p10")))
        h = m._auto_history(td, 20, cfg=cfg)
        print("  limit20: n=%s fact=%s nonfact=%s"
              % (h["n"], (h["by_type"]["fact"] or {}).get("n"),
                 (h["by_type"]["nonfact"] or {}).get("n")))
        b2 = m._auto_history(td, 300, cfg=cfg)
        print("  limit300: n=%s" % b2["n"])
        print("  上限放大后样本数 %s（%d → %d）"
              % ("增加 ✅" if b2["n"] > h["n"] else "没增加 ❌",
                 h["n"], b2["n"]))


if __name__ == "__main__":
    main()

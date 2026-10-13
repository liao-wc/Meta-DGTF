# -*- coding: utf-8 -*-
"""v1.23.15 判据修复（冻结快照）的**判别力背书**。

背景：`check_v12315` 原先直接读活 `outputs/`（两次读数之间目录被并行进程
与本判据自己的夹具改动）⇒ 报「上限放大后样本数没增加」的**假红**。
修复：改用**冻结快照**（`mkdtemp` + `copy2` 保 mtime）。

本脚本证明**修复后的判据仍有判别力**（不是把红改成绿就完事）：
变异体打在判据读的那个东西上 —— `_auto_history` 的**每题型上限**。
上限失效 ⇒ `by_type.fact.n` 会 > 20 ⇒ 判据的
`if _ft > 20 or _nf > 20` 必须报红。

跑法：
    python _mut_v12315_snapshot.py            # 只跑这一个变异体
"""
import os
import sys
import shutil
import tempfile
import importlib.util
from pathlib import Path

os.environ.setdefault("DGTF_API_KEY", "sk-mut")
os.environ["CODEBUDDY_SAFE_DELETE_ENABLED"] = "0"

SRC = Path("元DGTF-V1.23.27.py")

ANCHOR = '    _lim = max(1, int(limit or 200))\n'
MUTANT = '    _lim = max(1, int(limit or 200)) * 999  # 每题型上限失效\n'


def _load_src_text():
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    assert txt.count("\r\n") == txt.count("\n"), "主文件不是纯 CRLF"
    return txt.replace("\r\n", "\n")


def main():
    txt = _load_src_text()
    n = txt.count(ANCHOR)
    if n != 1:
        print("✗ 锚点命中 %d 次（应为 1）" % n)
        return 2
    mut = txt.replace(ANCHOR, MUTANT)

    tmpd = Path(tempfile.mkdtemp(prefix="_mutv12315_"))
    try:
        p = tmpd / "mut_mod.py"
        p.write_bytes(mut.replace("\n", "\r\n").encode("utf-8"))

        # ── ① 建冻结快照（与判据同法） ──
        snap = tmpd / "snap"
        snap.mkdir()
        k = 0
        for sp in sorted(Path("outputs").rglob("*.md")):
            try:
                st = sp.stat()
                dst = snap / ("%d_%s" % (k, sp.name))
                shutil.copy2(sp, dst)
                os.utime(dst, (st.st_mtime, st.st_mtime))
                k += 1
            except Exception:
                pass
        print("快照 %d 份" % k)

        # ── ② 加载两份模块，各跑一次 ──
        def run(tag, mod_src, path):
            spec = importlib.util.spec_from_file_location(tag, str(path))
            m = importlib.util.module_from_spec(spec)
            sys.modules[tag] = m
            spec.loader.exec_module(m)
            cfg = m.load_config("")
            h = m._auto_history(str(snap), 20, cfg=cfg)
            ft = (h["by_type"]["fact"] or {}).get("n", 0)
            nf = (h["by_type"]["nonfact"] or {}).get("n", 0)
            return ft, nf

        ft0, nf0 = run("m_orig", txt, SRC)
        ft1, nf1 = run("m_mut", mut, p)
        print("原版 : fact=%d nonfact=%d  ⇒ 上限 20 检查 %s"
              % (ft0, nf0, "通过" if (ft0 <= 20 and nf0 <= 20) else "报红"))
        print("变异 : fact=%d nonfact=%d  ⇒ 上限 20 检查 %s"
              % (ft1, nf1, "通过" if (ft1 <= 20 and nf1 <= 20) else "报红"))
        red = not (ft1 <= 20 and nf1 <= 20)
        print("MUT RESULT 判红 %d / 1" % (1 if red else 0))
        return 0 if red else 1
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

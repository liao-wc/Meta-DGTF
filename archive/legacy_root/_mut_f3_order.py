# -*- coding: utf-8 -*-
"""F3 时序修正的**变异体自证**（v2，改用两次 replace，不再手工 index）。

把回填块（`try: _seen_keys ... except: pass`）**前移**到 `pool.merge(...)`
之后（= 修复前的位置），判据必须判红。

★ 红线：变异体打在判据读的那个东西上 —— P2 读 `view.belief_items`，
  变异体改的正是它的**赋值时点**。
★ 红线：`finally` 里必须复原，且复原后校验纯 CRLF。
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TGT = HERE / "元DGTF-V1.23.28.py"
BAK = HERE / "_mut_f3_order_backup.py"
PY = sys.executable

# 回填块（含其前置注释），一字不差
BLOCK = (
    '        # [D1 回填 · 时序修正] `View.belief_items` 之前是**声明了、也出口了、\n'
    '        #   但从不被赋值**的死字段（`View.to_dict = asdict(self)` ⇒ 键恒 []）。\n'
    '        #   ★ 回填**必须放在 `add_undecidable` 之后** —— 信念条目是那一步才\n'
    '        #     upsert 进池的；放前面读到的池还是空的（真跑实测恒 []，\n'
    '        #     见 v12328_报告.md §2.5）。这是「有接线 ≠ 这跑走得到」的时序版。\n'
    '        #   ★ 只回填**与本次 view 相关**的条目（按 text 精确命中），\n'
    '        #     不是把全池倒给每个 view —— view 是「这一圈看到了什么」。\n'
    '        #   ★ 命中不到就保持 []（不猜、不兜底）。\n'
    '        try:\n'
    '            _seen_keys = set()\n'
    '            for _a in (view.amps or []):\n'
    '                _t0 = str(_a.get("desc") or _a.get("text") or "").strip()\n'
    '                if _t0:\n'
    '                    _seen_keys.add(_t0)\n'
    '            for _t0 in (view.anchor_touched or []):\n'
    '                _t0 = str(_t0.get("text") or _t0.get("desc") or "").strip()\n'
    '                if _t0:\n'
    '                    _seen_keys.add(_t0)\n'
    '            if _seen_keys:\n'
    '                _bind = []\n'
    '                for _it in (pool.belief_items or []):\n'
    '                    if str(_it.get("text", "")).strip() in _seen_keys:\n'
    '                        _bind.append(_it)\n'
    '                if _bind:\n'
    '                    view.belief_items = _bind\n'
    '        except Exception:\n'
    '            pass\n'
)
# 修复前的位置：pool.merge(...) 的收尾行之后
EARLY = '                   aspect_units=list(getattr(view, "aspect_units", None) or []))\n'


def _load(p):
    return p.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _save(p, txt):
    assert "\r\r\n" not in txt
    p.write_bytes(txt.replace("\n", "\r\n").encode("utf-8"))


def main():
    shutil.copy2(TGT, BAK)
    print("备份 →", BAK.name)
    red = False
    try:
        txt = _load(TGT)
        assert txt.count(BLOCK) == 1, "回填块命中 %d 次" % txt.count(BLOCK)
        assert txt.count(EARLY) == 1, "早期锚点命中 %d 次" % txt.count(EARLY)
        # ① 摘掉
        txt = txt.replace(BLOCK, "", 1)
        # ② 插到 merge 之后（修复前的位置）
        txt = txt.replace(EARLY, EARLY + BLOCK, 1)
        _save(TGT, txt)
        print("已注入变异：回填块前移到 `pool.merge(...)` 之后（= 修复前位置）")

        r = subprocess.run([PY, str(HERE / "_diag_f3_order.py")],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=str(HERE))
        out = (r.stdout or "") + (r.stderr or "")
        print("---- 变异体下判据输出（尾 12 行）----")
        print("\n".join(out.strip().splitlines()[-12:]))
        red = ("P2" in out and "NG" in out) or r.returncode != 0
    finally:
        shutil.copy2(BAK, TGT)
        _save(TGT, _load(TGT))          # 归一化换行
        BAK.unlink(missing_ok=True)
        print("已复原", TGT.name)

    b = TGT.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "复原后非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "复原后含 CRCRLF"
    print()
    if red:
        print("=== M-F3 ★ 变异体判红（判别力成立）===")
        sys.exit(0)
    print("=== M-F3 ✗ 变异体**未判红** ⇒ 判据无判别力 ===")
    sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 v1.23.23 的冒烟判据注入 smoke_test.py，并把 SRC 指向新版。

三件事（各自幂等）：
  ① `SRC = HERE / "元DGTF-V1.23.22.py"` -> `...V1.23.23.py`；
  ② 在 `check_v12322_web_hits_dump` 之前插入 `check_v12323_view_echo_full`；
  ③ `main()` 里接上守卫（插在 v12322 那条之后、跑 route 矩阵之前）。

smoke_test.py 同样是**纯 CRLF**：read_bytes -> 断言 -> 转 LF -> 改 -> 转回 -> write_bytes。

    python _mk_v12323_smoke.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"

SRC_OLD = 'SRC = HERE / "元DGTF-V1.23.22.py"'
SRC_NEW = 'SRC = HERE / "元DGTF-V1.23.23.py"'

FUNC_ANCHOR = "def check_v12322_web_hits_dump():"
# ★ 锚点必须唯一：`q = "测试问题：…"` 在文件里出现 **2 次**（另一次在别的用例里），
#   所以锚在「上一条守卫」上 —— 那段只在 main() 里出现。
GUARD_ANCHOR = ("    if not check_v12322_web_hits_dump():\n"
                "        return 1\n")
GUARD_NEW = """    if not check_v12323_view_echo_full():
        return 1
"""

CHECK = r'''def check_v12323_view_echo_full():
    """[v1.23.23] 日志回显不再把正文按字符硬砍（阴阳视角「内容没显示完全」）。

    用户实测：日志窗口里阴阳视角那块的**最后一行被砍在半句上**
    （`- [concept] 纠缠熵面积律不能单`）。查下来**不是前端裁的** —— `.run.log`
    里就是这行：四处回显写死了字符上限，而模型返回的是**多行正文**。

    三层判据：
      ① 结构：`self.vp(...)` 上不再出现按字符硬砍的上限；六处回显统一走
         `_vp_preview`（1 定义 + 6 调用）；
      ② 行为（**主路径**）：驱动生产入口 `DGTF._expand_pair`，桩住 LLM 返回一份
         >200 字的 4 行正文，**捕获 stdout**，断言「旧实现会被砍掉的那一段」
         真的出现在日志回显里（不是只在源码里多了个函数名）；
      ③ 反面对照：同一份正文的 `raw[:200]` **必须**丢掉那一段
         —— 保证这条样例在两个实现下会分岔（否则这条判据没有判别力）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8", newline="")

    # ① 结构 -----------------------------------------------------------------
    _caps = re.findall(r"self\.vp\([^\n]{0,140}\[:\d+\]", src)
    if _caps:
        bad.append("`self.vp(...)` 上还有按字符硬砍的上限：%s" % _caps[:2])
    if not hasattr(mod, "_vp_preview"):
        bad.append("模块里没有 `_vp_preview`")
    if src.count("_vp_preview(") != 7:
        bad.append("`_vp_preview(` 出现 %d 次（应为 1 定义 + 6 调用）"
                   % src.count("_vp_preview("))
    _wired = len(re.findall(r"self\.vp\([^\n]*_vp_preview\(", src))
    if _wired != 6:
        bad.append("`self.vp(...)` 上接 `_vp_preview` 的有 %d 处（应为 6）" % _wired)

    # ①b 行为：真截断时**切在换行上**且带可见痕（line-aware + 不静默丢）
    #     为什么单列：主路径那份样例只有 ~231 字、够不到 limit ⇒ 「按 limit 硬切」
    #     的坏实现也能通过 ② ⇒ 必须另喂一份**超过 limit** 的输入来分辨。
    if hasattr(mod, "_vp_preview"):
        _lm = "\n".join("- [concept] 第%d行候选：%s" % (_i, "字" * 60)
                        for _i in range(1, 6))
        _o = mod._vp_preview(_lm, limit=200)
        _head = _o.split("\n   …（预览到此")[0]
        if not (0 < len(_head) < len(_lm)):
            bad.append("超长正文没被限流（limit=200 时保留了 %d/%d 字）"
                       % (len(_head), len(_lm)))
        elif not (_lm.startswith(_head) and _lm[len(_head)] == "\n"):
            bad.append("超长正文没切在换行上（仍会砍出半行）")
        if _o[len(_head):] != ("\n   …（预览到此，另有 %d 字未显示）"
                               % (len(_lm) - len(_head))):
            bad.append("截断痕迹不对：%r" % _o[len(_head):][:40])

    # ②③ 行为（主路径）+ 反面对照 ------------------------------------------
    RAW = "\n".join([
        "- [thread] C1 点名方向已耗尽，本体层此处未生；本圈只列避开后的可判定侧残留：定义、痕迹、论证结构。",
        "- [concept] 空间离散化若被观测，只支持底层自由度截断，不支持外部模拟器；因此该痕迹不能单独判决世界是虚拟的。",
        "- [concept] 全息投影若无边界与体—边界字典，科学上不可检验；一切是全息投影作为字面命题当前不可判定。",
        "- [concept] 纠缠熵面积律不能单独支持全息，因为普通局域场论也满足；需比较对数修正系数与符号。",
    ])
    CUT = "纠缠熵面积律不能单独支持全息"
    if len(RAW) <= 200:
        bad.append("样例只有 %d 字，够不到旧上限 ⇒ 无判别力" % len(RAW))
    elif CUT in RAW[:200]:
        bad.append("样例选错：`raw[:200]` 恰好没砍到那一段，两版结果相同 ⇒ 无判别力")
    else:
        cfg = build_cfg(False)
        llm = mod.LLM(cfg)

        def _fake_call(system, user, temperature=0.6, max_tokens=3000,
                       json_mode=False, model=None):
            return RAW

        llm.call = _fake_call
        dg = mod.DGTF("0", llm, cfg)
        dg.verbose = True                       # vp 只在 verbose 下 print
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dg._expand_pair([("阴", "阴视角指令")], lambda label: "USER")
        out = buf.getvalue()
        if "💧 [阴视角]" not in out:
            bad.append("主路径没走到阴阳回显（stdout 里没有 `💧 [阴视角]`）")
        _miss = [ln for ln in RAW.split("\n") if ln not in out]
        if _miss:
            bad.append("回显里丢了 %d 行，例如：%s" % (len(_miss), _miss[-1][:44]))
        if CUT not in out:
            bad.append("旧实现被砍掉的那一段没出现在回显里：%s" % CUT)
        if "另有" in out:
            bad.append("约 %d 字的正文不该触发截断（却出现了「另有 N 字未显示」）"
                       % len(RAW))

    if bad:
        for _x in bad:
            print("  \u2717 [v12323] %s" % _x)
        return False
    print("  \u2713 [v12323] 日志回显按整行截断：六处调用点统一 + 主路径实测不丢行"
          "（旧上限下会丢「%s」）" % CUT)
    return True


'''


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "%s 不是纯 CRLF" % p.name
    assert b.count(b"\r") == b.count(b"\r\n"), "%s 有游离 CR" % p.name
    return b.decode("utf-8")


def write_crlf(p: Path, s: str) -> None:
    b = s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0, "CRCRLF"
    assert b.count(b"\r\n") == b.count(b"\n"), "不是纯 CRLF"
    p.write_bytes(b)


def main() -> int:
    cur = read_crlf(SMOKE).replace("\r\n", "\n")
    n_guard_before = len(re.findall(r"if not check_v\d+_\w+\(\):", cur))

    # ① SRC
    if SRC_NEW in cur:
        print("  · ① SRC 已指向 v1.23.23")
    else:
        assert cur.count(SRC_OLD) == 1, "SRC 行命中 %d 次" % cur.count(SRC_OLD)
        cur = cur.replace(SRC_OLD, SRC_NEW)
        print("  ✓ ① SRC -> 元DGTF-V1.23.23.py")

    # ② 判据函数
    if "def check_v12323_view_echo_full():" in cur:
        print("  · ② 判据函数已存在")
    else:
        assert cur.count(FUNC_ANCHOR) == 1, "函数锚点命中 %d 次" % cur.count(FUNC_ANCHOR)
        ast.parse(CHECK)
        cur = cur.replace(FUNC_ANCHOR, CHECK + FUNC_ANCHOR)
        print("  ✓ ② 注入 check_v12323_view_echo_full（AST 预检通过）")

    # ③ 守卫
    guard_inserted = False
    if "if not check_v12323_view_echo_full():" in cur:
        print("  · ③ main 守卫已接")
    else:
        assert cur.count(GUARD_ANCHOR) == 1, "守卫锚点命中 %d 次" % cur.count(GUARD_ANCHOR)
        cur = cur.replace(GUARD_ANCHOR, GUARD_ANCHOR + GUARD_NEW)
        guard_inserted = True
        print("  ✓ ③ main 里接上守卫")

    write_crlf(SMOKE, cur)

    # ④ 结构性自检（重新读盘）
    back = read_crlf(SMOKE).replace("\r\n", "\n")
    ast.parse(back)
    n_guard_after = len(re.findall(r"if not check_v\d+_\w+\(\):", back))
    assert n_guard_after == n_guard_before + (1 if guard_inserted else 0), \
        "守卫数 %d -> %d（只许 +%d）" % (n_guard_before, n_guard_after,
                                      1 if guard_inserted else 0)
    assert 'SRC = HERE / "元DGTF-V1.23.23.py"' in back
    assert back.count("def check_v12323_view_echo_full():") == 1
    assert back.count("def check_v12322_web_hits_dump():") == 1, "老判据被抹掉了"
    print("  ✓ ④ 自检：AST 通过 / 守卫 %d -> %d / 老判据仍在" % (n_guard_before, n_guard_after))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""[v1.23.39 补丁] smoke_test.py：SRC 切 V1.23.39 + 加 check_v12339_ondemand。

★ 真跑链仍在跑 v1.23.38（CLI 直接加载引擎文件，不读 smoke_test）
  ⇒ 这里切 SRC **不影响**正在跑的三场实验。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"

OLD_SRC = 'SRC = HERE / "元DGTF-V1.23.38.py"'
NEW_SRC = 'SRC = HERE / "元DGTF-V1.23.39.py"'

NEW_FN = '''def check_v12339_ondemand():
    """[v1.23.39] 按需联网**四层一致**：声明即查，不再被逐环节静态开关挡。

    ★ 问题（用户口径「四个层都应该一致，按需联网检索」）：
      v1.23.36 起「所有层都能联网」说的是**代码路径**（修行层硬豁免已取消）；
      但 `WebSearchGate.allow` 仍要求 `stages.<环节>` 静态授权，而 37 个开关
      默认只开 5 个、**修行层一个都没开** ⇒ 修行层环节即使写了
      `===WEB-NEED===` 声明也会被 `stage 'ing' 未授权` 挡掉
      ⇒ **声明了却查不到 = 四层行为不一致**。
    ★ 修法：`on_demand=True`（仅来自 `used_as == "record"`）跳过静态授权，
      **总闸 / 连续失败降级 / 三层配额一条不减**。
    ★ 四层验证：正（修行层声明即放行）+ 负一（总闸关仍拒）
      + 负二（配额打满仍拒）+ 负三（非按需路径仍受开关管）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")

    # ── 静态：on_demand 的产生点必须唯一 ──
    _n = len(re.findall(r\'on_demand\\s*=\\s*\\(str\\(used_as\\)\\s*==\\s*"record"\\)\',
                        src))
    if _n != 1:
        bad.append("[按需四层] `on_demand` 产生点 %d 处（要求 1：只从 "
                   "used_as=record 来）" % _n)
    if "on_demand: bool = False" not in src:
        bad.append("[按需四层] `allow` 缺 `on_demand` 形参")

    # ── 构造性：直接驱动 WebSearchGate（真对象）──
    def _cfg(en=True):
        return {"web_search": {"enabled": en,
                               "stages": {"research_evidence": True}}}

    try:
        g = mod.WebSearchGate(_cfg(True), run_id="smoke")
        # 正：修行层环节（未授权）按需放行
        ok, why = g.allow("ing", 1, on_demand=True)
        if not ok:
            bad.append("[按需四层] 修行层按需仍被拒：%s（四层不一致没修好）"
                       % why)
        # 负三：非按需路径仍受逐环节开关管
        if g.allow("ing", 1)[0]:
            bad.append("[按需四层] 非按需路径被放行（静态开关失效！）")
        # 已授权 stage 两路径都放行
        if not g.allow("research_evidence", 1, on_demand=True)[0]:
            bad.append("[按需四层] 已授权 stage 的按需路径反被拒")
        if not g.allow("research_evidence", 1)[0]:
            bad.append("[按需四层] 已授权 stage 的常规路径被拒（回归）")
        # 负一：总闸关 ⇒ 按需也拒
        g2 = mod.WebSearchGate(_cfg(False), run_id="smoke")
        if g2.allow("ing", 1, on_demand=True)[0]:
            bad.append("[按需四层] 总闸关时按需仍放行（成本闸门失效！）")
        # 负二：配额打满 ⇒ 按需也拒
        _c3 = _cfg(True)
        _c3["web_search"]["quota"] = {"per_run_total": 2,
                                      "per_stage_total": 8,
                                      "per_stage_round": 2}
        g3 = mod.WebSearchGate(_c3, run_id="smoke")
        for _i in range(2):
            g3.note_call("ing", 1)
        ok3, why3 = g3.allow("ing", 1, on_demand=True)
        if ok3:
            bad.append("[按需四层] 配额打满后按需仍放行（按需=无限检索！）")
        elif "配额" not in why3:
            bad.append("[按需四层] 配额拒绝原因不含「配额」：%s" % why3)
    except Exception as _e:
        bad.append("[按需四层] Gate 驱动抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.39 按需联网四层一致（修行层声明即查 · 非按需仍受开关 · "
          "总闸/配额照旧 · on_demand 单一来源）全过")
    return True


def check_v12338_relax_targets():'''

CALL_OLD = """    if not check_v12338_relax_targets():
        return 1"""
CALL_NEW = """    if not check_v12339_ondemand():
        return 1
    if not check_v12338_relax_targets():
        return 1"""


def _rw(p, fn):
    raw = p.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 不是纯 CRLF" % p.name
    assert b"\r\r\n" not in raw, "%s 含 CRLF 双写" % p.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out, "%s 写出后含 CRLF 双写" % p.name
    assert out.count(b"\n") == out.count(b"\r\n"), "%s 写出后不是纯 CRLF" % p.name
    p.write_bytes(out)


def apply(s):
    n = s.count(OLD_SRC)
    assert n == 1, "SRC 锚点命中 %d 次（要求 1）" % n
    s = s.replace(OLD_SRC, NEW_SRC)
    n = s.count("def check_v12338_relax_targets():")
    assert n == 1, "插入锚点命中 %d 次（要求 1）" % n
    s = s.replace("def check_v12338_relax_targets():", NEW_FN)
    n = s.count(CALL_OLD)
    assert n == 1, "调用锚点命中 %d 次（要求 1）" % n
    s = s.replace(CALL_OLD, CALL_NEW)
    return s


_rw(SM, apply)
raw = SM.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
assert b"\r\r\n" not in raw
s = raw.decode("utf-8")
assert s.count("def check_v12339_ondemand():") == 1
assert s.count("if not check_v12339_ondemand():") == 1
assert 'SRC = HERE / "元DGTF-V1.23.39.py"' in s
import ast
ast.parse(s)
print("[ok] smoke_test.py：SRC=V1.23.39 + check_v12339_ondemand + 调用")
print("[ok] 行数（LF 计）=", s.count("\n"), "| 纯 CRLF | AST OK")
# -*- coding: utf-8 -*-
"""[v1.23.39 补丁] 按需联网**四层一致**：声明即查，不再被逐环节静态开关挡。

【问题（用户口径：四个层都应该一致，按需联网检索）】
  v1.23.36 起「所有层都能联网」说的是**代码路径**（修行层硬豁免已取消）；
  但 `WebSearchGate.allow` 还要求 `stages.<环节>` 静态授权，而 37 个环节开关
  里默认只开 5 个（研究/对撞/元层），**修行层一个都没开**
  ⇒ 修行层环节即使在产出里写了 `===WEB-NEED===` 声明，也会被
  `stage 'ing' 未授权` 挡掉 ⇒ **声明了却查不到 ⇒ 四层行为不一致**。

【改法（两处，都在既有函数体内）】
  ① `WebSearchGate.allow(..., on_demand=False)`：`on_demand=True` 时
     **跳过 `stages` 静态授权**（那份开关只管「引擎主动注入」那一路）。
  ② `MetaDGTF._web_search`：`used_as == "record"`（= 按需声明路径）
     ⇒ 传 `on_demand=True`。

【成本闸门一条不减】
  总闸 `web_search.enabled` / 连续失败降级 / 三层配额
  （per_run_total / per_stage_total / per_stage_round）**全部照旧**
  ⇒ 不声明仍零调用；声明多了仍被配额压住。

协议：纯 CRLF 往返；锚点命中 == 1；写完 AST + 自检。
"""
from pathlib import Path

TGT = Path(__file__).resolve().parent / "元DGTF-V1.23.39.py"

# ── ① Gate.allow：加 on_demand 形参 + 跳过静态授权 ───────────────────
OLD_ALLOW = '''    def allow(self, stage: str, round_no: int) -> Tuple[bool, str]:
        if not bool(self.cfg.get("enabled", False)):
            return False, "web_search 未启用（默认关）"
        # ★ [运行中放宽] `_relaxed` 由心跳调度（经控制面）在**本次跑内**填充，
        #   **不改配置**（`cfg` 只读）⇒ 放开的只是「授权」这一道；
        #   配额 / 连续失败降级 / 各 stage 上限**照旧生效**（可控性不降）。
        _relaxed = getattr(self, "_relaxed", None) or ()
        if not bool((self.cfg.get("stages") or {}).get(stage, False)) \\
                and stage not in _relaxed:
            return False, "stage " + repr(stage) + " 未授权"'''

NEW_ALLOW = '''    def allow(self, stage: str, round_no: int,
              on_demand: bool = False) -> Tuple[bool, str]:
        if not bool(self.cfg.get("enabled", False)):
            return False, "web_search 未启用（默认关）"
        # ★ [按需四层一致] `on_demand=True`（环节自己在产出里声明了
        #   `===WEB-NEED===`）⇒ **跳过 `stages` 静态授权**：那份开关管的是
        #   「引擎主动注入」那一路；声明是**环节自己的判断**，若仍被 `stages`
        #   挡住 ⇒ 修行层永远查不到（37 键默认只开 5 个，无一个属修行层）
        #   ⇒ **四层行为不一致**（用户口径：四层都应该一致，按需联网检索）。
        # ★ **成本闸门一条不减**：总闸（上面已查）/ 连续失败降级 / 三层配额
        #   （per_run_total / per_stage_total / per_stage_round）全部照旧
        #   ⇒ 不声明仍**零调用**；声明多了仍被配额压住。
        # ★ [运行中放宽] `_relaxed` 由心跳调度（经控制面）在**本次跑内**填充，
        #   **不改配置**（`cfg` 只读）⇒ 放开的只是「授权」这一道；
        #   配额 / 连续失败降级 / 各 stage 上限**照旧生效**（可控性不降）。
        _relaxed = getattr(self, "_relaxed", None) or ()
        if not on_demand \\
                and not bool((self.cfg.get("stages") or {}).get(stage, False)) \\
                and stage not in _relaxed:
            return False, "stage " + repr(stage) + " 未授权"'''

# ── ② _web_search：按需路径传 on_demand ─────────────────────────────
OLD_CALL = '''            ok, why = gate.allow(stage, int(round_no))'''
NEW_CALL = '''            # ★ [按需四层一致] `used_as == "record"` = 这批检索来自环节的
            #   `===WEB-NEED===` 声明 ⇒ 按需授权（跳过逐环节静态开关，
            #   仍过总闸 + 三层配额）。其余（"evidence" 等）是引擎主动注入，
            #   维持「必须显式开该环节开关」的原语义。
            ok, why = gate.allow(stage, int(round_no),
                                 on_demand=(str(used_as) == "record"))'''


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
    n = s.count(OLD_ALLOW)
    assert n == 1, "allow 锚点命中 %d 次（要求 1）" % n
    s = s.replace(OLD_ALLOW, NEW_ALLOW)

    n = s.count(OLD_CALL)
    assert n == 1, "_web_search 的 gate.allow 调用锚点命中 %d 次（要求 1）" % n
    s = s.replace(OLD_CALL, NEW_CALL)

    # 自检：新增记号各 1 次
    for tok, want in (("on_demand: bool = False", 1),
                      ('on_demand=(str(used_as) == "record")', 1)):
        got = s.count(tok)
        assert got == want, "自检 %r 出现 %d 次（要求 %d）" % (tok, got, want)
    return s


_rw(TGT, apply)

raw = TGT.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
assert b"\r\r\n" not in raw
src = raw.decode("utf-8")
import ast
ast.parse(src)
print("[ok] 补丁已写入 %s" % TGT.name)
print("[ok] 行数（LF 计）=", src.count("\n"), "| 纯 CRLF | AST OK")
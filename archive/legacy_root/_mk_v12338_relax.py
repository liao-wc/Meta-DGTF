# -*- coding: utf-8 -*-
"""[v1.23.38 补丁2] `_TICK_WEB_RELAX` 放宽目标表：按同族补漏项。

现表：("ing", "probe_research", "probe_duel", "probe_meta")  —— 4 个
补入：he / phase_probe / expand_pair / expand_pair_merged_once      —— 4 个 ⇒ 共 8

依据（"停滞时最需要外部刺激的那一类"，与既有 4 个同类）：
  · he                     —— 「和」环节，与表内 `ing`（推理）**对偶**；漏了它不对称
  · phase_probe            —— 阶段探针，与表内三类 `probe_*` **同族**
  · expand_pair            —— 展开对撞对：停滞 = 没有新对 ⇒ 外部素材出对
  · expand_pair_merged_once—— 同上（合并路径）
★ 全部只在「上一圈零增量 + 联网总闸已开」时经 ControlSurface 放宽 ⇒ 默认零行为差。
★ 必须与 `web_search.stages` 对齐（否则放宽了也没用）—— 见配套判据。

协议：纯 CRLF；锚点断言 ==1；一律 Write 工具写脚本。
"""
from pathlib import Path

TGT = Path(__file__).resolve().parent / "元DGTF-V1.23.38.py"

OLD = '''    #: [心跳] 允许被「放宽联网」的环节 —— 只列**最需要外部刺激**的那一类。
    #: ★ 不列全 30 个：放宽是**有代价**的（每次调用都检索），只挑对撞/探针这类
    #:   「卡住时最该问外面」的环节。
    _TICK_WEB_RELAX = ("ing", "probe_research", "probe_duel", "probe_meta")'''

NEW = '''    #: [心跳] 允许被「放宽联网」的环节 —— 只列**最需要外部刺激**的那一类。
    #: ★ 不列全 30 个：放宽是**有代价**的（每次调用都检索），只挑对撞/探针这类
    #:   「卡住时最该问外面」的环节。
    #: ★ 按**同族补漏**扩展 4 个（4 → 8）：
    #:   · `he` —— 「和」环节，与表内 `ing`（推理）**对偶**（缺它不对称）
    #:   · `phase_probe` —— 阶段探针，与表内三类 `probe_*` **同族**
    #:   · `expand_pair` / `expand_pair_merged_once` —— 展开对撞对：
    #:     停滞（池零增量）= 没有新对 ⇒ 正是该问外面的时刻。
    #:   ★ 每个成员**必须在 `web_search.stages` 里存在**（否则放宽了也没用）——
    #:     由冒烟 `check_v12338_relax_targets` 与 `web_search.stages` 两向对账。
    _TICK_WEB_RELAX = ("ing", "probe_research", "probe_duel", "probe_meta",
                       "he", "phase_probe",
                       "expand_pair", "expand_pair_merged_once")'''


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
    n = s.count(OLD)
    assert n == 1, "放宽表锚点命中 %d 次（要求 1）" % n
    return s.replace(OLD, NEW)


_rw(TGT, apply)

# ── 回读 + 结构自检 ──────────────────────────────────────────────────
raw = TGT.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
assert b"\r\r\n" not in raw
src = raw.decode("utf-8")
import ast
import re

ast.parse(src)
m = re.search(r"_TICK_WEB_RELAX = \(([^)]*)\)", src, re.S)
assert m, "找不到放宽表"
members = re.findall(r'"([a-z_]+)"', m.group(1))
assert len(members) == 8, "放宽表成员数 %d（要求 8）" % len(members)

# ★ 两向对账：每个成员必须能在 web_search.stages 段里找到
y = (Path(__file__).resolve().parent / "dgtf_config.yaml").read_text(
    encoding="utf-8").replace("\r\n", "\n")
_i = y.find("plan_orientation: false")
_j = y.find("as_evidence")
seg = y[_i:_j]
avail = set(re.findall(r"(?m)^    ([a-z_]+): (?:true|false)", seg))
missing = [x for x in members if x not in avail]
assert not missing, "放宽表成员不在 web_search.stages 里：%r" % (missing,)

print("[ok] 放宽表 4 -> 8：", members)
print("[ok] 全部成员在 web_search.stages 中存在（两向对账过）")
print("[ok] 行数（LF 计）=", src.count("\n"), "| 纯 CRLF | AST OK")

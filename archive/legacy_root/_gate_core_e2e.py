# -*- coding: utf-8 -*-
"""[_gate_core_e2e] core_gate 端到端证据：真实引擎 + 出厂 yaml（mock LLM）跑三次。

为什么还要这一条（_gate_core_gate_probe.py 已按源码抽取验证过四类分支）：
  探针证明「那段源码在给定 packed 上的行为」；本脚本证明「真跑 run() 后
  packed 里真的有 core_ok / quality.flags，且 md 渲染得出来」—— 接线可达的
  构造性证明，不是复制一份逻辑自证。

三次跑（同一份出厂 yaml，只改 core_gate 与 LLM 桩）：
  A) warn + 审计通过（真实 fake_call）     ⇒ core_ok=True、无旗标、无告警，md「通过」
  B) warn + 审计有缺口（纯文本桩）          ⇒ core_ok=False、flags 含 core_audit_gaps、
                                              一行 warning，md「有缺口」+「质量线索」
  C) off  + 审计有缺口（同一纯文本桩）      ⇒ 不写 core_ok、不加旗标、不告警（审计照跑）
"""
from __future__ import annotations

import json
import logging
import pathlib
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
import smoke_test as st  # noqa: E402  （导入即打桩 LLM.call；引擎模块在 st.mod）

m = st.mod
ENGINE = st.SRC
_FAKE_CALL = m.LLM.call
_STUB_CALL = lambda system, user, *a, **k: (  # noqa: E731
    "- [concept] 占位候选：一段足够长的占位输出，用来过解析门槛。" * 2)

# 隔离一切侧效应：产物 / 记忆 / bandit / V2 事件 / 跑中快照都落临时目录
_tmp = pathlib.Path(tempfile.mkdtemp(prefix="coregate_"))
_cfg_base = m.load_config(str(HERE / "dgtf_config.yaml"))
_cfg_base.setdefault("output", {})["save_dir"] = str(_tmp / "out")
_cfg_base.setdefault("playbook", {})["dir"] = str(_tmp / "mem")
_cfg_base.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_tmp / "mem")
_cfg_base.setdefault("scheduler", {}).setdefault("v2", {})[
    "eml_path"] = str(_tmp / "v2_events.jsonl")
_orig_ckpt_dir = m.run_ckpt_dir
m.run_ckpt_dir = lambda base=None: _tmp / "ckpt"
(_tmp / "ckpt").mkdir(exist_ok=True)

WARN = []
_log = logging.getLogger("dgtf")


class _Cap(logging.Handler):
    def emit(self, rec):
        try:
            WARN.append(rec.getMessage())
        except Exception:
            pass


_cap = _Cap()
_cap.setLevel(logging.WARNING)
_log.addHandler(_cap)

QUESTION = "一个领域里那些被当作常识的东西是怎么来的，它靠不靠得住。"
FAILS = []


def ck(tag, cond, note=""):
    print(("  ✓ " if cond else "  ✗ ") + tag + (("　" + str(note)[:160]) if note else ""))
    if not cond:
        FAILS.append(tag)


def run_once(tag, gate, stub):
    cfg = json.loads(json.dumps(_cfg_base, ensure_ascii=False))
    cfg["scheduler"]["v2"]["core_gate"] = gate
    m.LLM.call = _STUB_CALL if stub else _FAKE_CALL
    obj = m.MetaDGTF(cfg)
    rid = "COREGATE_%s_%d" % (tag, int(time.time() * 1000) % 100000)
    WARN.clear()
    packed = obj.run(QUESTION, route=["0"], rounds={"0": 1},
                     parallel_mode="serial", run_id=rid)
    md_path = m.save_result(packed, str(_tmp / ("out_" + tag)))
    return packed, pathlib.Path(md_path).read_text(encoding="utf-8"), list(WARN)


def gaps_of(packed):
    return list(((packed.get("v2_shadow") or {}).get("core") or {}).get("gaps") or [])


# ── A) warn + 审计通过 ──
print("── A) core_gate=warn（出厂 yaml）+ 审计通过 ──")
pa, mda, wa = run_once("warn_ok", "warn", stub=False)
core_a = (pa.get("v2_shadow") or {}).get("core") or {}
flags_a = list((pa.get("quality") or {}).get("flags") or [])
ck("A1 v2_shadow.core 存在（审计真跑了）", bool(core_a), sorted(core_a)[:6])
ck("A2 core.ok=True 时 packed.core_ok=True",
   core_a.get("ok") is True and pa.get("core_ok") is True,
   "core.ok=%r core_ok=%r" % (core_a.get("ok"), pa.get("core_ok")))
ck("A3 审计通过 ⇒ quality.flags 不掺 core_audit_gaps",
   "core_audit_gaps" not in flags_a, repr(flags_a))
ck("A4 审计通过 ⇒ 无「核心职责审计有缺口」warning",
   not any("核心职责审计有缺口" in w for w in wa), repr(wa[:2]))
ck("A5 md：层核心职责=通过，且不出现 core_audit_gaps",
   "**层核心职责**: 通过" in mda and "core_audit_gaps" not in mda, "")

# ── B) warn + 审计有缺口 ──
print("── B) core_gate=warn + 审计有缺口（纯文本桩）──")
pb, mdb, wb = run_once("warn_gap", "warn", stub=True)
core_b = (pb.get("v2_shadow") or {}).get("core") or {}
flags_b = list((pb.get("quality") or {}).get("flags") or [])
gaps_b = [str(g) for g in (core_b.get("gaps") or [])]
ck("B1 core 审计确实有缺口（core.ok=False）",
   core_b.get("ok") is False and bool(gaps_b), repr(gaps_b[:4]))
ck("B2 packed.core_ok=False", pb.get("core_ok") is False, repr(pb.get("core_ok")))
ck("B3 quality.flags 追加 core_audit_gaps", "core_audit_gaps" in flags_b, repr(flags_b))
ck("B4 一行「核心职责审计有缺口」warning（带 gaps 摘要；run 不中断）",
   sum(1 for w in wb if "核心职责审计有缺口" in w) == 1
   and "不阻断" in next((w for w in wb if "核心职责审计有缺口" in w), ""),
   repr([w for w in wb if "核心职责审计有缺口" in w]))
ck("B5 md：层核心职责=有缺口，且质量线索可见 core_audit_gaps",
   "**层核心职责**: 有缺口" in mdb and "**质量线索**" in mdb
   and "core_audit_gaps" in mdb, "")

# ── C) off + 审计有缺口 ──
print("── C) core_gate=off + 审计有缺口（同一纯文本桩）──")
pc, mdc, wc = run_once("off_gap", "off", stub=True)
flags_c = list((pc.get("quality") or {}).get("flags") or [])
ck("C1 packed 里没有 core_ok", "core_ok" not in pc,
   sorted(k for k in pc if "core" in k))
ck("C2 quality.flags 不含 core_audit_gaps", "core_audit_gaps" not in flags_c, repr(flags_c))
ck("C3 不产生「核心职责审计有缺口」warning",
   not any("核心职责审计有缺口" in w for w in wc), repr(wc[:2]))
ck("C4 v2_shadow.core 仍被审计（off 只关门禁读数，不关审计）",
   isinstance((pc.get("v2_shadow") or {}).get("core"), dict)
   and "ok" in ((pc.get("v2_shadow") or {}).get("core") or {}), "")
ck("C5 md 不出现 core_audit_gaps（但层核心职责照常渲染）",
   "core_audit_gaps" not in mdc and "**层核心职责**" in mdc, "")

m.LLM.call = _FAKE_CALL
_log.removeHandler(_cap)
m.run_ckpt_dir = _orig_ckpt_dir

summary = {
    "engine": ENGINE.name,
    "A_warn_ok": {"core_ok": pa.get("core_ok"),
                  "core_ok_true": bool(core_a.get("ok")),
                  "has_flag": "core_audit_gaps" in flags_a},
    "B_warn_gap": {"core_ok": pb.get("core_ok"),
                   "core_ok_true": bool(core_b.get("ok")),
                   "gaps": gaps_b[:5],
                   "has_flag": "core_audit_gaps" in flags_b},
    "C_off_gap": {"has_core_ok": "core_ok" in pc,
                  "has_flag": "core_audit_gaps" in flags_c,
                  "core_audited": isinstance((pc.get("v2_shadow") or {}).get("core"), dict)},
}
(HERE / "_gate_core_e2e.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print(json.dumps(summary, ensure_ascii=False, indent=1))
print()
if FAILS:
    print("CORE_GATE E2E FAIL %d：%r" % (len(FAILS), FAILS))
    raise SystemExit(1)
print("CORE_GATE E2E PASS 15 / FAIL 0  （%s）" % ENGINE.name)

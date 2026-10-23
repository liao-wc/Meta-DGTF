# -*- coding: utf-8 -*-
"""v1.23.50 断点续跑 · 开发期构造性验证（mock，零 API）。

判据（与后面进冒烟的版本同源）：
  ① 构造：mock 跑一次 `route=["0"]` + `run_id` ⇒ 引擎自己写出快照（层 0 完成）。
  ② 续跑：`run(route=["0","1"], resume_ckpt=<快照>)` ⇒
     · `_run_layer` 的调用记录里**没有 "0"**（不重跑），**有 "1"**；
     · 最终产物的 `views["0"]` 与快照里的层 0 **逐字相同**（复用，不是重算）；
     · 层 0 的**池**被还原（续跑后的 `pools["0"]` 与快照里的一致）。
  ③ 负对照 A：题面不同 ⇒ **拒绝续跑**（"0" 会重跑）。
  ④ 负对照 B：`parallel_mode != serial` ⇒ **拒绝续跑**。
  ⑤ 记账：快照里 `llm_calls`/`llm_tokens` 是正整数；`route` 非空（死捕获已修）。
  ⑥ 墙钟预算：`max_minutes` 极小 ⇒ 优雅停（`paused`），且**未启动任何层**。
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as S  # noqa: E402  （只借它的 fake_call 打桩 + build_cfg 隔离）

spec = importlib.util.spec_from_file_location("m50", str(HERE / "元DGTF-V1.23.50.py"))
m50 = importlib.util.module_from_spec(spec)
sys.modules["m50"] = m50
spec.loader.exec_module(m50)
m50.LLM.call = S.fake_call          # mock，零 API

bad = []


def ck(tag, cond, note=""):
    print(("  ✓ " if cond else "  ✗ ") + tag + (("  — " + note) if note else ""))
    if not cond:
        bad.append(tag)


_CK = Path(tempfile.mkdtemp(prefix="v50ck_"))
_mem = Path(tempfile.mkdtemp(prefix="v50mem_"))
_orig_dir = m50.run_ckpt_dir
m50.run_ckpt_dir = lambda base=None: _CK      # 快照写临时目录，不碰仓库

Q = "冒烟问题：这件事的边界在哪里（v1.23.50 续跑验证）"


def _cfg(ck=True, interval=0.05):
    c = S.build_cfg(False)
    c["output"]["save_dir"] = str(Path(tempfile.mkdtemp(prefix="v50out_")))
    c["playbook"]["dir"] = str(_mem)
    c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(_mem)
    c["runtime"] = dict(c.get("runtime") or {})
    c["runtime"]["live_checkpoint"] = bool(ck)
    c["runtime"]["ckpt_interval"] = interval
    c["all_on"] = False
    return c


# ── ① 构造快照（层 0 完成） ─────────────────────────────────────────
m1 = m50.MetaDGTF(_cfg())
r1 = m1.run(Q, route=["0"], rounds={"0": 1}, parallel_mode="serial",
            run_id="V50T1")
_rid = list(_CK.glob("V50T1.json"))
ck("① 引擎自己写出快照", bool(_rid), str([p.name for p in _CK.glob('*.json')]))
_snap = _CK / "V50T1.json"
_s0 = json.loads(_snap.read_text(encoding="utf-8"))
ck("① 快照含层 0 的 view", isinstance((_s0.get("views") or {}).get("0"), dict))
ck("⑤ 快照带记账（llm_calls/llm_tokens 正数）",
   int(_s0.get("llm_calls") or 0) > 0 and int(_s0.get("llm_tokens") or 0) > 0,
   "calls=%s tokens=%s" % (_s0.get("llm_calls"), _s0.get("llm_tokens")))
ck("⑤ 快照 route 非空（死捕获已修）", bool(_s0.get("route")), repr(_s0.get("route")))
ck("⑤ 快照 mode=serial", _s0.get("mode") == "serial", repr(_s0.get("mode")))
_pools0 = (_s0.get("pools") or {}).get("0") or {}
ck("⑤ 快照带池（asdict 全字段）", bool(_pools0), "池字段 %d" % len(_pools0))

# 模拟"崩溃"：把状态改成 interrupted（真事故留下的就是 running/interrupted）
_s0["status"] = "interrupted"
_s0["interrupted_why"] = "（测试构造）"
_snap.write_text(json.dumps(_s0, ensure_ascii=False, indent=1), encoding="utf-8")

# ── ② 续跑：层 0 必须被跳过 ─────────────────────────────────────────
_ran = []
_orig_layer = m50.MetaDGTF._run_layer


def _spy(self, entry, n):
    _ran.append(entry)
    return _orig_layer(self, entry, n)


m50.MetaDGTF._run_layer = _spy
try:
    m2 = m50.MetaDGTF(_cfg())
    r2 = m2.run(Q, route=["0", "1"], rounds={"0": 1, "1": 1},
                parallel_mode="serial", run_id="V50T2", resume_ckpt=str(_snap))
finally:
    m50.MetaDGTF._run_layer = _orig_layer

ck("② 续跑没有重跑层 0", "0" not in _ran, "实跑层=%r" % (_ran,))
ck("② 续跑跑了缺的层 1", "1" in _ran, "实跑层=%r" % (_ran,))
_v0_final = (r2.get("views") or {}).get("0")
ck("② 层 0 产物 == 快照里那份（逐字复用）",
   json.dumps(_v0_final, sort_keys=True, ensure_ascii=False, default=str)
   == json.dumps(_s0["views"]["0"], sort_keys=True, ensure_ascii=False, default=str))
_p0 = m2.pools.get("0")
_pl_amps = len(getattr(_p0, "amps", []) or [])
ck("② 层 0 的池被还原（amps 数一致）",
   _pl_amps == len(_pools0.get("amps") or []),
   "续跑池 amps=%d，快照池 amps=%d" % (_pl_amps, len(_pools0.get("amps") or [])))

# ── ③ 负对照 A：题面不同 ⇒ 拒绝续跑 ─────────────────────────────────
_ran2 = []
m50.MetaDGTF._run_layer = _spy
_ran.clear()
m50.MetaDGTF._run_layer = lambda self, e, n: (_ran.append(e), _orig_layer(self, e, n))[1]
try:
    m3 = m50.MetaDGTF(_cfg())
    r3 = m3.run("完全不同的题面（不该续）", route=["0"], rounds={"0": 1},
                parallel_mode="serial", run_id="V50T3", resume_ckpt=str(_snap))
finally:
    m50.MetaDGTF._run_layer = _orig_layer
ck("③ 负对照：题面不同 ⇒ 拒绝续跑（层 0 重跑）", "0" in _ran, "实跑层=%r" % (_ran,))

# ── ④ 负对照 B：非 serial ⇒ 拒绝续跑 ────────────────────────────────
_rs_b = m50.load_resume_snapshot(str(_snap), question=Q, mode="B")
ck("④ 负对照：mode=B ⇒ 拒绝续跑且给理由",
   (not _rs_b.get("ok")) and bool(_rs_b.get("why")), repr(_rs_b.get("why"))[:60])
_rs_ok = m50.load_resume_snapshot(str(_snap), question=Q, mode="serial")
ck("④ 正对照：mode=serial + 同题 ⇒ 允许续跑", bool(_rs_ok.get("ok")))

# ── ⑥ 墙钟预算：极小预算 ⇒ 优雅停、不起新层 ──────────────────────────
_ran3 = []
m50.MetaDGTF._run_layer = lambda self, e, n: (_ran3.append(e), _orig_layer(self, e, n))[1]
try:
    m4 = m50.MetaDGTF(_cfg())
    r4 = m4.run(Q, route=["0", "1"], rounds={"0": 1, "1": 1},
                parallel_mode="serial", run_id="V50T4", max_minutes=1e-6)
finally:
    m50.MetaDGTF._run_layer = _orig_layer
ck("⑥ 预算到点 ⇒ 优雅停（paused）且**没启动任何层**",
   bool(r4.get("paused")) and not _ran3 and list(r4.get("pending_layers") or []) == ["0", "1"],
   "paused=%r ran=%r pending=%r" % (r4.get("paused"), _ran3, r4.get("pending_layers")))
_s4 = json.loads((_CK / "V50T4.json").read_text(encoding="utf-8"))
ck("⑥ 优雅停的快照状态是 paused（可续）", _s4.get("status") == "paused",
   repr(_s4.get("status")))

m50.run_ckpt_dir = _orig_dir
print("\n==== v1.23.50 续跑开发期验证：%s ===="
      % ("全部通过" if not bad else "失败 %d 条：%s" % (len(bad), bad)))
sys.exit(1 if bad else 0)

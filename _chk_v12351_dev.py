# -*- coding: utf-8 -*-
"""v1.23.51 开发期构造性验证：`_eml_finish` 幂等守卫（同一跑次只学一次）。

判据（每条都走**生产入口** `_eml_finish`，不是纯函数）：
  A 新版权：同一份 result 调两次 ⇒ **第二次一点都不改盘**（四个文件逐字节相同）
    + `dup_skipped` 为真
  B 旧版对照：同样两次 ⇒ 盘上**确实变了**（证明判据有牙，不是恒绿）
  C 正对照：换一个 run_id ⇒ 照写（不是「一律跳过」）
  D 续跑对照：同 run_id 但读数不同（模拟 paused 后跑完）⇒ 照写
  E episodes 行数：新版权 5 跑 = 5 条（不是 6 条）

用法：python _chk_v12351_dev.py
"""
import importlib.util
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
Q = "如何利用AI来帮助人类实现财富自由"
FILES = ("episodes.jsonl", "nogoods.jsonl", "playbook.jsonl", "MEMORY.md")
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(p):
    spec = importlib.util.spec_from_file_location("eng_" + p.stem[-6:], str(p))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def mkres(rid, cut=("1",)):
    return {"id": rid, "question": Q,
            "route": ["0", "1", "both", "all"],
            "rounds": {"0": 3, "1": 3, "both": 3, "all": 4},
            "dispatch": {"_parallel_mode": "serial"},
            "views": {e: {"stop_reason": ("体力耗尽（3 圈走满）" if e in cut
                                          else "自然安住"),
                          "duty": {"S": 0.1 if e in ("0", "1") else 0.5}}
                      for e in ("0", "1", "both", "all")},
            "pools": {"1": {"anchors": [], "web_results": []}},
            "tri_consensus": [], "llm_tokens": 10, "llm_calls": 1,
            "_auto_dispatch": {"_history": {}}}


def mkeng(mod, d):
    cfg = dict(mod.DEFAULT_CONFIG)
    cfg["playbook"] = {"mode": "on", "dir": str(d), "top_k": 3,
                       "promote_n": 3, "halflife_days": 14.0}
    return mod.MetaDGTF(cfg)


def snap(d):
    return {n: (d / n).read_bytes() for n in FILES if (d / n).is_file()}


def warm(mod, d):
    """4 跑同向证据 ⇒ 把条目推到 active（这样第 5 跑才会「用到」并写 used_outcomes）。"""
    e = mkeng(mod, d)
    for i in range(1, 5):
        e._eml_finish(mkres("RUN%d" % i))
    return e


def n_eps(mod, d):
    return len(mod.eml_read_jsonl(d / "episodes.jsonl"))


print("=" * 62)
print("【A】新版 v1.23.51：同一份 result 调两次 ⇒ 第二次不改盘")
new = load(HERE / "元DGTF-V1.23.51.py")
dA = pathlib.Path(tempfile.mkdtemp(prefix="v51A_"))
eng = warm(new, dA)
n_before = n_eps(new, dA)
eng._eml_prepare(Q)
eng._eml_apply({"0": 3, "1": 3, "both": 3, "all": 4})
res5 = mkres("RUN5")
blk1 = eng._eml_finish(res5)
s1 = snap(dA)
blk2 = eng._eml_finish(res5)
s2 = snap(dA)
ck(bool(blk1.get("used")), "第 5 跑确实用到了 playbook 条目（否则本判据测不到 used_outcomes）")
ck(blk2.get("dup_skipped") is True, "第二次调用标了 dup_skipped")
ck(s1 == s2, "第二次调用后四个文件**逐字节相同**（盘上一点没变）")
ck(n_eps(new, dA) == n_before + 1,
   "第 5 跑只写 1 条 episode（%d → %d）" % (n_before, n_eps(new, dA)))
_pb = [json.loads(x) for x in (dA / "playbook.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
_dbl = []
for e in _pb:
    c = [x for x in (e.get("used_outcomes") or []) if x.get("run") == "RUN5"]
    if len(c) > 1:
        _dbl.append((e.get("id"), len(c)))
ck(not _dbl, "没有条目把 RUN5 记进 used_outcomes 两次 %r" % (_dbl,))

print("\n【B】旧版 v1.23.50 对照：同样两次 ⇒ 盘上确实变了（判据有牙）")
old = load(HERE / "元DGTF-V1.23.50.py")
dB = pathlib.Path(tempfile.mkdtemp(prefix="v51B_"))
eo = warm(old, dB)
eo._eml_prepare(Q)
eo._eml_apply({"0": 3, "1": 3, "both": 3, "all": 4})
ro5 = mkres("RUN5")
eo._eml_finish(ro5)
t1 = snap(dB)
eo._eml_finish(ro5)
t2 = snap(dB)
_changed = sorted(k for k in t1 if t1.get(k) != t2.get(k))
ck(t1 != t2, "旧版第二次调用**改了盘**（变了：%s）" % ("、".join(_changed) or "?"))
ck(not any("旧版" in b for b in bad), "旧版对照成立（两版行为确实不同）")

print("\n【C】正对照：换 run_id ⇒ 照写（不是「一律跳过」）")
s3 = snap(dA)
blk3 = eng._eml_finish(mkres("RUN6"))
ck(not blk3.get("dup_skipped"), "RUN6 未被误判为重复")
ck(snap(dA) != s3, "RUN6 确实写了库")

print("\n【D】续跑对照：同 run_id 但读数不同 ⇒ 照写（否则完整样本永远进不了库）")
s4 = snap(dA)
blk4 = eng._eml_finish(mkres("RUN5", cut=("0", "1", "both", "all")))
ck(not blk4.get("dup_skipped"), "读数不同的 RUN5 没被挡掉")
ck(snap(dA) != s4, "读数不同的 RUN5 写了库（半程样本可被完整样本补上）")

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)

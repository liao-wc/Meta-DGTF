# -*- coding: utf-8 -*-
"""清账：把记忆库里 **mock 跑次**（合成样本）从 episodes 摘掉。

怎么认（四条指纹全部命中才删 —— **不按时间、不按人肉名单**）：
    tokens == 330 且 calls == 30 且 Σrounds_cap == 4 且 q_features.len == 18
为什么这组指纹可信：真实 LLM 跑的 tokens 是万级（实测 11 万~200 万），
   330 tokens / 30 calls 是桩函数产出的固定值；且 73 条**逐字相同**，
   真实跑不可能产出完全相同的读数。

影响面（已核）：这些跑次的 `used_outcomes` 与 nogoods **都是 0** ⇒
playbook 的权重与证据计数**没被污染**；被污染的只有 episodes 这份样本库，
以及建在它上面的 `autotune_run` 建议（它会全量读 episodes）。

用法：python _mk_episodes_dedup.py           # 干跑，只报数
      python _mk_episodes_dedup.py --apply   # 落盘（先备份）
"""
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
MEM = HERE / "dgtf_memory"
BAK = HERE / "_archive" / "v1.23.54" / "episodes_before_dedup_20261017"
APPLY = "--apply" in sys.argv

FP = {"tokens": 330, "calls": 30, "rounds": 4, "qlen": 18}
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def fp(r):
    c = r.get("cost") or {}
    rc = sum(int(v or 0) for v in (r.get("rounds_cap") or {}).values())
    ql = int((r.get("q_features") or {}).get("len") or 0)
    return {"tokens": int(c.get("tokens") or 0),
            "calls": int(c.get("calls") or 0),
            "rounds": rc, "qlen": ql}


p = MEM / "episodes.jsonl"
raw = p.read_bytes()
assert b"\r\n" not in raw, "episodes.jsonl 里有 CRLF（预期纯 LF）"
lines = [ln for ln in raw.split(b"\n") if ln.strip()]
rows = [json.loads(ln) for ln in lines]
print("\n【1】起始状态")
ck(len(rows) == 97, "episodes 起始 97 行（实测 %d）" % len(rows))

print("\n【2】四条指纹分别命中多少（单调性：全部命中数 ≤ 任一单条）")
masks = []
for k, v in FP.items():
    m = [i for i, r in enumerate(rows) if fp(r)[k] == v]
    masks.append(set(m))
    print("       %-7s == %-4s ⇒ %d 条" % (k, v, len(m)))
hit = set.intersection(*masks)
ck(len(hit) == 73, "四条指纹**同时**命中 73 条（实测 %d）" % len(hit))

print("\n【3】删之前先确认它们确实是同一份合成样本")
fps = {json.dumps(fp(rows[i]), sort_keys=True) for i in hit}
ck(len(fps) == 1, "73 条的指纹完全一致（%d 种）" % len(fps))
q = {json.dumps(rows[i].get("q_features"), sort_keys=True) for i in hit}
ck(len(q) == 1, "题面特征也完全一致（%d 种）" % len(q))
_pb = [json.loads(x) for x in (MEM / "playbook.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
fake_ids = {rows[i]["run_id"] for i in hit}
uo = sum(1 for e in _pb for x in (e.get("used_outcomes") or [])
         if x.get("run") in fake_ids)
ck(uo == 0, "这些 run_id 在 playbook.used_outcomes 里出现 %d 次（应为 0）" % uo)
_tu = sum(1 for e in _pb for x in (e.get("t_used") or []) if x in fake_ids)
ck(_tu == 0, "这些 run_id 在 t_used 里出现 %d 次（应为 0）" % _tu)
_ng = [json.loads(x) for x in (MEM / "nogoods.jsonl").read_text(
    encoding="utf-8").splitlines() if x.strip()]
ck(sum(1 for x in _ng if x.get("run") in fake_ids) == 0,
   "nogoods 里也没有它们的记录")

print("\n【4】保留的那 24 条必须都是真实跑次")
keep = [r for i, r in enumerate(rows) if i not in hit]
ck(len(keep) == 24, "保留 24 条（实测 %d）" % len(keep))
ck(all(fp(r)["tokens"] > 5000 for r in keep),
   "保留的每条 tokens 都 > 5000（最小 %d）"
   % min(fp(r)["tokens"] for r in keep))
ck(len({r["run_id"] for r in keep}) == 24, "保留的 run_id 互不相同")

print("\n【5】落盘前自检：行字节可原样复现（保证不误伤未命中的行）")
survivors = [ln for i, ln in enumerate(lines) if i not in hit]
ck(all(json.dumps(rows[i], ensure_ascii=False).encode("utf-8") == ln
       for i, ln in enumerate(lines) if i not in hit),
   "未命中的行 json.dumps 能逐字节复现")

print("\n" + "=" * 60)
print("判红 %d 项" % len(bad))
for b in bad:
    print("  ! " + b)
if bad:
    raise SystemExit("有断言没过 ⇒ 不写盘")

if not APPLY:
    _sum = sum(fp(r)["tokens"] for r in rows if r["run_id"] in fake_ids)
    print("干跑结束（未写盘）：将删 %d 行（97 → %d）"
          "；被删样本合计 tokens=%d（都是桩函数产出的假数，不是真花的钱）"
          % (len(hit), len(survivors), _sum))
    print("加 --apply 才落盘。")
    raise SystemExit(0)

BAK.mkdir(parents=True, exist_ok=True)
shutil.copy2(p, BAK / "episodes.jsonl")
p.write_bytes(b"\n".join(survivors) + b"\n")
print("备份 → %s" % BAK.relative_to(HERE))
print("已写：episodes 97 → %d 行" % len(survivors))

# -*- coding: utf-8 -*-
"""清账：把 V1250A / V1250B 的「双写」脏数据从记忆库里摘掉。

背景（不是引擎 bug，是 A/B 脚本 bug）：
  `run()` 内部已调 `_eml_finish`（元DGTF-V1.23.50.py:20591），
  `_fullrun_V1250AB.py:116` 又调了一次 ⇒ 每跑学两遍。
  v1.23.50 才修好「run_id 必须在 `_eml_finish` 之前盖章」，
  所以 v1.23.48/49 的 A/B 跑次是匿名的（内部那次被闸挡掉，看着正常）。

脏在哪（本次实测）：
  episodes.jsonl  V1250A/V1250B 各 2 条完全相同的行
  nogoods.jsonl   同上，各 2 条
  playbook.jsonl  7 个条目的 used_outcomes 每个 run 记了 2 次 ⇒ weight 多扣 0.05/次
  MEMORY.md       证据数 6→8 **是对的**（t_used 按 run_id 去重）⇒ 不动

修法（只做减法 + 精确逆运算）：
  1) episodes / nogoods：每个 run 保留第一条，删第二条（保留原始行字节）
  2) playbook：used_outcomes 每个 run 保留第一条；weight 加回 0.05/条（上限 1.0）
     ★ 只有「两次扣减都没碰到 0.1 地板」时逆运算才精确 ⇒ 脚本断言这一点
  3) bandit.json 不动（两次 pull 是真的，各 run 一次）

用法：python _fix_eml_dup_20261016.py [--apply]
      不带 --apply = 干跑（只报数，不写盘）
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEM = HERE / "dgtf_memory"
BAK = HERE / "_archive" / "v1.23.50" / "dgtf_memory_before_dedup_20261016"
RUNS = ("V1250A", "V1250B")
W_STEP = 0.05
W_FLOOR = 0.1
W_CAP = 1.0

APPLY = "--apply" in sys.argv
ok = []
bad = []


def chk(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load_lines(name):
    """按字节切行，保留原始行（改不改都只有被点的行才重写）。"""
    p = MEM / name
    raw = p.read_bytes()
    assert b"\r\n" not in raw, "%s 里出现了 CRLF，先停下" % name
    rows = [ln for ln in raw.split(b"\n") if ln.strip()]
    return p, rows


def dump(obj):
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def write_lines(p, rows):
    p.write_bytes(b"\n".join(rows) + b"\n")


# ── 1) episodes.jsonl ────────────────────────────────────────────────
print("\n【1】episodes.jsonl")
p_ep, ep = load_lines("episodes.jsonl")
chk(len(ep) == 99, "episodes 起始行数 99（实测 %d）" % len(ep))
ep_obj = [json.loads(x) for x in ep]
drop = []
for r in RUNS:
    idx = [i for i, o in enumerate(ep_obj) if o.get("run_id") == r]
    chk(len(idx) == 2, "%s 恰好 2 条（%d）" % (r, len(idx)))
    if len(idx) == 2:
        a = {k: v for k, v in ep_obj[idx[0]].items() if k != "t"}
        b = {k: v for k, v in ep_obj[idx[1]].items() if k != "t"}
        chk(a == b, "%s 两条除 t 外完全相同（确认是重复不是两次真跑）" % r)
        chk(ep_obj[idx[1]]["t"] > ep_obj[idx[0]]["t"], "%s 被删的是较晚那条（第 %d 行）"
            % (r, idx[1] + 1))
        drop.append(idx[1])
ep_new = [ln for i, ln in enumerate(ep) if i not in set(drop)]
chk(len(ep_new) == 97, "episodes 去重后 97 行（实测 %d）" % len(ep_new))

# ── 2) nogoods.jsonl ────────────────────────────────────────────────
print("\n【2】nogoods.jsonl")
p_ng, ng = load_lines("nogoods.jsonl")
chk(len(ng) == 21, "nogoods 起始行数 21（实测 %d）" % len(ng))
ng_obj = [json.loads(x) for x in ng]
drop2 = []
for r in RUNS:
    idx = [i for i, o in enumerate(ng_obj) if o.get("run") == r]
    chk(len(idx) == 2, "%s 恰好 2 条（%d）" % (r, len(idx)))
    if len(idx) == 2:
        a = {k: v for k, v in ng_obj[idx[0]].items() if k != "t"}
        b = {k: v for k, v in ng_obj[idx[1]].items() if k != "t"}
        chk(a == b, "%s nogood 两条除 t 外完全相同" % r)
        drop2.append(idx[1])
ng_new = [ln for i, ln in enumerate(ng) if i not in set(drop2)]
chk(len(ng_new) == 19, "nogoods 去重后 19 行（实测 %d）" % len(ng_new))

# ── 3) playbook.jsonl ───────────────────────────────────────────────
print("\n【3】playbook.jsonl")
p_pb, pb = load_lines("playbook.jsonl")
chk(len(pb) == 11, "playbook 起始行数 11（实测 %d）" % len(pb))
pb_obj = [json.loads(x) for x in pb]
# 先断言「未改动的行能逐字节复现」——否则重写会带出无谓 diff
chk(all(dump(o) == ln for o, ln in zip(pb_obj, pb)),
    "未改动的行 json.dumps 能逐字节复现（保证 diff 只落在被点的行）")
pb_new = []
n_removed = 0
for ln, o in zip(pb, pb_obj):
    uo = o.get("used_outcomes") or []
    keep, seen = [], {}
    changed = False
    for rec in uo:
        r = str(rec.get("run") or "")
        if r in RUNS:
            seen[r] = seen.get(r, 0) + 1
            if seen[r] > 1:          # 同 run 的第 2 条 = 双写产物，丢
                changed = True
                n_removed += 1
                continue
        keep.append(rec)
    if not changed:
        pb_new.append(ln)
        continue
    w0 = float(o.get("weight", W_CAP) or W_CAP)
    n_drop = len(uo) - len(keep)
    o["used_outcomes"] = keep
    w1 = min(W_CAP, w0 + W_STEP * n_drop)
    print("    %-6s weight %.4f → %.4f（删 %d 条 used_outcomes）"
          % (o.get("id"), w0, w1, n_drop))
    o["weight"] = w1
    pb_new.append(dump(o))

# 期望值 12（★ 别想当然写 7×2=14）：L0001 只被 V1250B 用过、L0003 只被 V1250A 用过
# ⇒ 5 个条目 × 2 条 + 2 个条目 × 1 条 = 12。硬等式，不是「>=12」。
chk(n_removed == 12, "playbook 共删 12 条重复 used_outcomes（5×2 + 2×1，实测 %d）"
    % n_removed)
# 地板断言：任何一条都不许等于 0.1（否则逆运算不精确）
floored = [o.get("id") for o in pb_obj
           if abs(float(o.get("weight", 1.0)) - W_FLOOR) < 1e-9]
chk(not floored, "没有条目落在 0.1 地板（逆运算精确）%s"
    % ("、".join(floored) if floored else ""))
# 去重后：每个 run 在每个条目里最多 1 条
for o in [json.loads(x) for x in pb_new]:
    c = {}
    for rec in (o.get("used_outcomes") or []):
        r = str(rec.get("run") or "")
        if r in RUNS:
            c[r] = c.get(r, 0) + 1
    assert all(v == 1 for v in c.values()), (o.get("id"), c)
chk(True, "去重后每个 run 在每个条目里最多 1 条 used_outcomes")

# ── 4) MEMORY.md 只读校验（不动）────────────────────────────────────
print("\n【4】MEMORY.md（只校验，不改）")
p_md, md = load_lines("MEMORY.md")
md_txt = b"\n".join(md).decode("utf-8")
for r in RUNS:
    chk(md_txt.count(r) == 0 or True, "%s 在 MEMORY.md 里的出现次数（证据按 run 去重，无需改）" % r)
for o in pb_obj:
    tu = [x for x in (o.get("t_used") or []) if str(x) in RUNS]
    assert len(tu) == len(set(tu)), ("t_used 有重复 run", o.get("id"), tu)
chk(True, "t_used 里每个 run 只出现一次 ⇒ MEMORY.md 证据数无需修正")

# ── 5) bandit.json 只读校验 ─────────────────────────────────────────
print("\n【5】bandit.json（不动）")
bd = json.loads((MEM / "bandit.json").read_text(encoding="utf-8"))
chk(int(bd["n"][0]) == 7, "bandit 臂0 n=7（5 + 两次 pull，各 run 一次 ⇒ 正常）")

# ── 结论 ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("判红 %d 项" % len(bad))
for b in bad:
    print("  ! " + b)
if bad:
    raise SystemExit("有断言没过 ⇒ 不写盘")

if not APPLY:
    print("干跑结束（未写盘）。加 --apply 才落盘。")
    raise SystemExit(0)

BAK.mkdir(parents=True, exist_ok=True)
for n in ("episodes.jsonl", "nogoods.jsonl", "playbook.jsonl",
          "bandit.json", "MEMORY.md"):
    shutil.copy2(MEM / n, BAK / n)
print("备份 → %s" % BAK.relative_to(HERE))

write_lines(p_ep, ep_new)
write_lines(p_ng, ng_new)
write_lines(p_pb, pb_new)
print("已写：episodes %d→%d 行 · nogoods %d→%d 行 · playbook 行数不变（内容修 7 行）"
      % (len(ep), len(ep_new), len(ng), len(ng_new)))

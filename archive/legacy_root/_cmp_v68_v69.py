# -*- coding: utf-8 -*-
"""[v1.21.69 验收] V68(改前) vs V69(改后) 真跑对照 + A 的不变量校验。

用法：
  python _cmp_v68_v69.py                 # 对照 V68 / V69
  python _cmp_v68_v69.py --ampcheck verif_V69B.log   # 只跑 A 的不变量校验

A 的不变量（**与版本无关、只看一次运行**）：
  各圈 `_amp_cand_count` 之和  ==  `[P3] & 候选（各圈累计）N 条` 里的 N。
  旧实现在 `_b_merge` 把累加写在 `for a in view.amps` 体内 ⇒
    N_旧 = Σ_r ( count_r × len(view.amps_r) )，空 amps 的圈整圈漏掉。
  所以顺便给出 N_旧 的预测值，用来判断这一次运行有没有判别力
  （串行通道本来就对，两者会相等 —— 那不是"修好了"，是"没测到"）。
"""
import argparse
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load_json(p: Path):
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8", errors="replace"))


def _log(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, path + "/[%d]" % i)
    else:
        yield path, o


def _dump_blocks(log: str):
    """切出每个留痕段：(kind, entry, head, body)。"""
    out = []
    lines = log.split("\n")
    for i, l in enumerate(lines):
        m = re.search(r"║ (圈全量留痕|收尾留痕) · entry=(\S+) · ([^\n]*)", l)
        if not m:
            continue
        body = []
        for l2 in lines[i + 1:]:
            body.append(l2)
            if "全量留痕结束" in l2:
                break
        out.append((m.group(1), m.group(2), m.group(3).strip(),
                    "\n".join(body)))
    return out


def _field_n(body: str, key: str):
    m = re.search(r"^   \u251c " + key + r"\uff1a\w+ (\d+) 项", body, re.M)
    return int(m.group(1)) if m else None


def _p3_lines(d):
    """产物里所有 [P3] 行 → {entry: 数值}（路径形如 /views/<entry>/meta/[i]）。"""
    out = {}
    for p, v in _walk(d or {}):
        s = str(v)
        if "/meta/" not in p or "[P3]" not in s:
            continue
        m = re.search(r"\[P3\] & 候选（各圈累计）(\d+) 条", s)
        if not m:
            continue
        em = re.search(r"/views/([^/]+)/meta/", p)
        out[em.group(1) if em else "?"] = (int(m.group(1)), s)
    return out


def ampcheck(log_path: Path):
    """A 的不变量校验。

    不变量（只在**跑了 `_b_merge` 的通道**上才有新旧差别）：
        第 e 层各圈 `_amp_cand_count` 之和  ==  该层 `[P3] & 候选（各圈累计）N 条` 的 N
    旧实现在 `_b_merge` 把累加写在 `for a in view.amps` 体内：
        N_旧 = Σ_r ( count_r × len(view.amps_r) )，且 amps 为空的那一圈整圈漏掉。
    串行通道（`_run_layer`）本来就是对的 ⇒ 在 serial 运行上两者必然相等，
    这时本次运行**对 A 没有判别力**（不是"修好了"，是"没测到"）。
    """
    log = _log(log_path)
    if not log:
        print(f"（没有 {log_path.name}）")
        return False
    m_mode = re.search(r"^\[banner\] .*? mode=(\S+)", log, re.M)
    mode = m_mode.group(1) if m_mode else "?"
    tag = log_path.stem.replace("verif_", "")
    full = _load_json(HERE / f"verif_{tag}.full.json")
    p3 = _p3_lines(full)
    blocks = _dump_blocks(log)
    rounds = [b for b in blocks if b[0] == "圈全量留痕"]
    print(f"== A 不变量校验 · {log_path.name}（mode={mode}）==")
    print(f"留痕段：圈 {len(rounds)} / 收尾 {len(blocks) - len(rounds)}")
    per = {}
    for kind, entry, head, body in rounds:
        m = re.search(r"[\u251c] _amp_cand_count\uff1a(\d+)", body)
        cnt = int(m.group(1)) if m else 0
        per.setdefault(entry, []).append((head, cnt, _field_n(body, "amps") or 0))
    ok_all = True
    has_disc = False
    _par = mode not in ("serial",)
    print("  entry | 各圈 (角色, _amp_cand_count, len(amps))")
    for entry, rows in per.items():
        txt = " ".join(f"({h.split('·')[0].strip() or h[:6]},{c},{n})"
                       for h, c, n in rows)
        new_pred = sum(c for _, c, _ in rows)
        old_pred = sum(c * n for _, c, n in rows)
        actual = p3.get(entry, (None, ""))[0]
        disc = _par and old_pred != new_pred
        has_disc = has_disc or disc
        good = actual is not None and actual == new_pred
        ok_all = ok_all and good
        _note = (f"　旧实现预测={old_pred}　"
                 f"{'旧≠新 ⇒ 有判别力' if disc else '旧=新'}"
                 if _par else "　（serial 不用 _b_merge，旧实现预测不适用）")
        print(f"  {entry:5s} | {txt}")
        print(f"        Σcount={new_pred}　产物 [P3]={actual}"
              f"　{'✅一致' if good else '❌不一致'}{_note}")
    print(f"  → 与新时代码一致：{'✅' if ok_all else '❌'}")
    if mode == "serial":
        print("  → 判别力：❌ 这条通道（serial / `_run_layer`）本来就是对的，"
              "新旧输出相同 ⇒ 要验 A 必须跑 mode ∈ {B,C,D,E,F,G,H}")
    else:
        print(f"  → 判别力：{'✅ 有' if has_disc else '❌ 无'}"
              f"（旧实现预测与新实现预测{'不同' if has_disc else '相同'}）")
    return ok_all and (mode != "serial") and has_disc


def report(tag_a="V68", tag_b="V69"):
    fa = _load_json(HERE / f"verif_{tag_a}.full.json")
    fb = _load_json(HERE / f"verif_{tag_b}.full.json")
    sa = _load_json(HERE / f"verif_{tag_a}.json")
    sb = _load_json(HERE / f"verif_{tag_b}.json")
    la, lb = _log(HERE / f"verif_{tag_a}.log"), _log(HERE / f"verif_{tag_b}.log")
    print(f"===== 真跑对照 {tag_a}（改前） vs {tag_b}（改后） =====")
    if fb is None:
        print(f"（还没有 verif_{tag_b}.full.json，先把真跑跑完）")
        return

    def _num(log, pat):
        m = re.search(pat, log)
        return m.group(1) if m else "?"

    rows = [
        ("llm_calls", str((sa or {}).get("llm_calls")),
         str((sb or {}).get("llm_calls"))),
        ("tokens", _num(la, r"tokens=(\d+)"), _num(lb, r"tokens=(\d+)")),
        ("耗时", _num(la, r"\[timing\] \d+s = ([\d.]+min)"),
         _num(lb, r"\[timing\] \d+s = ([\d.]+min)")),
        ("tri_state[一致,有效]", str((sa or {}).get("tri_state")),
         str((sb or {}).get("tri_state"))),
        ("views errors", str((sa or {}).get("views_errors")),
         str((sb or {}).get("views_errors"))),
        ("dispatch", _num(la, r"\[dispatch\] (.+?)\n"),
         _num(lb, r"\[dispatch\] (.+?)\n")),
        ("日志字符/行", f"{len(la)}", f"{len(lb)}"),
        ("圈留痕段", str(len([b for b in _dump_blocks(la)
                             if b[0] == "圈全量留痕"])),
         str(len([b for b in _dump_blocks(lb) if b[0] == "圈全量留痕"]))),
        ("收尾留痕段", str(len([b for b in _dump_blocks(la)
                               if b[0] == "收尾留痕"])),
         str(len([b for b in _dump_blocks(lb) if b[0] == "收尾留痕"]))),
        ("ing 就地行", str(la.count("🔥 │")), str(lb.count("🔥 │"))),
    ]
    w = max(len(r[0]) for r in rows)
    print(f"  {'指标'.ljust(w)} | {tag_a:>28s} | {tag_b:>28s}")
    for k, a, b in rows:
        print(f"  {k.ljust(w)} | {a:>28s} | {b:>28s}")
    print("  （↑ 头 6 行是同题同比的对照；口径差别的项见下表）")

    # ---- D：不可判定追溯 ----
    print("\n-- D 不可判定追溯 --")
    for tag, d in ((tag_a, fa), (tag_b, fb)):
        dec = (d or {}).get("decidability", {}) or {}
        print(f"  {tag}: decidability={dec.get('decidability')} "
              f"_divergent={dec.get('_divergent')} "
              f"_und_untraced={len(dec.get('_und_untraced') or [])} 条 "
              f"_und_traced={len(dec.get('_und_traced') or [])} 条")
        for x in (dec.get("_und_untraced") or []):
            print(f"        ✗ {str(x)[:56]}")

    # ---- B：两个覆盖率 ----
    print("\n-- B 不可判定覆盖率（pool 1）--")
    for tag, d in ((tag_a, fa), (tag_b, fb)):
        ch = (((d or {}).get("pools") or {}).get("1") or {}).get(
            "undecidable_channel") or {}
        if not ch:
            print(f"  {tag}: （无 undecidable_channel）")
            continue
        print(f"  {tag}: struct_cov={ch.get('last_struct_coverage')} "
              f"hit={ch.get('last_struct_hit')}/{len(ch.get('und_aspects') or [])}"
              f" | aligned_cov={ch.get('last_aligned_coverage')} "
              f"hit={ch.get('last_aligned_hit')}"
              f" | struct_amps={len(ch.get('structural_amps') or [])} "
              f"aligned_amps={len(ch.get('aligned_amps') or [])}")

    # ---- A：pool.meta 的 [P3] 行 ----
    print("\n-- A [P3] & 候选（各圈累计）行（按层）--")
    for tag, d in ((tag_a, fa), (tag_b, fb)):
        p3 = _p3_lines(d)
        if not p3:
            print(f"  {tag}: （无）")
            continue
        for entry, (n, s) in sorted(p3.items()):
            print(f"  {tag} entry={entry:4s} N={n:<4d} {s[:96]}")

    # ---- C：ing 正文里有没有「各个局部 / 上游」这类错标签的痕迹 ----
    print("\n-- C ing 正文词面（错标签会留下「各个局部/上游 view」的痕迹）--")
    for tag, log in ((tag_a, la), (tag_b, lb)):
        ing = [x for x in log.split("\n") if "🔥 │" in x]
        print(f"  {tag}: ing 行 {len(ing)}｜含「各个局部」"
              f"{sum('各个局部' in x for x in ing)} 行｜含「上游」"
              f"{sum('上游' in x for x in ing)} 行")

    # ---- E：收尾留痕里的累积字段 ----
    print("\n-- E 收尾留痕里的累积字段（项数）--")
    for tag, log in ((tag_a, la), (tag_b, lb)):
        tail = [b for b in _dump_blocks(log) if b[0] == "收尾留痕"]
        if not tail:
            print(f"  {tag}: （没有收尾留痕段）")
            continue
        for kind, entry, head, body in tail:
            om = re.search(r"增量模式：(\d+)/(\d+) 个字段", body)
            print(f"  {tag} entry={entry:4s} {head[:18]:18s} "
                  f"省略={om.group(1) + '/' + om.group(2) if om else '?'} "
                  f"round_log={_field_n(body, 'round_log')} "
                  f"roles_run={_field_n(body, 'roles_run')} "
                  f"carry_checks={_field_n(body, 'carry_checks')}")

    # ---- 产物 md 里的「对齐覆盖率」 ----
    print("\n-- 产物 md 的不可判定通道行 --")
    for tag in (tag_a, tag_b):
        m = re.search(r"\[artifacts\] 产物=(.+\.md)",
                      _log(HERE / f"verif_{tag}.log"))
        if not m:
            print(f"  {tag}: （日志里没有产物路径）")
            continue
        p = Path(m.group(1).strip())
        if not p.exists():
            print(f"  {tag}: （产物不存在 {p.name}）")
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        ls = [x for x in t.split("\n") if "研究层不可判定通道" in x]
        print(f"  {tag}: " + (ls[0][:200] if ls else "（正文没有这一行）"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ampcheck", default=None)
    a = ap.parse_args()
    if a.ampcheck:
        ok = ampcheck(HERE / a.ampcheck)
        print("\nA 不变量校验：", "通过" if ok else "未通过/无判别力")
        sys.exit(0 if ok else 1)
    report()

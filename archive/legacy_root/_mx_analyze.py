"""mx batch01 分析器（严格按 mx_design_batch01.md 预注册的判据出结论）。

设计要点：
  · **成本**：直接从 v60_<tag>_*.log 尾部读 llm_calls / tokens，不重算。
  · **质量**：用 `_fact_checklists.json` 的预注册清单判命中；
    ★ 必须在**同一道题内部**做等长截断 —— 不截断的话「命中多」就退化成
      「写得长」，这是 §7.16 已经踩过的坑。
  · **盲评**：随机编号，法官不知道这份是哪个单元。
  · **法官噪声**：每份打两次，从严取交集，并把自相矛盾条数报出来 ——
    如果噪声大于组间差，结论就得判「不可判定」，不许硬说。

判据（跑前写死，跑完不许改）：
  · 成本：某因子两水平 calls 中位数差 < 10% → 不构成主成本旋钮
  · 质量：组间差必须 > 组内极差才许断言
  · thinking：若档间命中率差 ≤1 条而 calls/token 差 >10% → 便宜那档更划算
  · 交互项：只在主效应达标时才解释；事后发现的一律留待下批预注册验证
"""
import json
import random
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 2026100204

CK = json.load(open(HERE / "_fact_checklists.json", encoding="utf-8"))
QKEY = {"eu": "欧盟AI法案", "ip": "IPv6", "tls": "TLS"}


# ---------------- 任务清单 → 单元定义 ----------------
def load_units(task_file="mx_batch01.txt"):
    units = []
    for ln in (HERE / task_file).read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "|" not in ln:
            continue
        head, body = ln.split("|", 1)
        mode, rounds, tag, question = body.strip().split(" ", 3)
        th = dict(s.split("=", 1) for s in head.split(","))
        th = {k.strip(): v.strip() for k, v in th.items()}
        m = re.match(r"mx_(\w+?)_(A|B)_(r\w+?)_(t\d)$", tag)
        if not m:
            print(f"  ⚠️ tag 解析不了，跳过：{tag}")
            continue
        qk, md, rc, tc = m.groups()
        units.append({
            "tag": tag, "mode": md, "rounds": rc, "thinking": tc,
            "qkey": qk, "raw_thinking": th.get("V60_THINKING", ""),
        })
    return units


def find_log(tag):
    cands = sorted(HERE.glob(f"v60_{tag}_*.log"))
    return cands[0] if cands else None


def log_fields(tag):
    lg = find_log(tag)
    if not lg:
        return None
    txt = lg.read_text(encoding="utf-8", errors="replace")
    out = {}
    for key, pat in (
            ("calls", r"llm_calls=(\d+)"),
            ("tokens", r"tokens=(\d+)"),
            ("secs", r"耗时 (\d+)s"),
            ("served", r"served_by=(\[[^\]]*\])"),
            ("missing", r"dispatch\.missing=(\[[^\]]*\])"),
            ("skipped", r"dispatch\.skipped=(\[[^\]]*\])"),
            ("views", r"views=(\[[^\]]*\])"),
            ("product", r"产物=(.+)$")):
        m = re.search(pat, txt, re.M)
        if not m:
            continue
        v = m.group(1).strip()
        out[key] = int(v) if key in ("calls", "tokens", "secs") else v
    return out or None


def product_text(tag):
    f = log_fields(tag) or {}
    p = f.get("product")
    if not p:
        return None
    p = Path(p)
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None


# ---------------- 判分（沿用 _fact_audit.py 的方法） ----------------
_SYS = "你是严格的事实核对员，只做「有没有给出」的判断，不做质量评价。"
_PROMPT = """你是事实核对员。给定「问题」和「必须项清单」，逐条判断：
文档里**是否真的给出了**这一项的内容——有实质说明就算有，只在标题里
掠过、或只有一句空话（例如"应当处理", "相关打开文件"）不算给出。

回答严格 JSON：
{"items":[{"i":1,"hit":0或1,"why":"≤15字，命中就抄原文片段"}]}

不许怜悯：宁可判 0。不许因为文档篇幅长就加分。

【问题】
{q}

【必须项清单】
{items}

【文档（已截断到等长）】
---
{doc}
---
"""

_PROMPT_NEG = """你是事实核对员。给定「问题」和「错误说法清单」，逐条判断：
文档里**是否出现了这个错误说法**（哪怕只是顺带提到、或作为"有人认为"
转述，只要白纸黑字出现了这个错误说法就算出现）。

回答严格 JSON：
{"items":[{"i":1,"hit":0或1,"why":"≤15字，出现就抄原文片段"}]}

不许怜悯：宁可判 0。这些是公认错误，出现即扣分。

【问题】
{q}

【错误说法清单】
{items}

【文档（已截断到等长）】
---
{doc}
---
"""


def _audit(llm, question, items, docs, prompt, reps, seed):
    """通用判分：对每份 doc 判 items 是否命中。返回 {tag: 命中数}, {tag: 矛盾数}。"""
    rng = random.Random(seed)
    keys = list(docs)
    rng.shuffle(keys)
    hitcount, disagree = {}, {}
    for k in keys:
        p = (prompt.replace("{q}", question)
                   .replace("{items}",
                            "\n".join(f"{i+1}. {t}"
                                      for i, t in enumerate(items)))
                   .replace("{doc}", docs[k]))
        votes = []
        for _ in range(reps):
            try:
                raw = llm.call(_SYS, p, temperature=0.0,
                               max_tokens=1500, json_mode=True)
                data = llm.parse_json(raw) or {}
            except Exception as e:
                print(f"    ✗ {k} 判分调用失败：{type(e).__name__}: {e}")
                continue
            got = {int(x.get("i")): x for x in (data.get("items") or [])}
            votes.append({i: bool(got.get(i, {}).get("hit"))
                          for i in range(1, len(items) + 1)})
        if not votes:
            print(f"    ⚠️ {k} 判分 {reps} 次全失败，该份未计入（判据缺口）")
            continue
        strict = {i: all(v[i] for v in votes)
                  for i in range(1, len(items) + 1)}
        hitcount[k] = sum(1 for v in strict.values() if v)
        disagree[k] = sum(1 for i in strict
                          if len({v[i] for v in votes}) > 1)
    return hitcount, disagree


def judge(mod, question, pos_items, neg_items, docs, reps=2, seed=SEED):
    """docs: {tag: 文本} —— 已在同一道题内部等长截断。

    返回 (pos_hit, neg_hit, disagree, pos_tot, neg_tot)。
    pos_hit = 正分命中数；neg_hit = 负分命中数（答了幻觉）；总分 = pos - neg。
    """
    llm = mod.LLM(mod.load_config(str(HERE / "dgtf_config.yaml")))
    pos_hit, pos_dis = _audit(llm, question, pos_items, docs,
                              _PROMPT, reps, seed)
    neg_hit, neg_dis = _audit(llm, question, neg_items, docs,
                              _PROMPT_NEG, reps, seed + 1)
    disagree = {k: pos_dis.get(k, 0) + neg_dis.get(k, 0)
                for k in set(pos_dis) | set(neg_dis)}
    return pos_hit, neg_hit, disagree, len(pos_items), len(neg_items)


# ---------------- 主效应 ----------------
def main_effect(rows, factor, metric):
    """rows: list of dict(tag, mode, rounds, thinking, calls, tokens, hits)"""
    lv = sorted({r[factor] for r in rows})
    if len(lv) != 2:
        return None
    a = [r[metric] for r in rows if r[factor] == lv[0] and r[metric] is not None]
    b = [r[metric] for r in rows if r[factor] == lv[1] and r[metric] is not None]
    if not a or not b:
        return None
    ma, mb = statistics.median(a), statistics.median(b)
    return lv, ma, mb, (mb - ma) / ma * 100 if ma else float('nan'), \
        max(a) - min(a), max(b) - min(b)


def main():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "dgtf", HERE / "元DGTF-V1.21.61.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf"] = mod
    spec.loader.exec_module(mod)

    units = load_units()
    print(f"=== mx batch01：{len(units)} 个单元 ===")

    rows = []
    for u in units:
        f = log_fields(u["tag"])
        if not f:
            print(f"  缺日志：{u['tag']}")
            continue
        u.update(f)
        rows.append(u)

    done = [r for r in rows if "calls" in r]
    print(f"已跑完 {len(done)}/{len(units)}\n")

    print("=== 成本明细 ===")
    print(f"{'tag':28s}{'calls':>7s}{'tokens':>10s}{'分钟':>7s}  served_by")
    for r in sorted(done, key=lambda x: x["tag"]):
        print(f"{r['tag']:28s}{r['calls']:>7d}{r['tokens']:>10d}"
              f"{r['secs']/60:>7.1f}  {r.get('served','?')}")

    # ---------- 质量：组内等长截断 + 盲评 ----------
    print("\n=== 质量（事实清单；同题内等长截断 + 盲评 + 两次从严）===")
    by_q = {}
    for r in done:
        by_q.setdefault(r["qkey"], []).append(r)

    report = {"judged": 0, "no_checklist": 0, "empty": 0, "few_docs": 0}
    for qk, rs in sorted(by_q.items()):
        key = QKEY.get(qk)
        if not key or key not in CK:
            print(f"  {qk}：没有预注册清单，跳过")
            report["no_checklist"] += 1
            continue
        items = CK[key].get("items") or CK[key].get("必须项") or []
        neg_items = CK[key].get("负分项") or []
        if not items:
            print(f"  {qk}：清单为空，跳过")
            report["empty"] += 1
            continue
        docs = {}
        for r in rs:
            t = product_text(r["tag"])
            if t:
                docs[r["tag"]] = t
        if len(docs) < 2:
            print(f"  {qk}：产物不足 {len(docs)} 份，跳过")
            report["few_docs"] += 1
            continue
        report["judged"] += 1
        n = min(len(d) for d in docs.values())
        docs = {k: v[:n] for k, v in docs.items()}
        question = {"eu": CK.get("欧盟AI法案", {}).get("题", ""),
                    "ip": CK.get("IPv6", {}).get("题", ""),
                    "tls": CK.get("TLS", {}).get("题", "")}.get(qk, "")
        pos_hit, neg_hit, dis, pos_tot, neg_tot = judge(
            mod, question or "见清单", items, neg_items, docs)
        print(f"  【{key}】正分 {pos_tot} 条 + 负分 {neg_tot} 条，"
              f"等长截断到 {n} 字，产物 {len(docs)} 份")
        for tag in sorted(pos_hit):
            r = next(x for x in rs if x["tag"] == tag)
            p = pos_hit.get(tag, 0)
            ng = neg_hit.get(tag, 0)
            r["hits"] = p - ng          # 净分 = 正分命中 - 负分命中
            r["items_tot"] = pos_tot
            r["neg_hits"] = ng
            print(f"    {tag:28s} 正 {p}/{pos_tot}  负 {ng}/{neg_tot}  "
                  f"净 {p - ng}   法官矛盾 {dis.get(tag, '-')} 条")

    # ---------- 主效应 ----------
    print("\n=== 主效应（按预注册判据）===")
    for metric, label in (("calls", "成本 llm_calls"),
                          ("tokens", "成本 tokens"),
                          ("hits", "质量 命中条数")):
        print(f"\n-- {label} --")
        for fac, name in (("mode", "mode"), ("rounds", "rounds"),
                          ("thinking", "thinking")):
            got = main_effect([r for r in done if metric in r], fac, metric)
            if not got:
                continue
            lv, ma, mb, pct, ra, rb = got
            print(f"  {name:9s} {lv[0]}=中位{ma:>8.0f} "
                  f"{lv[1]}=中位{mb:>8.0f}  差 {pct:+.1f}%  "
                  f"组内极差 {ra}/{rb}")
            if metric == "calls":
                verdict = ("不构成主成本旋钮（差 <10%）"
                           if abs(pct) < 10 else "**是主成本旋钮**")
                print(f"            判据：{verdict}")
            else:
                if abs(mb - ma) <= max(ra, rb):
                    print("            判据：组间差 ≤ 组内极差 → "
                          "**不可判定**，不许写成结论")
                else:
                    print("            判据：组间差 > 组内极差 → 可断言")

    # ---------- 判据执行报告（堵静默失败：跑完必须能一眼看出缺口）----------
    print("\n=== 判据执行报告 ===")
    _skipped = report["no_checklist"] + report["empty"] + report["few_docs"]
    print(f"  已判分 {report['judged']} 题 / 跳过 {_skipped} 题"
          f"（无清单 {report['no_checklist']} · 清单空 {report['empty']} · "
          f"产物不足 {report['few_docs']}）")
    judged_tags = [r["tag"] for r in done if "hits" in r]
    missing = [r["tag"] for r in done if r["tag"] not in judged_tags]
    if missing:
        print(f"  ⚠️ 以下 {len(missing)} 个单元没有质量得分（判据缺口）：{missing}")
    else:
        print(f"  ✓ 全部 {len(done)} 个单元都有质量得分，无判据缺口")


if __name__ == "__main__":
    main()

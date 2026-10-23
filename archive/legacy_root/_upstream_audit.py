# -*- coding: utf-8 -*-
"""中上游题判分器：读 _upstream_checklists.json，判「有没有给出」四类必答项。

与 _fact_audit.py 的区别：事实清单判「答没答对事实」，这里判「有没有识别出
约束 / 摊开权衡 / 归对边界 / 落到动作」——中上游题没有唯一答案，但可以预注册
「好答案必须覆盖的要素」。

判分方法沿用已验证的：等长截断 + 盲评 + 两次从严取交集 + 报法官矛盾数。
净分 = 约束命中 + 权衡命中 + 可判命中 + 拍板命中 + 落地命中。
"""
import json
import random
import statistics
import sys
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
CK = json.load(open(HERE / "_upstream_checklists.json", encoding="utf-8"))
SEED = 2026100210

_SYS = "你是严格的结构核对员，只做「有没有给出」的判断，不做质量评价。"

# 约束/权衡/可判/拍板四类，都是「文档里有没有真的给出这一项」
_PROMPT_GIVE = """你是结构核对员。给定「问题」和「必答项清单」，逐条判断：
文档里**是否真的给出了**这一项的内容——有实质展开就算给出，只在标题里
掠过、或只有一句空话（例如"应当综合考虑"）不算给出。

回答严格 JSON：
{"items":[{"i":1,"hit":0或1,"why":"≤15字，命中就抄原文片段"}]}

不许怜悯：宁可判 0。不许因为文档篇幅长就加分。

【问题】
{q}

【必答项清单】
{items}

【文档（已截断到等长）】
---
{doc}
---
"""

# 落地判据：方案里有没有「具体动作 + 明确第一步」，不是空话
_PROMPT_LAND = """你是结构核对员。判断文档给出的方案里：
是否包含**可执行的具体动作**（有动词 + 具体对象 + 顺序/第一步），
而不是停在「应当综合考虑 / 建议权衡利弊」这种空话。

判据：{criterion}

回答严格 JSON：
{"hit":0或1,"why":"≤20字，命中就抄原文里最能体现具体动作的那句"}

不许怜悯：宁可判 0。

【问题】
{q}

【文档（已截断到等长）】
---
{doc}
---
"""


def load_module():
    spec = importlib.util.spec_from_file_location(
        "dgtf60", HERE / "元DGTF-V1.21.61.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf60"] = mod
    spec.loader.exec_module(mod)
    return mod


def _audit(llm, question, items, docs, prompt, reps, seed):
    """对每份 doc 判 items 是否命中。返回 {tag: 命中数}, {tag: 矛盾数}。"""
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


def _audit_land(llm, question, criterion, docs, reps, seed):
    """落地判据：每份判 hit 0/1。返回 {tag: hit}, {tag: 矛盾数}。"""
    rng = random.Random(seed)
    keys = list(docs)
    rng.shuffle(keys)
    hit, disagree = {}, {}
    for k in keys:
        p = (_PROMPT_LAND.replace("{q}", question)
                         .replace("{criterion}", criterion)
                         .replace("{doc}", docs[k]))
        votes = []
        for _ in range(reps):
            try:
                raw = llm.call(_SYS, p, temperature=0.0,
                               max_tokens=800, json_mode=True)
                data = llm.parse_json(raw) or {}
            except Exception as e:
                print(f"    ✗ {k} 落地判分失败：{type(e).__name__}: {e}")
                continue
            votes.append(bool(data.get("hit")))
        if not votes:
            continue
        hit[k] = 1 if all(votes) else 0
        disagree[k] = 1 if len({v for v in votes}) > 1 else 0
    return hit, disagree


def audit_question(mod, qkey, docs, reps=2, seed=SEED):
    """判一道中上游题。docs: {tag: 文本}（已在等长截断）。"""
    cl = CK[qkey]
    question = cl["题"]
    llm = mod.LLM(mod.load_config(str(HERE / "dgtf_config.yaml")))

    # 四类「必答项」合并判分（约束+权衡+可判+拍板）
    give_items = (cl.get("约束项", []) + cl.get("权衡项", [])
                  + cl.get("可判项", []) + cl.get("拍板项", []))
    give_hit, give_dis = _audit(llm, question, give_items, docs,
                                _PROMPT_GIVE, reps, seed)

    # 落地判据单独判（0/1）
    land_hit, land_dis = _audit_land(llm, question, cl.get("落地判据", ""),
                                     docs, reps, seed + 1)

    # 汇总
    result = {}
    for tag in docs:
        g = give_hit.get(tag, 0)
        l = land_hit.get(tag, 0)
        result[tag] = {
            "give": g, "give_tot": len(give_items),
            "land": l,
            "net": g + l,
            "disagree": give_dis.get(tag, 0) + land_dis.get(tag, 0),
        }
    return result, len(give_items)


def main():
    """用法：python _upstream_audit.py <题key> <产物1> [产物2 ...]"""
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    qkey = sys.argv[1]
    if qkey not in CK:
        print(f"评尺里没有「{qkey}」，现有：{list(CK)}")
        return 2
    mod = load_module()
    docs = {}
    for p in sys.argv[2:]:
        f = Path(p)
        if f.exists():
            docs[f.name] = f.read_text(encoding="utf-8", errors="replace")
    if len(docs) < 1:
        print("没有可读的产物")
        return 2
    n = min(len(d) for d in docs.values())
    docs = {k: v[:n] for k, v in docs.items()}
    result, tot = audit_question(mod, qkey, docs)
    print(f"=== 中上游题评尺：{qkey}（必答项 {tot} 条 + 落地 1 条）===")
    for tag in sorted(result):
        r = result[tag]
        print(f"  {tag:40s} 必答 {r['give']}/{r['give_tot']}  "
              f"落地 {r['land']}/1  净 {r['net']}/{tot+1}  "
              f"法官矛盾 {r['disagree']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

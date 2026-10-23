# -*- coding: utf-8 -*-
"""事实核对：砍层到底有没有把「答案」砍掉。

起因（2026-10-02）：项目头条那个「已答子问题 X/Y」经 `_ans_variance.py`
验出是个**饱和+带噪**的指标（89 份里 84 份 X==Y；同题同配置下 Y 从 1 漂
到 5）。拿它判质量判不出东西，但「砍层伤不伤答案」这个问题又必须回答，
否则不知道能不能为了省钱默认走 light。

于是换一把尺：**预注册的事实核对清单**（`_fact_checklists.json`，写于
打分之前），一条一条问「这份产物里到底有没有给出这一项」。

长度控制：同一题的两份产物先各自截断到**较短那一份的字符数**再交给法官。
不这么做的话，四层产物天生更长、提到的点更多，命中差就变成了字数差。

用法：
  python _fact_audit.py            # 跑全表
  python _fact_audit.py 欧盟AI法案  # 只跑一题
"""
import importlib.util
import json
import os
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"


def load_mod():
    spec = importlib.util.spec_from_file_location(
        "dgtf", str(HERE / "元DGTF-V1.21.61.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf"] = m
    spec.loader.exec_module(m)
    return m


# 题 → （砍层 tag, 四层 tag）。产物路径从对应日志末尾的 `产物=<path>` 行取，
# 不靠文件名猜（欧盟那题全库有 15 份产物，按前缀取必错）。
PAIRS = {
    "欧盟AI法案": ("f1_2", "f1_4"),
    "IPv6":      ("f2_2", "f2_4"),
    "TLS":       ("f3_2", "f3_4"),
}

# 开放/哲学题没有外部正确答案，改用**产出形态**清单（`_rubric_open.json`）。
# 这才是「四层真正有用」最可能成立的一格；取证题那三对只证明了取证题打平，
# 不能外推到这一格，必须自己跑出来。
OPEN_PAIRS = {
    "自由意志":     ("o1_2", "o1_4"),
    "整体大于部分": ("o2_2", "o2_4"),
    "人有灵魂吗":   ("o3_2", "o3_4"),
}


def product_of(tag: str):
    """从 v60_<tag>_r5_A.log 尾 NN-NN 取 `产物=<path>`，不猜文件名。"""
    lg = HERE / f"v60_{tag}_r5_A.log"
    if not lg.exists():
        return None
    for line in lg.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("产物="):
            p = Path(line[3:].strip())
            return p if p.exists() else None
    return None

_SYS = ("你是严格的事实核对员，只做「有没有给出」的判断，不做质量评价。")

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


def audit(mod, q, items, docs, reps=1):
    """reps=2 用来量**法官自己的噪声** —— 同一份文档打两次分不一致的话，
    两组的差就可能是法官在飘，不是层在起作用。"""
    llm = mod.LLM(mod.load_config(str(HERE / "dgtf_config.yaml")))
    n = min(len(d) for d in docs.values())
    res = {}
    # ★ 盲评：两份随机编号，法官不知道哪份是砍层
    keys = list(docs)
    random.shuffle(keys)
    coded = {keys[i]: f"候选{chr(65+i)}" for i in range(len(keys))}
    for k in keys:
        doc = docs[k][:n]
        # ★ 用 replace 不用 .format —— 模板里有 JSON 示例的 `{}`，一 format 就炸
        p = (_PROMPT.replace("{q}", q)
                    .replace("{items}",
                             "\n".join(f"{i+1}. {t}"
                                       for i, t in enumerate(items)))
                    .replace("{doc}", doc))
        votes = []
        for _rep in range(reps):
            raw = llm.call(_SYS, p, temperature=0.0, max_tokens=1200,
                           json_mode=True)
            try:
                data = llm.parse_json(raw) or {}
            except Exception as e:
                print(f"  ✗ [{coded[k]}] 解析失败 {e}")
                continue
            got = {int(x.get("i")): x for x in (data.get("items") or [])}
            votes.append({i: bool(got.get(i, {}).get("hit"))
                          for i in range(1, len(items) + 1)})
        if not votes:
            continue
        # 从严：两次都判中才算中。顺便把法官自己的矛盾条数打出来
        res[k] = {i: all(v[i] for v in votes)
                  for i in range(1, len(items) + 1)}
        if len(votes) > 1:
            _d = sum(1 for i in res[k] if len({v[i] for v in votes}) > 1)
            print(f"    （{coded[k]}：法官两次自相矛盾 {_d}/{len(items)} 条）")
    return res, coded, n


def run_pair(mod, key, title, items, tags, reps, neg_from=None):
    """跑一对（砍层 vs 四层）。neg_from 之后的条目是**扣分项**。"""
    p_light, p_full = product_of(tags[0]), product_of(tags[1])
    if not p_light or not p_full:
        print(f"\n### {key}：产物还没齐"
              f"（砍层={p_light is not None}，四层={p_full is not None}）")
        return None
    docs = {"light": p_light.read_text(encoding="utf-8"),
            "full": p_full.read_text(encoding="utf-8")}
    print(f"\n### {key}　{len(items)} 条"
          f"（{'其中第 ' + str(neg_from) + ' 条起是扣分项' if neg_from else '全部为正向必答'}）")
    print(f"    light={p_light.name[:44]}")
    print(f"    full ={p_full.name[:44]}")
    res, coded, n = audit(mod, title, items, docs, reps=reps)
    print(f"    等长截断到 {n} 字（较短那一份的长度）")
    out = {}
    for k, coded_name in coded.items():
        v = res.get(k, {})
        if neg_from:
            pos = sum(1 for i, ok in v.items() if ok and i < neg_from)
            neg = sum(1 for i, ok in v.items() if ok and i >= neg_from)
            out[k] = pos - neg
            miss = [str(i) for i in sorted(v) if not v[i] and i < neg_from]
            trips = [str(i) for i in sorted(v) if v[i] and i >= neg_from]
            print(f"    {coded_name}({k}){'':<4}正{pos}/负{neg} → 计 {out[k]:<4}"
                  f"漏 {','.join(miss) or '—'}"
                  f"{'　⚠扣中：' + ','.join(trips) if trips else ''}")
        else:
            out[k] = sum(1 for x in v.values() if x)
            miss = [str(i) for i in sorted(v) if not v[i]]
            print(f"    {coded_name}({k}){'':<4}{out[k]}/{len(items):<8}"
                  f"漏 {','.join(miss) or '—'}")
    lv = [i for i, ok in res.get("light", {}).items() if ok]
    fv = [i for i, ok in res.get("full", {}).items() if ok]
    if lv or fv:
        print(f"    → 只有砍层答到：{sorted(set(lv)-set(fv)) or '无'}")
        print(f"    → 只有四层答到：{sorted(set(fv)-set(lv)) or '无'}")
    return out


def main():
    mod = load_mod()
    ck = json.load(open(HERE / "_fact_checklists.json", encoding="utf-8"))
    rb = json.load(open(HERE / "_rubric_open.json", encoding="utf-8"))
    want = [a for a in sys.argv[1:] if not a.startswith("--")]
    _REPS = next((int(a.split("=")[1]) for a in sys.argv
                  if a.startswith("--reps=")), 1)
    want = want or list(PAIRS) + list(OPEN_PAIRS)

    total = {"light": 0, "full": 0}
    # ---- 取证题：事实清单 ----
    for key, tags in PAIRS.items():
        if key not in want:
            continue
        spec = ck[key]
        r = run_pair(mod, key, spec["题"], spec["必须项"], tags, _REPS)
        if r:
            for k in total:
                total[k] += r[k]
    # ---- 开放题：产出形态清单 ----
    for key, tags in OPEN_PAIRS.items():
        if key not in want:
            continue
        spec = rb[key]
        items = (rb["通用于开放题"]["正向必须项"] + spec["专项必须项"]
                 + rb["通用于开放题"]["反向扣分项"])
        r = run_pair(mod, key, spec["题"], items, tags,
                     _REPS, neg_from=len(rb["通用于开放题"]["正向必须项"])
                     + len(spec["专项必须项"]) + 1)
        if r:
            for k in total:
                total[k] += r[k]
    print(f"\n=== 合计得分（越高越好）：砍层 {total['light']} "
          f"vs 四层 {total['full']} ===")


if __name__ == "__main__":
    main()

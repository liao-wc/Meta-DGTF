# -*- coding: utf-8 -*-
"""从元DGTF packed 构建 LLM SFT 数据集：问题 → 四层 route/rounds 调度 JSON。

目标短、可校验、可直接接入 app 的调度规划；不是生成整篇长报告。
"""
from __future__ import annotations
import glob, json, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "llm_sft"
LAYERS = ["0", "1", "both", "all"]

SYSTEM = ("你是元DGTF的调度规划器。阅读用户问题，输出严格 JSON："
          '{"route": ["0","1","both","all"] 的子集, '
          '"rounds": {"0":int,"1":int,"both":int,"all":int}, '
          '"why": "不超过20字的理由"}。'
          "route 只放需要的层；rounds 给每层圈数（1-8）；不要输出 JSON 以外内容。")

def norm_q(q):
    return re.sub(r"\s+", " ", str(q or "")).strip()[:300]

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in glob.glob(str(ROOT / "outputs" / "*.packed.json")):
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        q = norm_q(d.get("question"))
        route = [x for x in (d.get("route") or []) if str(x) in LAYERS]
        rounds = d.get("rounds") or {}
        if not q or not route:
            continue
        rd = {}
        for x in route:
            try:
                rd[str(x)] = max(1, min(8, int(rounds.get(x, 1))))
            except Exception:
                rd[str(x)] = 1
        target = {"route": route, "rounds": rd}
        if d.get("decidability") in ("on", "off", "auto"):
            target["decidability"] = d["decidability"]
        target["why"] = "按问题结构选择层与圈数"
        md = Path(p).with_suffix("").with_suffix(".md")
        rows.append({"question": q, "target": target,
                     "run": Path(p).stem, "packed": Path(p).name,
                     "has_md": md.exists(), "mock": bool(d.get("mock"))})
    items = sorted(rows, key=lambda x: x["run"])
    # 按问题分组切分：同一问题的不同跑次只进同一侧，避免同题泄漏
    qs = sorted({x["question"] for x in items})
    cut = max(1, int(len(qs) * 0.8))
    train_q, val_q = set(qs[:cut]), set(qs[cut:])
    train = [x for x in items if x["question"] in train_q]
    val = [x for x in items if x["question"] in val_q]
    def write(rows, name):
        with (OUT / name).open("w", encoding="utf-8") as f:
            for x in rows:
                rec = {"messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": x["question"]},
                    {"role": "assistant",
                     "content": json.dumps(x["target"], ensure_ascii=False,
                                           separators=(",", ":"))}
                ], "meta": {"run": x["run"], "mock": x["mock"]}}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    write(train, "train.jsonl")
    write(val, "val.jsonl")
    manifest = {"total": len(items), "train": len(train), "val": len(val),
                "questions": len(qs), "train_questions": len(train_q),
                "val_questions": len(val_q),
                "route_dist": {",".join(x["target"]["route"]): 0 for x in items},
                "note": "问题→route/rounds JSON；按 run 分组切分"}
    from collections import Counter
    c = Counter(",".join(x["target"]["route"]) for x in items)
    manifest["route_dist"] = dict(c)
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=1)[:4000])
    if train:
        print("SAMPLE", json.dumps(train[0]["target"], ensure_ascii=False))

if __name__ == "__main__":
    main()

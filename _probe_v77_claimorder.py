# -*- coding: utf-8 -*-
"""
M1 复诊探针：把 claims 的取值顺序从 (1,0,both,all) 改成 (0,1,both,all)，
用**已跑完的 packed** 重放收尾对照（1 次 LLM 调用），看对照是否终于有反应。

为什么怀疑是顺序问题（而不是层次问题）：
  v76 的 B 模式 packed 里，层 0 的 candidates 明明是领域事实层
  （"产线报价单不含停产改造期的订单流失" / "订单不稳定时高固定成本会放大
  淡季现金流缺口"），与锚点 a2 / a5 同层；但收尾对照取的 12 条 claims
  **全是层 1 的**（"现金维持期是本轮唯一已显形的约束"这种操作层）。
  查 `_anchor_claims`：`for k in ("1", "0", "both", "all")` —— 层 1 排最前，
  12 条配额被它占满，层 0 的领域论断一条都挤不进去。

  即：**不是"引擎不产领域论断"，是我把取值的优先级排反了。**

判据：
  · 新口径 `anchor_used` > 0（至少有一条锚点被引用）
  · 且 supported + conflicted > 0（不只是"沾边"，而是真的判出了对应关系）
  · 负对照：旧口径在同一份 packed 上仍应为 0/0/N（否则是这次调用碰巧）
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.76.py"
PACK = HERE / "v76arm_B_boundary.full.json"
ANCH = HERE / "anchors" / "up_biz_anchors.json"

ORDER_OLD = ("1", "0", "both", "all")
ORDER_NEW = ("0", "1", "both", "all")
CAP = 12


def load_dotenv(p: Path) -> None:
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def claims_of(views: dict, order) -> list:
    out = []
    for k in order:
        v = views.get(k)
        if not v:
            continue
        for c in (v.get("candidates") or []):
            if isinstance(c, dict):
                t = str(c.get("desc") or "").strip()
                if t:
                    out.append(t[:300])
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:CAP]


def main() -> int:
    load_dotenv(HERE / ".env")
    spec = importlib.util.spec_from_file_location("d76m", str(SRC))
    m = importlib.util.module_from_spec(spec)
    sys.modules["d76m"] = m
    spec.loader.exec_module(m)

    pack = json.loads(PACK.read_text(encoding="utf-8"))
    views = pack.get("views") or {}
    ad = json.loads(ANCH.read_text(encoding="utf-8"))
    anchors = (ad.get("anchors") or [])[:6]

    cfg = m.load_config(str(HERE / "dgtf_config.yaml"))
    cfg["external_anchor"] = {"enabled": True, "path": str(ANCH),
                              "max_items": 6, "per_round": 2,
                              "as_evidence": False, "triage": False,
                              "retriever": "snapshot", "crosscheck": True}

    def build():
        o = object.__new__(m.MetaDGTF)
        o.config = cfg
        o.llm = m.LLM(cfg)
        o._anchors = anchors
        o._anchor_err = ""
        o._anchor_source = {"file": ANCH.name, "retriever": "snapshot",
                            "retrieved_at": ad.get("retrieved_at", "")}
        o._anchor_calls = 0
        o._call_budget = 0
        o.pools = {"0": m.Pool(), "1": m.Pool(),
                   "both": m.Pool(), "all": m.Pool()}
        o.vp = lambda *a, **k: None
        return o

    print("=== 锚点 6 条 ===")
    for a in anchors:
        print(f"  {a['id']}: {str(a['claim'])[:70]}")

    results = {}
    for k, v in views.items():
        class _V:
            def __init__(self, d):
                self.candidates = d.get("candidates") or []
                self.decidable_product = d.get("decidable_product") or {}
        results[k] = _V(v)

    out = {}
    for tag, order in (("旧口径 (1,0,both,all)", ORDER_OLD),
                       ("新口径 (0,1,both,all)", ORDER_NEW)):
        cs = claims_of(views, order)
        o = build()
        o._anchor_claims = (lambda cs_: (lambda results_: list(cs_)))(cs)
        r = o._anchor_crosscheck(results)
        sm = r.get("summary") or {}
        out[tag] = (len(cs), sm)
        print(f"\n=== {tag} ===")
        print(f"  claims={len(cs)}  "
              f"印证={sm.get('supported')} 冲突={sm.get('conflicted')} "
              f"无对应={sm.get('unmatched')} 用到锚点={sm.get('anchor_used')}")
        for it in (r.get("items") or [])[:14]:
            if it.get("verdict") != "无对应" or it.get("anchor_ids"):
                print(f"    ★ {it['verdict']}｜{str(it['claim'])[:60]}")
                print(f"        锚点={it.get('anchor_ids')} | "
                      f"{str(it.get('note'))[:70]}")
        if r.get("error"):
            print("  error:", r["error"])

    print("\n=== 判定 ===")
    ns, ss = out["新口径 (0,1,both,all)"]
    os_, so = out["旧口径 (1,0,both,all)"]
    hit = (ss.get("anchor_used") or 0) > 0
    rel = (ss.get("supported", 0) + ss.get("conflicted", 0)) > 0
    print(f"  旧：用到锚点={so.get('anchor_used')}  新：用到锚点={ss.get('anchor_used')}")
    if not hit:
        print("  ✗ 换顺序后仍然一条锚点都没用上 —— 顺序不是根因，"
              "要往「锚点与引擎产出的东西本就不同层」想。")
        return 1
    print(f"  ✓ 顺序是根因：anchor_used {so.get('anchor_used')} → "
          f"{ss.get('anchor_used')}，"
          f"印证+冲突 {so.get('supported',0)+so.get('conflicted',0)} → "
          f"{ss.get('supported',0)+ss.get('conflicted',0)}")
    if not rel:
        print("  ⚠ 但只有「沾边」（ing 类引用），没有真的判出印证/冲突 —— "
              "对照仍是弱信号，别当成「锚点被验证了」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

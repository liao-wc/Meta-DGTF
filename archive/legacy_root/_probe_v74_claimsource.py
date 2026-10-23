# -*- coding: utf-8 -*-
"""[探索性 · 不计入预注册对照] 层次错配是「引擎的错」还是「抽取器的错」？

背景：v1.21.73/74 的预注册对照里，ON 臂 5 条 claims 被判 5/5「无对应」。
当时有两种解释：
  (A) 引擎在 route=[0,1] 上产出的本来就不是关于世界的断言 → 锚点天然够不着；
  (B) `_anchor_claims` 只看了两处（各层 decidable_product.answer + 研究池已答
      子问题），**恰好都是认识论层的东西**，而引擎真正的领域论断在别处。

两者对策完全不同：(A) 要改题型/改层；(B) 只是换个取值处。

本脚本检验 (B)：把 claims 换成 `views[*].candidates`（基于**已跑完的** ON packed，
不重跑流程），喂同一个 `_anchor_crosscheck`，看还判不判「无对应」。

★ 为什么标「探索性」：这改了 `_anchor_prereg.json` 里写死的 M1 口径。
  事后改口径挑好看的数字是本项目明确禁止的动作，所以本脚本的结果
  **不并入主结论**，只用于决定下一轮要不要正式扩口径。

跑法：python _probe_v74_claimsource.py [ON侧车路径]
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.74.py"
ANCHORS = HERE / "anchors" / "up_biz_anchors.json"
PACKED = Path(sys.argv[1]) if len(sys.argv) > 1 \
    else HERE / "v73arm_ON.full.json"


def load_dotenv(p: Path):
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    load_dotenv(HERE / ".env")
    spec = importlib.util.spec_from_file_location("d74cs", str(SRC))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["d74cs"] = mod
    spec.loader.exec_module(mod)

    packed = json.loads(PACKED.read_text(encoding="utf-8"))
    views = packed.get("views") or {}

    # 三种取 claims 的口径，同一份 packed、同一份锚点、同一把对照尺
    def claims_prereg(_r):
        """预注册口径：成品答案 + 研究池已答子问题。"""
        out = []
        for k in ("1", "both", "all", "0"):
            v = views.get(k)
            if not v:
                continue
            ans = str(((v.get("decidable_product") or {}).get("answer")
                       or "")).strip()
            if ans:
                out.append(ans[:300])
        for sq in ((packed.get("pools") or {}).get("1")
                   or {}).get("sub_questions") or []:
            if isinstance(sq, dict) and sq.get("status") == "answered":
                q = str(sq.get("question") or "").strip()
                if q:
                    out.append(q[:300])
        seen, uniq = set(), []
        for c in out:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq[:12]

    def _cand_texts():
        out = []
        for k in ("0", "1"):
            for c in ((views.get(k) or {}).get("candidates") or []):
                if isinstance(c, dict):
                    t = str(c.get("desc") or c.get("text") or "").strip()
                else:
                    t = str(c).strip()
                if t:
                    out.append(t)
        seen, uniq = set(), []
        for c in out:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        return uniq

    cands = _cand_texts()
    print(f"packed：{PACKED.name}")
    print(f"candidates 去重后 {len(cands)} 条，本次取前 12 条当 claims\n")

    def claims_cands(_r):
        return [c[:300] for c in cands[:12]]

    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
    cfg["external_anchor"] = {"enabled": True, "path": str(ANCHORS),
                              "max_items": 12, "crosscheck": True}
    m = mod.MetaDGTF(cfg)
    m.verbose = False
    m._load_anchors()
    print(f"载入锚点 {len(m._anchors)} 条\n")

    results = []
    for tag, fn in (("预注册口径（成品答案+已答子问题）", claims_prereg),
                    ("探索口径（views.candidates 前 12 条）", claims_cands)):
        m._anchor_claims = fn          # 只换"取哪些条目"，对照器一字不改
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rep = m._anchor_crosscheck({})
        sm = rep.get("summary") or {}
        results.append((tag, rep))
        print(f"── {tag}")
        print(f"   claims={sm.get('claims')} 印证={sm.get('supported')} "
              f"冲突={sm.get('conflicted')} 无对应={sm.get('unmatched')} "
              f"用到锚点={sm.get('anchor_used')}/{len(m._anchors)}")
        if rep.get("error"):
            print(f"   error: {rep['error']}")
        for it in (rep.get("items") or []):
            mk = {"印证": "✅", "冲突": "❌", "无对应": "➖"}.get(
                it.get("verdict"), "?")
            print(f"   {mk} {it.get('anchor_ids')} | "
                  f"{it.get('claim', '')[:56]}")
            print(f"        {it.get('note', '')[:96]}")
        print()

    # 判别：探索口径要在"沾得上边"这件事上明显不同，才说明是抽取器的问题
    a_sm = results[0][1].get("summary") or {}
    b_sm = results[1][1].get("summary") or {}
    a_hit = int(a_sm.get("supported") or 0) + int(a_sm.get("conflicted") or 0)
    b_hit = int(b_sm.get("supported") or 0) + int(b_sm.get("conflicted") or 0)
    print("=" * 60)
    print(f"沾得上边的条数：预注册口径 {a_hit} / {a_sm.get('claims')} "
          f"→ 探索口径 {b_hit} / {b_sm.get('claims')}")
    if b_hit >= 1 and int(b_sm.get("anchor_used") or 0) >= 1:
        print("判定：层次错配主要是**抽取器取值位置**的问题（解释 B）。")
        print("      引擎在 route=[0,1] 上确实产出了领域事实层的论断，")
        print("      只是 `_anchor_claims` 没去 candidates 取。")
        print("      → 下一轮应把 candidates 正式纳入 M1 口径并重新预注册，")
        print("        本脚本结果不并入本轮主结论。")
        ok = True
    else:
        print("判定：换口径也没用 → 更可能是解释 A（输出本身与锚点不同层）。")
        ok = True          # 不确定结论也是结论，脚本不算失败

    out = HERE / "_probe_claimsource.json"
    out.write_text(json.dumps(
        {"pre": results[0][1], "explore": results[1][1]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写入 {out.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

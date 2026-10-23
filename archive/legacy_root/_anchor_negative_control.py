# -*- coding: utf-8 -*-
"""[v1.21.73 负对照] 证明锚点对照器**会**判「冲突」，而不只是奉承。

为什么必须做：ON 臂报「冲突 0 条」有两种可能 —— 真的没冲突，或者这把尺
压根不会判冲突。不做这一步，两者无法区分（预注册里写死了这条）。

做法：拿**同一份锚点**，喂一组明显与锚点相反的合成结论，看它判不判冲突。
同时塞一条与锚点一致的结论，看它会不会判印证 —— 只判冲突不判印证的尺子
同样没用（那是逢迎的反面：逢反）。

跑法：
  python _anchor_negative_control.py
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import contextlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.73.py"
ANCHORS = HERE / "anchors" / "up_biz_anchors.json"


def load_dotenv(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# 明显与锚点相反的结论（每条后面标了它违哪条）
CONFLICTING = [
    ("自动化产线在任何行业都能在 1 年内回本，回本周期与订单结构和稼动率无关", "违 a1/a5/a6"),
    ("设备买回来即使长期闲置也不产生成本，折旧和利息只在开机时发生", "违 a5/a8"),
    ("多品种小批量的零散订单同样适合全套刚性自动化产线，换产调试成本可以忽略", "违 a6/a8"),
    ("工艺没标准化也能直接上自动化，自动化设备会自动修正来料波动，不会放大报废", "违 a7"),
]
# 与锚点一致的结论（应该判印证或无对应，不该被判冲突）
CONSISTENT = [
    ("先做瓶颈工序的局部自动化、分阶段投入，可以降低一次性重资产投入的风险", "合 a9/a12 方向"),
]


def main() -> int:
    load_dotenv(HERE / ".env")
    spec = importlib.util.spec_from_file_location("dgtf73nc", str(SRC))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf73nc"] = mod
    spec.loader.exec_module(mod)

    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
    cfg["external_anchor"] = {"enabled": True, "path": str(ANCHORS),
                              "max_items": 12, "crosscheck": True}
    m = mod.MetaDGTF(cfg)
    m.verbose = False
    m._load_anchors()
    print(f"载入锚点 {len(m._anchors)} 条，err={m._anchor_err or '（无）'}")
    if not m._anchors:
        print("❌ 锚点没载入，负对照无从谈起")
        return 1

    # 塞合成结论（走 `_anchor_claims` 的池路径，与生产同口径）
    m.pools["1"].sub_questions = []
    for i, (txt, _why) in enumerate(CONFLICTING + CONSISTENT, 1):
        m.pools["1"].sub_questions.append(
            {"id": i, "question": txt, "status": "answered"})

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rep = m._anchor_crosscheck({})
    sm = rep.get("summary") or {}
    print(f"claims={sm.get('claims')} 印证={sm.get('supported')} "
          f"冲突={sm.get('conflicted')} 无对应={sm.get('unmatched')} "
          f"用到锚点={sm.get('anchor_used')}")
    print()
    for it in rep.get("items") or []:
        mark = {"印证": "✅", "冲突": "❌", "无对应": "➖"}.get(it.get("verdict"), "?")
        print(f"{mark} {it.get('verdict')} | {it.get('claim', '')[:60]}")
        print(f"     锚点 {it.get('anchor_ids')} | {it.get('note', '')[:80]}")
    if rep.get("error"):
        print(f"error: {rep['error']}")

    conf = int(sm.get("conflicted", 0) or 0)
    sup = int(sm.get("supported", 0) or 0)
    ok = True
    if conf < 1:
        print(f"\n❌ 负对照失败：4 条明显冲突的结论只判出 {conf} 条冲突 "
              f"—— 这把尺不会判冲突，ON 臂的所有数字作废")
        ok = False
    else:
        print(f"\n✅ 负对照通过：{conf} 条判为冲突（尺子会判冲突）")
    if sup < 1:
        print(f"⚠️ 与锚点一致的结论未被判印证（supported={sup}）"
              f"—— 只判冲突不判印证的尺子同样不可用")
        ok = False
    else:
        print(f"✅ 正向也通：{sup} 条判为印证（不是逢反）")

    out = HERE / "_anchor_negative_control.json"
    out.write_text(json.dumps({"report": rep, "ok": ok},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写入 {out.name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

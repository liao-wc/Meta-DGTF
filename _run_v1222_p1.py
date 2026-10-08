# -*- coding: utf-8 -*-
"""[v1.22.2 P1] 真跑验收：ON/OFF 两臂各 2 次（按用户口径：每题只跑 2 次）。

产出：
  outputs/v1222_p1/{ON,OFF}_<i>/*.md     产物
  _v1222_p1_consistency.json             逐跑读数（stabilities / _vote_mode / 头部行）

判据（写进报告，不在本脚本判红）：
  · 两臂**每一跑**的产物头部都必须出现「三态判决（单票/多票）」；
  · 两臂的 stability 分布都可算（不再出现「一致率 0% ⚠️ unstable」）。
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(src):
    spec = importlib.util.spec_from_file_location("dgtf_run", str(HERE / src))
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_run"] = m
    spec.loader.exec_module(m)
    return m


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "元DGTF-V1.22.2.py"
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    q = ("老城区排水管网的现有设计标准是多少年一遇？"
         "该不该整体提标改造、按什么顺序做？")
    mod = load(src)
    base = HERE / "outputs" / "v1222_p1"
    rows = []
    for arm, multi in (("ON", True), ("OFF", False)):
        for i in range(1, reps + 1):
            d = base / ("%s_%d" % (arm, i))
            d.mkdir(parents=True, exist_ok=True)
            cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
            cfg["actions"] = dict(cfg.get("actions") or {})
            cfg["actions"]["tri_multi_vote"] = multi
            cfg["output"] = dict(cfg.get("output") or {})
            cfg["output"]["save_dir"] = str(d)
            cfg["output"]["verbose"] = False
            t0 = time.time()
            meta = mod.MetaDGTF(cfg)
            res = meta.run(q, route=["0", "1"], rounds={"0": 2, "1": 2},
                           parallel_mode="serial", orientation="auto")
            p = mod.save_result(res, str(d))
            subs = ((res.get("pools") or {}).get("1") or {}).get(
                "sub_questions") or []
            st = [s.get("stability") for s in subs]
            vm = sorted({str(s.get("_vote_mode")) for s in subs})
            md = p.read_text(encoding="utf-8")
            line = ""
            for ln in md.split("\n"):
                if "三态判决（" in ln or "三态多票**：" in ln:
                    line = ln.strip()
                    break
            rows.append({"arm": arm, "rep": i, "multi": multi,
                         "n_subs": len(subs), "stability": st,
                         "vote_mode": vm, "header": line,
                         "md": str(p), "secs": round(time.time() - t0, 1),
                         "llm_calls": res.get("llm_calls")})
            print("[%s #%d] subs=%d vm=%s st=%s" % (arm, i, len(subs), vm, st),
                  flush=True)
            print("        头部：%s" % line, flush=True)
    out = HERE / "_v1222_p1_consistency.json"
    out.write_bytes(json.dumps(rows, ensure_ascii=False, indent=2)
                    .encode("utf-8"))
    print("已写 " + out.name, flush=True)
    ok = all(("三态判决（" in r["header"]) for r in rows)
    print("两臂每跑都分口径印标题：" + str(ok), flush=True)


if __name__ == "__main__":
    main()

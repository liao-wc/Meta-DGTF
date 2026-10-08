# -*- coding: utf-8 -*-
"""[v1.23.3] 修 `_ab_thinking_v1233.py` 三处（`--from-capture` 路径）：
  ① `_t0` 在跳过录播时未定义；
  ② `cfg` 在跳过录播时未定义（回放要用它建 LLM）；
  ③ ★ 存档写点必须**跳过** —— 否则把 direct 驱动来的 5 个 stage 覆盖掉。
"""
from pathlib import Path
import ast

P = Path(__file__).resolve().parent / "_ab_thinking_v1233.py"
s = P.read_text(encoding="utf-8")


def rep1(old, new, tag):
    global s
    assert s.count(old) == 1, "%s：命中 %d 次" % (tag, s.count(old))
    s = s.replace(old, new)
    print("  · %s" % tag)


rep1('''    if "--from-capture" in sys.argv:
        print("[think] --from-capture：跳过录播", flush=True)
    else:''',
     '''    _t0 = time.time()
    if "--from-capture" in sys.argv:
        print("[think] --from-capture：跳过录播", flush=True)
        cfg = m.DEFAULT_CONFIG.copy()
        cfg["output"] = dict(cfg.get("output") or {})
        _rd = HERE / "outputs" / "_v1233_think_replay"
        _rd.mkdir(parents=True, exist_ok=True)
        cfg["output"]["save_dir"] = str(_rd)
        cfg["output"]["verbose"] = False
    else:''', "① _t0 / cfg 补齐")

rep1('''    (HERE / "_v1233_think_capture.json").write_bytes(
        json.dumps({"src": SRC.name, "n_calls": len(rec_calls),
                    "stages": {k: [{"system": c["system"][:4000],
                                    "user": c["user"][:4000],
                                    "temperature": c["temperature"],
                                    "max_tokens": c["max_tokens"],
                                    "json_mode": c["json_mode"]}
                                   for c in v] for k, v in picked.items()}},
                   ensure_ascii=False, indent=1).encode("utf-8"))''',
     '''    if "--from-capture" not in sys.argv:
        # ★ **只在不跳过录播时才写存档** —— 否则回放路径会把只有流程录播的
        #   版本写回去，**覆盖掉** `_ab_thinking_direct.py` 直接驱动来的 stage
        #   （本机实踩：skip 判断放晚了，白跑 16 分钟还差点丢数据）。
        (HERE / "_v1233_think_capture.json").write_bytes(
            json.dumps({"src": SRC.name, "n_calls": len(rec_calls),
                        "stages": {k: [{"system": c["system"][:4000],
                                        "user": c["user"][:4000],
                                        "temperature": c["temperature"],
                                        "max_tokens": c["max_tokens"],
                                        "json_mode": c["json_mode"]}
                                       for c in v]
                                   for k, v in picked.items()}},
                       ensure_ascii=False, indent=1).encode("utf-8"))''',
     "③ 存档写点加守卫")

P.write_text(s, encoding="utf-8")
ast.parse(s)
print("parse OK")

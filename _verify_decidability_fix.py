# -*- coding: utf-8 -*-
"""验证 fix：外部判定器对「信息不足/隐私」类题不再判 decidable。

只调 _assess_decidability 这一步（每道题一次 LLM 调用），不跑完整 DGTF。
用法：python _verify_decidability_fix.py
"""
import sys, importlib.util, io, contextlib
from pathlib import Path
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent


def load_module():
    spec = importlib.util.spec_from_file_location(
        "dgtf60", HERE / "元DGTF-V1.21.61.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["dgtf60"] = mod
    spec.loader.exec_module(mod)
    return mod


QUESTIONS = [
    ("张三今天早餐吃了什么？", "信息不足"),
    ("提问者家的 Wi-Fi 密码是多少？", "隐私信息"),
    ("2038 年世界杯足球赛冠军是哪支球队？", "未来事件（对照，应 undecidable）"),
]


def main():
    load_dotenv(HERE / ".env")
    mod = load_module()
    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
    llm = mod.LLM(cfg)
    d = mod.DGTF("0", llm, cfg)

    for q, kind in QUESTIONS:
        with contextlib.redirect_stdout(io.StringIO()):
            r = d._assess_decidability(q)
        print(f"【{kind}】{q}")
        print(f"  → decidability = {r.get('decidability')}")
        print(f"    原始状态       = {r.get('_original_status')}")
        print(f"    reason         = {r.get('reason')}")
        print(f"    decidable_aspects   = {r.get('decidable_aspects')}")
        print(f"    undecidable_aspects = {r.get('undecidable_aspects')}")
        print()


if __name__ == "__main__":
    main()

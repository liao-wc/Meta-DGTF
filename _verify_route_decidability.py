# -*- coding: utf-8 -*-
"""验证 _route_by_decidability：undecidable 降 [0,1]，partial 保持。
只调外部判定（每例一次 LLM 调用），不跑完整 DGTF。
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


CASES = [
    ("张三今天早餐吃了什么？", "信息不足 → 应降 [0,1]"),
    ("提问者家的 Wi-Fi 密码是多少？", "隐私 → 应降 [0,1]"),
    ("2038 年世界杯足球赛冠军是哪支球队？", "未来事件 → 应保持 full（partial）"),
]


def main():
    load_dotenv(HERE / ".env")
    mod = load_module()
    cfg = mod.load_config(str(HERE / "dgtf_config.yaml"))
    meta = mod.MetaDGTF(cfg)

    for q, expect in CASES:
        with contextlib.redirect_stdout(io.StringIO()):
            r = meta._route_by_decidability(q, ["0", "1", "both", "all"])
        print(f"【{expect}】")
        print(f"  {q}")
        print(f"  route → {r}")
        print()


if __name__ == "__main__":
    main()

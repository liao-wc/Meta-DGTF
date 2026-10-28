# -*- coding: utf-8 -*-
"""生成「全本地档」临时配置：把引擎的 LLM 端点指向本地适配层（零 API 成本）。

用途：预算耗尽时仍能端到端跑引擎，验证**链路与读数**（不是质量）。
输出 `_local_run.yaml`（临时文件，跑完可删）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "dgtf_config.yaml"
DST = ROOT / "_local_run.yaml"
SHIM = "http://127.0.0.1:8773/v1"


def main() -> int:
    cfg = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    api = cfg.setdefault("api", {})
    api["key"] = "local-shim"
    api["base_url"] = SHIM
    # ★ model 名带 stage 后缀会被适配层解析；不带则按 prompt 特征推断。
    api["default_model"] = "local"
    api["reasoner_model"] = "local"
    api["timeout"] = 180

    # ★ 本地档默认打开失败熔断：0.5B 在大 prompt 上会超时（实测每 111s 一次），
    #   不熔断的话后续调用会把每次超时都等满，把整跑拖死。
    api["circuit_breaker"] = {
        "enabled": True,
        "fail_threshold": 3,
        "cooldown_sec": 120,
    }

    # ★ 答案门：本地档**只留痕不阻断**（block=False）。
    #   0.5B 的输出质量本来就差，用它验证时要把门关掉才看得到后续链路；
    #   出厂 dgtf_config.yaml 里是 block=true（真跑才需要那道门）。
    out = cfg.setdefault("output", {})
    if isinstance(out, dict):
        out["answer_gates"] = {"enabled": True, "block": False}

    # 本地档必须关掉会真联网/真花钱的东西
    cfg.setdefault("web_search", {})["enabled"] = False
    (cfg.setdefault("output", {}) or {})
    cfg["output"]["verbose"] = False
    # 思考档在本地模型上没有收益，且会把 max_tokens 抬到 32000
    th = cfg.setdefault("api", {}).setdefault("thinking", {})
    if isinstance(th, dict):
        th["default"] = "disabled"
    # 成本护栏：本地跑也要有上限，防止挂死
    cfg["max_tokens"] = 200000

    DST.write_text(
        "# 由 _mk_local_config.py 生成：全本地档（零 API 成本，链路验证用）\n"
        + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False,
                         default_flow_style=False),
        encoding="utf-8")
    print("写出 %s（base_url=%s）" % (DST.name, SHIM))
    return 0


if __name__ == "__main__":
    sys.exit(main())

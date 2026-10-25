# -*- coding: utf-8 -*-
"""前缀缓存机制小测（零/极低成本，决定要不要做 prompt 重排）。

DeepSeek 官方定价：输入 cache hit $0.003/M vs cache miss $0.15/M（谷时）= 50×。
本脚本验证三件事：
  A. 相同长 system + 不同 user → 第二次是否命中缓存（命中量多少）；
  B. system 里插入一段**每次变化**的内容（变体放前面）→ 是否破坏命中；
  C. 把变化内容挪到末尾（静态在前）→ 是否恢复命中。
这三条直接决定引擎 prompt 重排的收益上限与做法。

用法：python scripts/lead_prefix_cache_test.py [--runs 2] [--tokens 800]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_env() -> dict:
    out = {}
    for ln in (ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokens", type=int, default=800,
                    help="静态段目标 token 数（用中文重复填充近似）")
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()
    from openai import OpenAI
    env = read_env()
    cli = OpenAI(api_key=env.get("DGTF_API_KEY"),
                 base_url=env.get("DGTF_BASE_URL", "https://api.deepseek.com/v1"))

    # 约 1 token ≈ 1.5 汉字；用确定性文本填充
    filler = "".join("对偶判断只看位置维度，属性由来源决定，不用猜。" for _ in range(
        max(1, args.tokens // 20)))
    static = ("你是【对偶判断者】。只判位置：0 / 1 / both。"
              "严格 JSON：{\"judgments\":[{\"idx\":1,\"position\":\"0|1|both\"}]}\n"
              "【静态规范】\n" + filler)
    variable_head = "\n【本圈变化】第 %d 圈，锚点文本：%s\n"
    variable_tail = "\n【本圈候选】\n1. [concept] 候选 %s\n"

    def call(system: str, user: str, tag: str) -> dict:
        t0 = time.monotonic()
        r = cli.chat.completions.create(
            model="deepseek-flash",
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            max_tokens=60, temperature=0, response_format={"type": "json_object"})
        u = r.usage
        extra = getattr(u, "model_extra", None) or {}
        return {"tag": tag, "ms": int((time.monotonic() - t0) * 1000),
                "prompt": getattr(u, "prompt_tokens", 0),
                "completion": getattr(u, "completion_tokens", 0),
                "cache_hit": int(extra.get("prompt_cache_hit_tokens") or 0),
                "cache_miss": int(extra.get("prompt_cache_miss_tokens") or 0),
                "content": (r.choices[0].message.content or "")[:120]}

    rows = []
    # A：静态 system（完全相同）+ 不同 user
    for i in range(args.runs):
        rows.append(call(static, "输出 {\"judgments\":[{\"idx\":1,\"position\":\"0\"}]}",
                         "A_same_system_%d" % i))
        time.sleep(0.5)
    # B：变化内容放 system 前部
    for i in range(args.runs):
        sys_b = static.replace("你是【对偶判断者】。",
                               "你是【对偶判断者】。本圈=%d。" % i) if i else static
        # 第一次用基准，第二次插入变化
        sys_b = ("【本圈变化】第 %d 圈。\n" % i) + static if i else static
        rows.append(call(sys_b, "输出 {\"judgments\":[{\"idx\":1,\"position\":\"0\"}]}",
                         "B_var_system_head_%d" % i))
        time.sleep(0.5)
    # C：变化内容放 user 末尾（system 静态到底）
    for i in range(args.runs):
        rows.append(call(static,
                         "输出 {\"judgments\":[{\"idx\":1,\"position\":\"0\"}]}"
                         + variable_tail % i,
                         "C_var_tail_%d" % i))
        time.sleep(0.5)
    print(json.dumps(rows, ensure_ascii=False, indent=1))
    total = sum(r["prompt"] for r in rows)
    hit = sum(r["cache_hit"] for r in rows)
    print("\n汇总：prompt=%d cache_hit=%d (%.1f%%)" % (total, hit,
                                                     100.0 * hit / max(1, total)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

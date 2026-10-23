# -*- coding: utf-8 -*-
"""① A/B 对照分析：max_uncovered_pushes 1(A) vs 0(B)。

读 ab_A.log / ab_B.log + 两个 arm 的产物，逐项对比。
用法：python _ab_compare.py
"""
import glob
import os
import re

ARMS = {"A": ("ab_A.log", 1), "B": ("ab_B.log", 0)}


def log_lines(p):
    return open(p, encoding="utf-8", newline="").read().replace(
        "\r\n", "\n").split("\n")


def head(p, pat):
    for l in log_lines(p):
        m = re.search(pat, l)
        if m:
            return m.group(1)
    return "?"


def count(p, pat):
    return sum(1 for l in log_lines(p) if re.search(pat, l))


def product_of(p):
    """从日志的 [OUTPUT] 行取产物路径。"""
    out = head(p, r"^\[OUTPUT\]\s*(.+?)\s*$")
    return out if out != "?" else None


def md_stats(path):
    t = open(path, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    rounds = re.findall(r"实际走了 (\d+) 圈", t)
    return {
        "rounds": rounds,
        "bytes": len(t.encode("utf-8")),
        "answered": (re.findall(r"answered_sub_ids：\[([^\]]*)\]", t)
                     or ["?"])[0],
        "distance": (re.search(r"- distance：([\d.]+)", t)
                     or [None, "?"])[1],
        "composite": (re.search(r"\*\*综合距离\*\*：([\d.]+)", t)
                      or [None, "?"])[1],
        "quality": [x.strip() for x in re.findall(
            r"\*\*质量线索\*\*：(.+)", t)],
        "closure": (re.search(r"\*\*闭环清算\*\*：(.+)", t)
                    or [None, "?"])[1].strip(),
        "stops": re.findall(r"\*\*螺旋停止\*\*：(.+)", t),
    }


rows = {}
for tag, (logf, push) in ARMS.items():
    if not os.path.exists(logf):
        print(f"[{tag}] 缺 {logf}，跳过")
        continue
    prod = product_of(logf)
    r = {
        "push": push,
        "calls": head(logf, r"llm_calls=(\d+)"),
        "tokens": head(logf, r"tokens=(\d+)"),
        "elapsed": head(logf, r"耗时 (\d+)s"),
        "exhaust": count(logf, r"体力耗尽"),
        "real_stop": count(logf, r"螺旋停止（第"),
        "defer": count(logf, r"推迟停止"),
        "release": count(logf, r"放行停止"),
    }
    if prod and os.path.exists(prod):
        r.update(md_stats(prod))
        r["product"] = prod
    else:
        r["product"] = None
    rows[tag] = r

print("=" * 72)
hdr = f"{'指标':26}{'A (push=1)':>16}{'B (push=0)':>16}{'差':>12}"
print(hdr)
print("-" * 72)
def line(name, key, fmt=str, diff=True):
    a, b = rows.get("A", {}), rows.get("B", {})
    va, vb = a.get(key, "?"), b.get(key, "?")
    d = ""
    if diff:
        try:
            d = f"{float(vb) - float(va):+.0f}"
        except (TypeError, ValueError):
            d = "—"
    print(f"{name:26}{fmt(va):>16}{fmt(vb):>16}{d:>12}")

line("max_uncovered_pushes", "push")
line("LLM 调用", "calls")
line("token", "tokens")
line("耗时(s)", "elapsed")
line("体力耗尽 次数", "exhaust")
line("真实螺旋停止 次数", "real_stop")
line("fix-88b 推迟 次数", "defer")
line("fix-88b 放行 次数", "release")
line("各层实际圈数", "rounds", fmt=lambda v: (
    "/".join(map(str, v)) if isinstance(v, list) else str(v)), diff=False)
line("产物字节", "bytes")
line("answered", "answered", diff=False)
line("answer.distance", "distance", diff=False)
line("综合距离", "composite", diff=False)
print("-" * 72)
for tag in ("A", "B"):
    r = rows.get(tag)
    if not r:
        continue
    print(f"[{tag}] 质量线索: {r.get('quality')}")
    print(f"[{tag}] 闭环清算: {r.get('closure')}")
    for s in (r.get("stops") or []):
        print(f"[{tag}] 停止: {s[:110]}")
    print(f"[{tag}] 产物: {r.get('product')}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 环境] 把「出厂 yaml 手调 vs 默认值」的 48 项差异**登记成表**。

背景：`check_config_parses` 原来是「yaml 一律不许改默认值」。但
`dgtf_config.yaml` 是 aL 手调的**质量档**（quality + thinking 全开 +
0.7 家族阈值），基线与 rc1 上都是同样 48 项 —— 这条 FAIL 从 v1.21.x
就一直在，属于历史遗留，不是 v1.22 引入。

处理原则：**不放宽检查，改成要销账**。
  · 未登记的差异 → 仍然 FAIL（新漂移照样抓得住）；
  · 登记表里出现过期条目（yaml 已改回默认却没销账）→ 也 FAIL。
两向都锁，登记表不能腐烂。

★ 这是**测试侧**改动（smoke_test.py），不动引擎任何一行。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "smoke_test.py"
SRC = HERE / "元DGTF-V1.22.0-rc1.py"

REASONS = [
    ("cost_profile", "质量档：手调 quality（默认 balanced 是省钱档）"),
    ("api.thinking.effort", "thinking 强度 high（刻意不随档位降）"),
    ("api.thinking.stages.", "thinking 分阶段全开（§档位刻意不覆盖这里）"),
    ("output.show_", "调试期要看 ing / manifest / 探针诊断"),
    ("actions.", "并行预热圈数手调"),
    ("probe.", "探针门限与选条手调"),
    ("memory.", "形状记忆条数与字数手调"),
    ("spiral.", "螺旋停止 / 去重 / 对齐 / 漂移阈值手调（0.7 家族）"),
]

OLD_DIFF_HEAD = ("    diff = [(k, du[k], dd[k]) for k in du if k in dd "
                 "and du[k] != dd[k]]")
OLD_DIFF_TAIL = "    # load_config 必须真的吃进 yaml（不是又退回默认）"

NEW_DIFF = """    du, dd = _flat(user), _flat(mod.DEFAULT_CONFIG)
    diff = [(k, du[k], dd[k]) for k in du if k in dd and du[k] != dd[k]]
    # [v122 环境] 手调项必须**逐条销账**：未登记的差异照旧判红；登记表里
    #   出现过期条目（yaml 已改回默认却没销账）也判红。两向都锁，登记表
    #   才不会腐烂成一张「什么都能过」的名单。
    _unk = [(k, a, b) for k, a, b in diff if k not in CONFIG_TUNED]
    _diff_keys = {k for k, _a, _b in diff}
    _stale = sorted(k for k in CONFIG_TUNED if k not in _diff_keys)
    if _unk:
        print("  \\u2717 [配置] 出厂 yaml 有**未登记**的手调："
              + "；".join(f"{k}: {a!r}\\u2260{b!r}" for k, a, b in _unk[:4]))
        ok = False
    if _stale:
        print("  \\u2717 [配置] 登记表过期（yaml 已改回默认却没销账）："
              + "；".join(_stale[:6]))
        ok = False
    if not _unk and not _stale:
        print(f"  \\u2713 [配置] 出厂 yaml 能解析；手调 {len(diff)} 项"
              f"**全部已登记**，未登记 0 项；登记表无过期条目")
"""


def _keys():
    spec = importlib.util.spec_from_file_location("dgtf_cfg", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_cfg"] = m
    spec.loader.exec_module(m)
    import yaml
    user = yaml.safe_load((HERE / "dgtf_config.yaml").read_text("utf-8")) or {}

    def _flat(d, pre=""):
        out = {}
        for k, v in (d or {}).items():
            key = f"{pre}.{k}" if pre else str(k)
            if isinstance(v, dict):
                out.update(_flat(v, key))
            else:
                out[key] = v
        return out
    du, dd = _flat(user), _flat(m.DEFAULT_CONFIG)
    return sorted(k for k in du if k in dd and du[k] != dd[k])


def main() -> int:
    ks = _keys()
    assert len(ks) == 48, f"手调项应为 48，实测 {len(ks)}：{ks}"

    def _reason(k):
        for pre, r in REASONS:
            if k == pre or k.startswith(pre):
                return r
        raise SystemExit(f"没有为 {k} 指定理由 —— 登记表不许有裸条目")

    body = [
        "# [v122 环境] `dgtf_config.yaml` 相对 `DEFAULT_CONFIG` 的**已销账**"
        "手调项。",
        "#   表里每一项都是「有意为之」，理由写在值里。`check_config_parses`",
        "#   对**不在表里**的差异照旧判红，对**在表里但已不再差异**的条目也判红"
        " —— 两向都要对上账，登记表才不会腐烂成一张什么都能过的名单。",
        "#   ★ 说明文字一律放注释，不要塞进 dict 当第一个元素：相邻的两个字符串",
        "#     字面量会被 Python **静默拼接**成一个键，dict 里就只剩一条巨型条目"
        "（实测踩过）。",
        "CONFIG_TUNED = {",
    ]
    for k in ks:
        body.append(f'    "{k}": "{_reason(k)}",')
    body.append("}")
    block = "\n".join(body) + "\n\n\n"

    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and b.count(b"\r\r\n") == 0
    s = s.replace("\r\n", "\n")

    # 幂等前置：先摘掉旧的登记表（含它上面那几行注释）
    lines0 = s.split("\n")
    if "CONFIG_TUNED = {" in lines0:
        i0 = lines0.index("CONFIG_TUNED = {")
        j0 = next(i for i in range(i0 + 1, len(lines0)) if lines0[i] == "}")
        k0 = i0
        while k0 > 0 and lines0[k0 - 1].startswith("# [v122 环境]"):
            k0 -= 1
        while k0 > 0 and lines0[k0 - 1].strip() == "":
            k0 -= 1
        del lines0[k0:j0 + 1]
        s = "\n".join(lines0)
        print("  · 已摘除旧登记表（幂等）")

    anchor = "def check_config_parses():"
    assert s.count(anchor) == 1, "check_config_parses 定义不唯一"
    s = s.replace(anchor, block + anchor, 1)

    # 用**行号切片**做替换：这段源码里混着字面 `✗` 与 `\u2717` 两种写法，
    # 直接拼字符串锚点会被自己的转义坑到（实测第一次就 0 命中）。
    lines = s.split("\n")
    i1 = [i for i, l in enumerate(lines) if l == OLD_DIFF_HEAD]
    i2 = [i for i, l in enumerate(lines) if l == OLD_DIFF_TAIL]
    assert len(i1) == 1, f"diff 头行锚点 {len(i1)} 处"
    assert len(i2) == 1, f"diff 尾行锚点 {len(i2)} 处"
    assert i2[0] > i1[0], "尾行在头行之前，锚点不对"
    old_body = "\n".join(lines[i1[0]:i2[0]]) + "\n"
    s = s.replace(old_body, NEW_DIFF, 1)

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    TARGET.write_bytes(out.encode("utf-8"))
    print(f"✓ 登记表写入 smoke_test.py：{len(ks)} 项")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 收尾] 把「出厂 yaml 被外部手改」这件事写进报告 §9/§10 与工作记忆。"""
from __future__ import annotations

import sys
from pathlib import Path

CR = chr(13)
LF = chr(10)
NL = chr(10)


def patch_report() -> None:
    p = Path("v1221_报告.md")
    raw = p.read_bytes()
    s = raw.decode("utf-8")
    assert (CR + CR + LF) not in s
    _crlf = (s.count(CR + LF) == s.count(NL)) and (s.count(NL) > 0)
    t = s.replace(CR + LF, NL) if _crlf else s

    old = NL.join([
        "★ 因此**没有**再做一轮「加圈数」的补测：主流缺口（`_not_do` 恒空）是**已知的设计缺口**，",
        "不是圈数不够造成的 —— 加圈数不会让 `_not_do` 从空变满。",
    ])
    new = NL.join([
        "★ 因此**没有**再做一轮「加圈数」的补测：主流缺口（`_not_do` 恒空）是**已知的设计缺口**，",
        "不是圈数不够造成的 —— 加圈数不会让 `_not_do` 从空变满。",
        "",
        "### ⚠️ F.1 期间出厂 `dgtf_config.yaml` 被外部手改（已查明并恢复）",
        "",
        "F.1 跑完后冒烟报了配置红：出厂 yaml 里 `external_anchor` 三项与默认不同且**未登记** ——",
        "`enabled: true`（默认 false）、`as_evidence: \"gate\"`（默认 \"off\"）、`triage: true`（默认 false）。",
        "",
        "**查明过程与结论**：",
        "",
        "- 该 yaml 的 mtime 落在 F.1 期间；但把工作区**所有** `*.py` 扫了一遍，",
        "  **没有任何脚本**写它（唯一命中写动作的 `_audit_eval_quality.py` 本会话没跑过）；",
        "- `triage: true` 这个字面串**只存在于这个 yaml**，不在任何脚本/示例里；",
        "- `enabled: true` 配 `path: \"\"` 是**自相矛盾**：必然走",
        "  「外部锚点加载失败：enabled=True 但没有给 path」——实测 F.1 的 20 题里",
        "  **10 题的产物带着这条假告警**，`_bench_v1221_full.log` 里也有。",
        "",
        "⇒ 判为**事故性外部手改**（没人会想要「一半产物报一条必然失败的锚点告警」）。",
        "处置：备份为 `_bak_dgtf_config.pre_anchor_revert.yaml`，把三项**恢复成默认值**",
        "（`false / \"off\" / false`），并核对 `load_config` 生效值 == `DEFAULT_CONFIG`。",
        "之后冒烟回绿：`[配置] 能解析；键已列全（129 项，豁免 0 项）；手调 48 项全部已登记`。",
        "",
        "★ 两件事值得记下来：",
        "① **这条红项正是配置检查该拦的东西** —— 出厂文件与默认悄悄分叉，而没有任何东西",
        "看得见（v1.22.0 那轮的「配置文件同步」就是为了治这个病）；",
        "② **F.1 的产物里那 10 条锚点告警是噪声，不是缺陷**：锚点加载失败 → 无锚点 →",
        "对照退化为「无锚点」路径，对判定/一致率/rubric 都无影响（十道题的读数与另十道同分布）。",
    ])
    assert t.count(old) == 1, t.count(old)
    t = t.replace(old, new, 1)

    old2 = NL.join([
        "    这两处都不是「改动引擎」能立刻解决的，也不该靠放宽 `min_actions` 去凑",
        "    （见第八节第 2 条：那是把尺子改短）。",
    ])
    new2 = NL.join([
        "    这两处都不是「改动引擎」能立刻解决的，也不该靠放宽 `min_actions` 去凑",
        "    （见第八节第 2 条：那是把尺子改短）。",
        "13. **出厂 yaml 的分叉要一直看得见**：本轮 F.1 期间 `dgtf_config.yaml` 被外部手改",
        "    （`external_anchor` 三项 `enabled/true`、`as_evidence/gate`、`triage/true`，",
        "    未登记），已查明非本轮脚本所写、判定为事故并恢复默认（见第九节末尾）。",
        "    下一版可考虑：让这类「出厂文件被改」不仅冒烟判红，**也在产物头部留一行**",
        "    （现在只在冒烟里可见）。",
    ])
    assert t.count(old2) == 1, t.count(old2)
    t = t.replace(old2, new2, 1)

    out = t.replace(NL, CR + LF) if _crlf else t
    assert (CR + CR + LF) not in out
    p.write_bytes(out.encode("utf-8"))
    print("  ✓ v1221_报告.md 已补 yaml 事故段与第 13 条")


def patch_memory() -> None:
    m = Path(".workbuddy/memory/2026-10-05.md")
    t = m.read_bytes().decode("utf-8").replace(CR + LF, LF).rstrip(NL)
    key = "出厂 yaml 被外部手改"
    if key in t:
        print("  · 记忆已含该段（跳过）")
        return
    add = NL.join([
        "",
        "### ⚠️ 出厂 `dgtf_config.yaml` 被外部手改（F.1 期间，已查明并恢复）",
        "",
        "F.1 跑完后冒烟红：yaml 里 `external_anchor.enabled: true`（默认 false）、",
        "`as_evidence: \"gate\"`（默认 \"off\"）、`triage: true`（默认 false），三项**未登记**。",
        "- 扫遍工作区所有 `*.py`：**没有脚本**写它；`triage: true` 这个字面串只在这个 yaml 里。",
        "- `enabled: true` + `path: \"\"` 自相矛盾（必然报「enabled=True 但没有给 path」）→",
        "  实测 F.1 的 20 题里 **10 题产物带这条假告警**。",
        "- 判为事故性手改；备份 `_bak_dgtf_config.pre_anchor_revert.yaml`，三项恢复默认，",
        "  `load_config` 生效值 == `DEFAULT_CONFIG` 已核对；冒烟回绿（129 键 / 48 手调全登记）。",
        "",
        "★ 顺带修掉同一族的另一处：**冒烟 `check_v1221_p3` 也在拿活审计当锚**",
        "（我只先改了验收脚本的 P3.4）→ 同样改成对 `_negctl_v1221_p3_frozen.json` 冻结快照。",
        "教训：同一判据在两处实现（验收 + 冒烟）时，改一处必须**同时**改另一处。",
    ])
    m.write_bytes((t + NL + add).replace(NL, CR + LF).encode("utf-8"))
    c = m.read_bytes()
    print("  ✓ 记忆已追加（crr " + str(c.count(bytes([13, 13, 10]))) + "）")


def main() -> int:
    patch_report()
    patch_memory()
    return 0


if __name__ == "__main__":
    sys.exit(main())

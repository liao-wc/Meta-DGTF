#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 配置同步] 把出厂配置 `dgtf_config.yaml` 同步到 v1.22.0。

背景：v1.22.0 的 `DEFAULT_CONFIG` 多了 5 个键、`as_evidence` 由布尔升级为
五档字符串，而 `dgtf_config.yaml` 一次都没跟上 —— 而且经查，它还漏着更早
版本就有的 10 个键（`actions.input_sanity` / `actions.parallel_expand` /
`memory.self_layers_per_entry` / `spiral.both_quota.*` 等）。共 15 个键。
「漏键」这件事此前**没有任何检查看得见**，所以「同步过」只是句口头承诺。

本脚本做三件事：
  A. yaml 头部版本 → v1.22.0，并补一段【v1.21.77 → v1.22.0】升级说明；
  B. 把 15 个漏键按**默认值**写进 yaml（值不动 = 行为不动），各带注释；
  C. 给 `check_config_parses` 补**第三向**：yaml 必须列全 DEFAULT_CONFIG
     的键（漏键判红 + 豁免表过期也判红）。配合已有的「未登记差异判红 /
     过期登记判红」，配置文件同步就闭合了，不会再悄悄漂移。

★ 为什么「列全」不会把默认值钉死：值一旦与当前默认不符，已有的那两向
  立刻报红（未登记即红）。所以列全 = 可核，不是 = 冻结。

★ 锚点一律用**整行相等**（不用子串）：本项目踩过「8 空格注释是 12 空格
  同名注释的子串 → 替换发生在行中间、留下残渣 + IndentationError」。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML_T = HERE / "dgtf_config.yaml"
SMOKE_T = HERE / "smoke_test.py"
SRC = HERE / "元DGTF-V1.22.0.py"

SENTINEL_YAML = "# 【v1.21.77 → v1.22.0】"
SENTINEL_SMOKE = "CONFIG_NOT_IN_YAML"


# ---------------------------------------------------------------
# A/B. yaml 的改动：("repl" 整行换 / "ins_before" / "ins_after", 锚点整行, 载荷行)
# ---------------------------------------------------------------
YAML_OPS = [
    ("repl", "# 元 DGTF · v1.21.56 配置文件",
     ["# 元 DGTF · v1.22.0 配置文件"]),

    ("repl", "# 【本文件是 DEFAULT_CONFIG 的覆盖层】",
     ["# 【本文件是 DEFAULT_CONFIG 的完整覆盖层】"]),
    ("repl", "#   缺省字段用代码内置默认，不需要全部写出。",
     ["#   本文件把 DEFAULT_CONFIG 的键**列全**（冒烟 check_config_parses",
      "#   会核「有没有漏键」）；值上与默认不同的只有 48 项手调，逐条登记在",
      "#   CONFIG_TUNED 里 —— 未登记的差异判红、过期登记也判红。",
      "#   ★ 列全 ≠ 钉死：任何一项与当前默认值不符且未登记，冒烟立刻报红，",
      "#     所以「默认改了而本文件没跟上」不会静默发生。"]),

    # 【分层说明】补两行（原来漏了 cost_profile 与 external_anchor）
    ("ins_before", "#   api      —— API 连接",
     ["#   cost_profile    —— 成本档位（economy / balanced / quality，顶层总控）"]),
    ("ins_before", "#   spiral   —— 螺旋停止 / 循环判据",
     ["#   external_anchor —— 外部事实锚点（题外参照：不进池、不参与清算）"]),

    # 【修改心法】补三条
    ("ins_after", '#   调"B/C 预热几圈"   → 改 actions.parallel_warmup_rounds',
     ['#   调"要不要行动清单"   → 改 actions.landing_decision（取向 decision 时才生效）',
      '#   调"子问题判得准不准" → 改 actions.tri_multi_vote（三态多票）',
      '#   调"接不接外部事实"   → 改 external_anchor.*（默认全关，不花调用）']),

    # 升级说明段（插在现有最新段之前，保持"最新在最前"）
    ("ins_before", "# 【v1.21.55 → v1.21.56】", [
        "# 【v1.21.77 → v1.22.0】",
        "#   新增字段（都有默认值；本文件按「列全」原则已写出，见上）：",
        "#     external_anchor.as_evidence: \"off\"  ← 布尔升级为**五档**：",
        "#         off / record / crosscheck / evidence / gate",
        "#         （旧写法 true / false 仍认，true → \"evidence\"，兼容一版）",
        "#     external_anchor.retriever: \"snapshot\"",
        "#         \"snapshot\" = 零调用读快照；其它值走真检索（当前实现 tavily，",
        "#         结果按 queries 的 sha256 落 cache/anchors/，TTL 内不打网络）；",
        "#         未知取值**抛错留痕**，不静默降级。",
        "#     external_anchor.tier_floor: 2    ← 锚点分级门槛：tier ≤ 2 才允许",
        "#         进「结论 → 锚点」引用表（1 一手标准 / 2 权威二手 / 3 一般二手",
        "#         / 4 传闻转述 —— 转述可以留痕，但不当证据）。",
        "#     external_anchor.per_round: 2     ← 每圈最多并入几条锚点（元层不检索）",
        "#     external_anchor.api_key_env / cache_ttl_hours",
        "#         ← 真检索后端的 key 环境变量名 / 结果缓存小时数（key 不进本文件）",
        "#     external_anchor.triage: false    ← 分诊降级：undecidable 的理由若是",
        "#         「信息不足 / 需外部动作 / 缺数据 / 无外部」，而锚点里**有**材料",
        "#         能答，该条降为 decidable 或 partial；「自指循环 / 无共同参照系 /",
        "#         本体论判断」一律**不降**。",
        "#     actions.tri_multi_vote: true     ← 子问题可判定性**三态多票**：同一条",
        "#         问三个视角各判一次取多数；三票互异 = 无多数票 → 进校准队列",
        "#         （不再是「每条都塞进队列」，队列只收真要人工核的）。",
        "#     actions.landing_decision: true   ← 取向 decision 时，落脚段改渲染",
        "#         「行动清单六字段（verb/object/owner_role/deadline_hint/",
        "#         acceptance/fallback）+ 不做什么 + 决策 rubric」。",
        "#         取向 boundary 或关掉本项 → 退回老模板（池级留痕两者共用，不丢）。",
        "#     actions.input_sanity: true       ← 输入健全性自检（只报告、不改写）",
        "#     actions.parallel_expand: true    ← 一次展开里多个 job 并发调 LLM",
        "#     memory.self_layers_per_entry: 2  ← self 通道**每层**保留几条",
        "#         （与 memory.self_layers 是两个口径，别当替代关系）",
        "#     spiral.both_quota.{enabled,max_ratio,min_items}",
        "#         ← both 占比超 max_ratio 就去问「缺什么」（**追问**，不动极性；",
        "#           both_tighten_ratio 才是**改判**，两条语义完全不同）",
        "#   行为变化（不需要改配置）：",
        "#     · 产物头部多「分层目标（修行/研究/对撞/元）」「三态多票 / 冻结",
        "#       签名」「机制审计」三段；日志同印。",
        "#     · 硬约束 flag（action_incomplete / not_do_missing）不再被",
        "#       quality_flags 的重算冲掉。",
        "#   怎么退回旧行为：",
        "#     actions.tri_multi_vote / actions.landing_decision /",
        "#     actions.input_sanity / actions.parallel_expand 全置 false，",
        "#     external_anchor 保持 enabled: false（默认即关）→ 与 v1.21.77 同。",
        "#",
    ]),

    # A. 四个 actions 键
    ("ins_before", "  # 【用途】是否做全局可判定性评估。", [
        "  # 【用途】输入健全性自检（v1.21.50 [P1-6] 引入）。",
        "  #   「PN 不是任何标准复杂度类」那次事故：引擎不知道，把一个可能",
        "  #   是笔误的符号当合法对象收下，跑了 168 次调用。",
        "  # 【建议】保持 true。",
        "  # 【注意】只报告、不改写 —— 替用户改写问题等于替他决定想问什么。",
        "  # 【关闭后】本步不跑，产物里 input_sanity 段为空。",
        "  input_sanity: true",
        "",
    ]),
    ("ins_before", "  # ---------- ★ v1.21.54 并行模式 ----------", [
        "  # 【用途】子问题可判定性的**三态多票**（v1.22 引入）。",
        "  #   同一条子问题问三个视角各判一次（decidable / partial /",
        "  #   undecidable），取多数票；三票互异 = 无多数票 → 进校准队列。",
        "  # 【建议】保持 true。",
        "  # 【关闭后】退回单票判定，产物无 tri_consensus / calibration_queue。",
        "  tri_multi_vote: true",
        "",
    ]),
    ("ins_after", '  parallel_mode: "auto"', [
        "",
        "  # 【用途】一次展开里多个 job（阴/阳、&/线头）**并发**调 LLM。",
        "  # 【建议】true —— 每层每圈省一次往返。",
        "  # 【关闭后】job 串行执行：调用数不变、耗时变长（排查限流时用）。",
        "  parallel_expand: true",
    ]),
    ("ins_before", "  # 【用途】self-check（自省）。", [
        "  # 【用途】落地决策模板（v1.22 引入）。",
        "  #   取向为 decision 时，落脚段渲染「行动清单六字段（verb / object /",
        "  #   owner_role / deadline_hint / acceptance / fallback）+ 不做什么 +",
        "  #   决策 rubric」，而不是原来的 boundary 留痕模板。",
        "  # 【建议】true。",
        "  # 【关闭 / 取向 boundary】退回老模板（池级留痕两个模板共用，不丢）。",
        "  landing_decision: true",
        "",
    ]),

    # B. external_anchor 的 7 个键
    ("ins_before", "  # 【用途】收尾要不要做「结论 vs 锚点」只读对照（一次额外 LLM 调用）。", [
        "  # 【用途】锚点检索后端（v1.22 引入）。",
        "  #   \"snapshot\" —— **零调用**：直接读上面 path 指的快照 JSON（默认）。",
        "  #   其它取值    —— 走真检索：当前实现 `tavily`，结果按 queries 的",
        "  #                  sha256 落 `cache/anchors/`，TTL 内不再打网络；",
        "  #                  未知取值**抛错留痕**，不静默降级。",
        "  retriever: \"snapshot\"",
        "",
        "  # 【用途】真检索后端读 API key 的环境变量名（key 不写进本文件）。",
        "  api_key_env: \"TAVILY_API_KEY\"",
        "",
        "  # 【用途】真检索结果的缓存有效期（小时）：期内同 queries 不再打网络。",
        "  cache_ttl_hours: 24",
        "",
        "  # 【用途】每圈最多并入几条锚点（0 = 本圈不检索）。元层（all）不检索。",
        "  per_round: 2",
        "",
        "  # 【用途】锚点**分级门槛**（v1.22 引入）：tier ≤ 此值的锚点才允许进",
        "  #   「结论 → 锚点」引用表。tier 越小越硬：",
        "  #     1 = 一手标准/官方　2 = 权威二手　3 = 一般二手　4 = 传闻转述",
        "  # 【建议】2 —— 网络转述（3/4）可以留痕，但不当证据。",
        "  # 【失败行为】值不合法 → 回落 2，不静默放松成「全都进表」。",
        "  tier_floor: 2",
        "",
    ]),
    ("ins_after", "  crosscheck: true", [
        "",
        "  # 【用途】锚点**证据资格**五档（v1.22 引入，取代旧的布尔写法）。",
        "  #   \"off\"        不参与（旧 false 等价，默认）",
        "  #   \"record\"     只记进产物，不进引用表",
        "  #   \"crosscheck\" 只做收尾只读对照",
        "  #   \"evidence\"   允许被「结论 → 锚点」引用表引用（再受 tier_floor 门控）",
        "  #   \"gate\"       最高档",
        "  # 【建议】\"off\" —— 打开要多花调用；想验锚点链路时逐档上调。",
        "  # 【兼容】旧写法 as_evidence: true / false 仍认（true → \"evidence\"）。",
        "  as_evidence: \"off\"",
        "",
        "  # 【用途】分诊降级（v1.22 引入）。",
        "  #   开启后，研究层某条 undecidable 的理由若属于",
        "  #   「信息不足 / 需外部动作 / 缺数据 / 无外部」，而池里的外部锚点",
        "  #   **有**材料能答 → 该条降为 decidable 或 partial；",
        "  #   理由若是「自指循环 / 无共同参照系 / 本体论判断」→ 检索无关，",
        "  #   **保持 undecidable，不许降级**。",
        "  # 【建议】false（默认）—— 只在这四类理由上动，且只出建议清单。",
        "  triage: false",
    ]),

    # B. memory / spiral 各一处
    ("ins_after", "  self_layers: 4", [
        "",
        "  # 【用途】self 通道**每层**保留几条（v1.21.50 [P1-4] 引入）。",
        "  #   以前是「最近 self_layers 条」，0 层刷屏会把研究层的挤掉；改成",
        "  #   每层各留本项条数，再按（圈序, 层序）交错。",
        "  # 【建议】2。",
        "  # 【注意】与 self_layers 是**两个口径**：总条数 ≈ 本项 × 参与的层数。",
        "  self_layers_per_entry: 2",
    ]),
    ("ins_before", "  # ---------- ★ v1.21.56 · 四象限对齐的两条判据 ----------", [
        "  # ---------- ★ v122 · both 配额（**追问**，不动极性）----------",
        "",
        "  # 【用途】both 占比超过 max_ratio → 去问「缺什么」，把答案挂进",
        "  #   view.both_quota.missing，下一圈据此要求把缺的东西生出来。",
        "  # 【建议】max_ratio 0.7 / min_items 2（条数太少不判占比）。",
        "  # 【关闭】enabled: false → 不追问（both 占比再高也不补裁）。",
        "  # ⚠️ 上面 both_tighten_ratio 是**改判**（动极性），这里才是**追问**，",
        "  #    两条阈值语义完全不同，别混。",
        "  both_quota:",
        "    enabled: true",
        "    max_ratio: 0.7",
        "    min_items: 2",
        "",
    ]),
]


# ---------------------------------------------------------------
# C. smoke_test.py 的改动（第三向：列全）
# ---------------------------------------------------------------
CONST_BLOCK = [
    "# [v122 配置同步] 允许**不出现在** dgtf_config.yaml 里的键（默认空）。",
    "#   默认策略是「yaml 必须列全 DEFAULT_CONFIG 的键」—— 这样新字段不会",
    "#   悄悄漏在配置文件外（本次同步前已经漏了 15 个，没有一个检查看得见）。",
    "#   真要留一个键只给代码用，必须在这里登记并写清理由；登记了却已经写进",
    "#   yaml 的，同样判红（两向对账，和 CONFIG_TUNED 一个道理）。",
    "CONFIG_NOT_IN_YAML = {}",
    "",
    "",
]

CHECK_BLOCK = [
    "    # [v122 配置同步] 第三向：本文件必须**列全** DEFAULT_CONFIG 的键。",
    "    #   ★ 判红而不是只打提示：漏键是**看不见**的漂移 —— 「同步过」如果",
    "    #     没有检查兜着，就只是句口头承诺。",
    "    #   ★ 列全不等于把值钉死：值一旦与当前默认不符，上面两向立刻报红",
    "    #     （未登记即红），所以默认改了而本文件没跟上也不会静默。",
    "    _miss = sorted(k for k in dd",
    "                   if k not in du and k not in CONFIG_NOT_IN_YAML)",
    "    _x_stale = sorted(k for k in CONFIG_NOT_IN_YAML if k in du)",
    "    if _miss:",
    "        print(\"  ✗ [配置] 出厂 yaml 漏了 DEFAULT_CONFIG 的键（未同步）：\"",
    "              + \"；\".join(_miss[:6])",
    "              + (f\" …共 {len(_miss)} 项\" if len(_miss) > 6 else \"\"))",
    "        ok = False",
    "    if _x_stale:",
    "        print(\"  ✗ [配置] 豁免表过期（登记了不进 yaml，其实已写进 yaml）：\"",
    "              + \"；\".join(_x_stale[:6]))",
    "        ok = False",
    "    if not _unk and not _stale and not _miss and not _x_stale:",
    "        print(f\"  ✓ [配置] 能解析；键已列全（{len(dd)} 项，豁免 \"",
    "              f\"{len(CONFIG_NOT_IN_YAML)} 项）；手调 {len(diff)} 项\"",
    "              f\"**全部已登记**；登记表无过期条目\")",
]


def _read_lf(p: Path):
    b = p.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), f"{p.name} 行尾混杂"
    assert b.count(b"\r\r\n") == 0, f"{p.name} 出现 \\r\\r\\n"
    return s.replace("\r\n", "\n")


def _write_crlf(p: Path, s: str):
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and "\r\r\n" not in out
    p.write_bytes(out.encode("utf-8"))


def _apply_yaml(lines):
    for kind, anchor, payload in YAML_OPS:
        idx = [i for i, l in enumerate(lines) if l == anchor]
        assert len(idx) == 1, f"[{kind}] 锚点 {len(idx)} 处：{anchor!r}"
        i = idx[0]
        if kind == "repl":
            lines[i:i + 1] = payload
        elif kind == "ins_before":
            lines[i:i] = payload
        elif kind == "ins_after":
            lines[i + 1:i + 1] = payload
        else:
            raise SystemExit(f"未知 op {kind}")
    return lines


def _apply_smoke(s: str) -> str:
    lines = s.split("\n")
    # 1) 摘掉重复的 `du, dd = _flat(...)`（实测重复 4 行，只留第一行）
    DUP = "    du, dd = _flat(user), _flat(mod.DEFAULT_CONFIG)"
    n = lines.count(DUP)
    assert n >= 1, "找不到 du/dd 行"
    first = lines.index(DUP)
    lines = [l for i, l in enumerate(lines) if l != DUP or i == first]
    print(f"  · du/dd 重复行 {n} → 1")
    # 2) CONFIG_NOT_IN_YAML 常量，插在 CONFIG_TUNED 的 `}` 之后
    i0 = lines.index("CONFIG_TUNED = {")
    j0 = next(i for i in range(i0 + 1, len(lines)) if lines[i] == "}")
    lines[j0 + 1:j0 + 1] = CONST_BLOCK
    # 3) 把「成功提示」那一段换成含列全核对的新段
    i1 = lines.index("    if not _unk and not _stale:")
    assert lines[i1 + 1].lstrip().startswith('print(f"  \\u2713'), \
        f"i1+1 不是成功提示：{lines[i1 + 1]!r}"
    assert lines[i1 + 2].lstrip().startswith('f"**全部已登记**'), \
        f"i1+2 不是成功提示续行：{lines[i1 + 2]!r}"
    lines[i1:i1 + 3] = CHECK_BLOCK
    return "\n".join(lines)


def main() -> int:
    # ---- A/B. yaml ----
    if SENTINEL_YAML in YAML_T.read_text(encoding="utf-8"):
        print("· yaml 已同步过（幂等跳过）")
    else:
        lines = _read_lf(YAML_T).split("\n")
        lines = _apply_yaml(lines)
        _write_crlf(YAML_T, "\n".join(lines))
        print(f"✓ dgtf_config.yaml 同步完成（{len(YAML_OPS)} 处改动）")

    # ---- C. smoke ----
    if SENTINEL_SMOKE in SMOKE_T.read_text(encoding="utf-8"):
        print("· smoke_test.py 已有列全判据（幂等跳过）")
    else:
        _write_crlf(SMOKE_T, _apply_smoke(_read_lf(SMOKE_T)))
        print("✓ smoke_test.py += 列全判据（第三向）")

    # ---- 自检 ----
    import ast
    ast.parse(_read_lf(SMOKE_T))
    import yaml as _y
    u = _y.safe_load(_read_lf(YAML_T)) or {}

    spec = importlib.util.spec_from_file_location("dgtf_cfg_sync", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_cfg_sync"] = m
    spec.loader.exec_module(m)

    def _flat(d, pre=""):
        out = {}
        for k, v in (d or {}).items():
            key = f"{pre}.{k}" if pre else str(k)
            if isinstance(v, dict):
                out.update(_flat(v, key))
            else:
                out[key] = v
        return out

    du, dd = _flat(u), _flat(m.DEFAULT_CONFIG)
    miss = sorted(k for k in dd if k not in du)
    only_y = sorted(k for k in du if k not in dd)
    diff = sorted(k for k in du if k in dd and du[k] != dd[k])
    print(f"  漏键 {len(miss)}　多键 {len(only_y)}　值差异 {len(diff)}")
    assert not miss, f"仍有漏键：{miss}"
    assert not only_y, f"yaml 里有默认没有的键：{only_y}"
    assert len(diff) == 48, f"值差异应为 48，实测 {len(diff)}"
    print("✓ 自检通过：键已列全、值差异仍 48、ast OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

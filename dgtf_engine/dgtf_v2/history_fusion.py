#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史谱系融合层（V2.1.0）。

目标不是把 V1 的代码再复制一遍，而是把 V1.0 → V1.30.4 → V2.0.0 的演化知识
变成可验证的运行时 provenance：

- 读取历史清单 history_manifest.json（由 V1 归档生成）；
- 将每个时代的能力轴映射到当前 V2 实现与测试；
- 在每次运行时选择 contract-first / exploration-first 作业剖面；
- 在 packed 中写入 fusion 读数，供 App / 审计 / 文档引用。

边界：
- 只写元数据，不生成、不改写答案；
- 不依赖网络、API、LLM；
- 历史清单缺失时降级为内置最小清单，不阻断引擎。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

HISTORY_FUSION_VERSION = "2.1.0"
SCHEMA = "metadgtf.history_fusion.v1"
TARGET = "2.1.0"

# 能力轴：V1 来源 -> V2 实现 -> 可复跑判据。
CAPABILITY_AXES: List[Dict[str, Any]] = [
    {"key": "spiral_core", "name": "四层螺旋推理", "v1_origin": "V1.0",
     "v2_implementation": "MetaDGTF.run / _run_serial / dgtf_v2.layers_*",
     "status": "native", "tests": "dgtf_v2/tests.py + tests_core.py", "weight": 1.0},
    {"key": "three_channels", "name": "content/context/self 三通道", "v1_origin": "V1.0",
     "v2_implementation": "MemoryChannel / MetaDGTF.channels",
     "status": "native", "tests": "tests_core.py + smoke_test.py", "weight": 1.0},
    {"key": "evidence_anchor", "name": "证据链与外部锚点", "v1_origin": "V1.21.x",
     "v2_implementation": "dgtf_v2.evidence + external_anchor",
     "status": "native", "tests": "tests_evidence.py + tests_fact_flow.py", "weight": 1.0},
    {"key": "fact_answer_gate", "name": "事实门 / 答案门 / 过程门", "v1_origin": "V1.23.x-V1.30.x",
     "v2_implementation": "fact_flow.py + fact_contract.py + evidence.py",
     "status": "native", "tests": "tests_fact_flow.py + tests_fact_contract.py", "weight": 1.0},
    {"key": "auto_scheduler", "name": "自动调度与 Pareto", "v1_origin": "V1.23.13-V1.23.65",
     "v2_implementation": "dgtf_v2.scheduler（MAPE-K/EVOI/MPC）",
     "status": "native", "tests": "tests.py + tests_decision_policy.py", "weight": 1.0},
    {"key": "frontier_kernels", "name": "前沿内核（e-process/保形/BOCPD/Dung）",
     "v1_origin": "V1.23.64-V1.23.66",
     "v2_implementation": "engine 内 F1-F4 + tests_evidence/consistency",
     "status": "native", "tests": "tests_evidence.py + tests_decidability_audit.py", "weight": 0.8},
    {"key": "quality_cost_pareto", "name": "质量-成本帕累托与信用分配",
     "v1_origin": "V1.23.50-V1.23.66",
     "v2_implementation": "quality report + scheduler credit + bench",
     "status": "native", "tests": "tests_structural_diversity.py + bench", "weight": 0.8},
    {"key": "eml_bitemporal", "name": "EML 双时态知识面", "v1_origin": "V1.24.0",
     "v2_implementation": "dgtf_v2.memory + unified_memory",
     "status": "native", "tests": "tests_unified_memory.py + tests_evidence.py", "weight": 1.0},
    {"key": "four_layer_contracts", "name": "四层契约 F2-F5", "v1_origin": "V1.24.0-V1.25.0",
     "v2_implementation": "layers_all/one/both/zero + contracts.py",
     "status": "native", "tests": "tests_all.py + tests_one.py + tests_both.py + tests_zero.py",
     "weight": 1.0},
    {"key": "l0_generation", "name": "F5 0 层生成", "v1_origin": "V2.0.0（V1 实验线）",
     "v2_implementation": "dgtf_v2.layers_zero.generate_zero_layer",
     "status": "native", "tests": "tests_zero.py", "weight": 1.0},
    {"key": "app_workbench", "name": "本地 Web 工作台", "v1_origin": "V1.4.x app",
     "v2_implementation": "dgtf_app（HTTPS/鉴权/任务/产物/DSH）",
     "status": "native", "tests": "dgtf_app/selftest.py 371 项", "weight": 0.9},
    {"key": "local_model", "name": "本地模型路由 / LoRA", "v1_origin": "V1.23.x app",
     "v2_implementation": "scripts/local_model + app engine_runner",
     "status": "bridged", "tests": "docs/llm_lora_finetune.md + pip check", "weight": 0.7},
    {"key": "rag_online", "name": "RAG / 联网 / 出处", "v1_origin": "V1.23.x",
     "v2_implementation": "app RAG v2 + dgtf_v2.net_policy + web_search",
     "status": "native", "tests": "tests_evidence.py + app selftest", "weight": 0.8},
    {"key": "multi_modal_input", "name": "多轮 / 视觉 / 外部文件", "v1_origin": "V1.30.x",
     "v2_implementation": "multi_turn.py / vision_input.py / external_input.py",
     "status": "native", "tests": "tests_multi_turn.py + tests_vision_input.py + tests_external_input.py",
     "weight": 0.8},
    {"key": "safety_auth", "name": "安全边界（HTTPS/鉴权/网络策略）", "v1_origin": "V1.30.x app",
     "v2_implementation": "server.py + dgtf_v2.net_policy",
     "status": "native", "tests": "tests_api_policy.py + app selftest", "weight": 0.9},
    {"key": "provenance_audit", "name": "决策回执 / 过程账本 / 可回放",
     "v1_origin": "V1.21.x-V1.23.x",
     "v2_implementation": "process_ledger.py + replay.py + decision_trace",
     "status": "native", "tests": "tests_facet_ledger.py + tests_decidability_audit.py", "weight": 1.0},
    {"key": "history_fusion", "name": "历史谱系融合（V2.1 创新）",
     "v1_origin": "V1.0-V1.30.4（整个历史）",
     "v2_implementation": "dgtf_v2.history_fusion + 运行时 provenance",
     "status": "native", "tests": "tests_history_fusion.py", "weight": 1.0},
]

_ERAS_FALLBACK = [
    {"name": "V1.0-V1.9", "key": "foundation", "start": "V1.0",
     "capabilities": ["四层螺旋推理", "三通道", "单文件引擎", "产物落盘与审计"]},
    {"name": "V1.10-V1.20", "key": "evidence", "start": "V1.10",
     "capabilities": ["证据链", "EML 雏形", "质量读数", "并行档位"]},
    {"name": "V1.21.x", "key": "self-audit", "start": "V1.21",
     "capabilities": ["自动调度", "探针/悬置/延迟债务", "输入自检", "分环节成本"]},
    {"name": "V1.22.x", "key": "architecture", "start": "V1.22",
     "capabilities": ["模块边界", "依赖审计", "快照续跑", "回归门禁"]},
    {"name": "V1.23.x", "key": "frontier", "start": "V1.23",
     "capabilities": ["前沿内核", "质量-成本 Pareto", "事实/答案门", "RAG"]},
    {"name": "V1.24-V1.25", "key": "v2-shadow", "start": "V1.24",
     "capabilities": ["V2 影子调度", "EML 双写", "四层契约", "L0-v2 archive"]},
    {"name": "V1.26-V1.30", "key": "hardening", "start": "V1.26",
     "capabilities": ["答案/过程门分离", "事实卡", "真跑验收", "多模态输入"]},
    {"name": "V2.0", "key": "three-planes", "start": "V2.0.0",
     "capabilities": ["EML v2", "Scheduler v2", "F2-F5", "F5 0 层生成", "App V2"]},
    {"name": "V2.1", "key": "fusion", "start": "V2.1.0",
     "capabilities": ["历史谱系融合", "能力连续性审计", "运行 provenance", "来源文档"]},
]

def _root() -> Path:
    return Path(__file__).resolve().parents[2]

def manifest_path() -> Path:
    return Path(__file__).with_name("history_manifest.json")

def version_key(version: str) -> tuple:
    parts = [int(x) for x in str(version).strip(".").lstrip("vV").split(".") if x]
    return tuple(parts) + (0,) * (4 - len(parts))

def load_manifest(path: Optional[str] = None) -> Dict[str, Any]:
    p = Path(path) if path else manifest_path()
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("versions"), list):
                return data
        except Exception:
            pass
    return {
        "schema": "metadgtf.history_manifest.v1",
        "project": "Meta-DGTF-道生三阶模型",
        "generated_at": "unknown",
        "archive": "（历史清单缺失：降级为内置最小清单）",
        "eras": _ERAS_FALLBACK,
        "versions": [
            {"version": e["start"], "era": e["name"], "era_key": e["key"],
             "capabilities": e["capabilities"], "source": "fallback"}
            for e in _ERAS_FALLBACK
        ] + [{"version": TARGET, "era": "V2.1", "era_key": "fusion",
              "status": "target", "capabilities": ["历史谱系融合", "能力连续性审计"]}],
    }

def build_plan(manifest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    m = manifest or load_manifest()
    versions = sorted(
        [v for v in (m.get("versions") or []) if isinstance(v, dict)
         and str(v.get("version") or "").strip()],
        key=lambda v: version_key(v["version"]))
    axes = []
    for a in CAPABILITY_AXES:
        item = dict(a)
        item["covered"] = item["status"] in ("native", "bridged")
        axes.append(item)
    covered = [a for a in axes if a["covered"]]
    readiness = round(
        sum(float(a["weight"]) for a in covered)
        / max(1e-9, sum(float(a["weight"]) for a in axes)), 4)
    missing = [a["key"] for a in axes if not a["covered"]]
    eras = list(m.get("eras") or _ERAS_FALLBACK)
    provenance = {
        "archive": m.get("archive", ""),
        "manifest_versions": len(versions),
        "manifest_schema": m.get("schema", ""),
        "axes": len(axes),
        "native": len([a for a in axes if a["status"] == "native"]),
        "bridged": len([a for a in axes if a["status"] == "bridged"]),
        "retired": len([a for a in axes if a["status"] == "retired"]),
        "readiness": readiness,
        "missing": missing,
    }
    return {
        "schema": SCHEMA, "project": "Meta-DGTF-道生三阶模型",
        "target": TARGET, "generated_at": m.get("generated_at", "unknown"),
        "archive": m.get("archive", ""), "total_versions": len(versions),
        "versions": versions, "eras": eras, "axes": axes,
        "readiness": readiness, "continuity_ok": not missing and readiness >= 0.99,
        "missing": missing, "provenance": provenance,
    }

def select_profile(question: str, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """按题面形状选择作业剖面；只影响 provenance，不生成答案。"""
    q = str(question or "")
    fact = bool(re.search(r"(是什么|何时|哪年|多少|谁|哪里|是否|？|\?)", q))
    decision = bool(re.search(r"(如何|应该|方案|决策|比较|取舍|建议|规划|风险)", q))
    high = bool(re.search(r"(安全|法律|医疗|金融|生产|不可逆|合规|事故)", q))
    if high or (fact and len(q) <= 80):
        return {"profile": "contract-first",
                "reason": "factual/high-stakes question -> 先过契约与证据门"}
    if decision:
        return {"profile": "contract-first",
                "reason": "decision-shaped question -> 先闭合 all/证据"}
    return {"profile": "exploration-first",
            "reason": "open/exploratory question -> 保留 0 层发散优先"}

def apply_history_fusion(cfg: Dict[str, Any], question: str = "") -> Dict[str, Any]:
    """写入 cfg['_history_fusion']；不修改答案相关配置。"""
    plan = build_plan()
    prof = select_profile(question, cfg)
    summary = {
        "enabled": True, "schema": SCHEMA, "target": TARGET,
        "project": plan["project"], "total_versions": plan["total_versions"],
        "readiness": plan["readiness"], "continuity_ok": plan["continuity_ok"],
        "missing": plan["missing"], "profile": prof["profile"],
        "profile_reason": prof["reason"],
        "axes_covered": len([a for a in plan["axes"] if a["covered"]]),
        "axes_total": len(plan["axes"]), "archive": plan["archive"],
        "generated_at": plan["generated_at"],
    }
    if isinstance(cfg, dict):
        cfg["_history_fusion"] = summary
    return summary

def audit_run(pack: Dict[str, Any], summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """运行时 provenance；只读 packed，不写答案。"""
    s = summary or {}
    route = [str(x) for x in (pack.get("route") or [])]
    views = pack.get("views") or {}
    present = [x for x in route if isinstance(views.get(x), dict)]
    covered = int(s.get("axes_covered") or 0)
    total = int(s.get("axes_total") or len(CAPABILITY_AXES))
    ok = bool(s.get("continuity_ok", False)) and covered == total
    return {
        "schema": SCHEMA, "target": s.get("target", TARGET),
        "project": s.get("project", "Meta-DGTF-道生三阶模型"),
        "total_versions": int(s.get("total_versions") or 0),
        "readiness": float(s.get("readiness") or 0.0),
        "continuity_ok": bool(ok), "profile": s.get("profile", ""),
        "profile_reason": s.get("profile_reason", ""),
        "axes_covered": covered, "axes_total": total, "route": route,
        "views_present": present, "archive": s.get("archive", ""),
        "generated_at": s.get("generated_at", ""),
    }

def render_markdown(plan: Optional[Dict[str, Any]] = None) -> str:
    p = plan or build_plan()
    lines = [
        "# Meta-DGTF-道生三阶模型 · 历史谱系融合计划", "",
        f"- 目标版本：V{p['target']}",
        f"- 历史版本：{p['total_versions']} 个",
        f"- 连续性 readiness：{p['readiness']:.2f}",
        f"- continuity_ok：{p['continuity_ok']}",
        f"- 归档：{p['archive']}", "", "## 时代", "",
        "| 时代 | 起点 | 能力 |", "|---|---|---|",
    ]
    for e in p.get("eras") or []:
        lines.append("| %s | %s | %s |" % (
            e.get("name", ""), e.get("start", ""),
            " / ".join(e.get("capabilities") or [])))
    lines += ["", "## 能力轴", "", "| 能力 | V1 来源 | V2 实现 | 状态 | 判据 |",
              "|---|---|---|---|---|"]
    for a in p.get("axes") or []:
        lines.append("| %s | %s | %s | %s | %s |" % (
            a.get("name", ""), a.get("v1_origin", ""),
            a.get("v2_implementation", ""), a.get("status", ""),
            a.get("tests", "")))
    lines += ["", "## 生成说明", "",
              "本计划由 dgtf_engine/dgtf_v2/history_fusion.py 从历史清单生成；",
              "只做 provenance 与连续性审计，不改写答案。"]
    return "\n".join(lines) + "\n"

def manifest_digest() -> str:
    p = manifest_path()
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else ""

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Meta-DGTF 历史谱系融合计划")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()
    plan = build_plan()
    if args.markdown:
        print(render_markdown(plan))
    else:
        out = {k: v for k, v in plan.items() if k not in ("versions", "axes", "eras")}
        out["manifest_digest"] = manifest_digest()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

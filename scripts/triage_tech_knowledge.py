# -*- coding: utf-8 -*-
"""DSH 技术知识分诊：给 agent_knowledge.jsonl 每条打 applicability/action/applied/triage。

守卫巡检每轮追加技术知识后应运行一次；随后至少选择一条 triage=actionable
做落地评估（能安全实现则实现并跑门禁），不能落地要写明原因。
"""
import sys, json, os, tempfile
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
root=Path(__file__).resolve().parent.parent
p=root/"dgtf_memory/agent_knowledge.jsonl"

def _search_fetch_landed():
    """确认官方 Search/Fetch 双端点已在实际引擎与配置中落地。"""
    try:
        engs = sorted((root / "dgtf_engine/dgtf_v2/engine").glob("Meta-DGTF-V*.py"),
                      key=lambda x: x.stat().st_mtime)
        txt = engs[-1].read_text(encoding="utf-8", errors="replace") if engs else ""
        cfg = (root / "dgtf_config.yaml").read_text(encoding="utf-8", errors="replace")
        bridge = (root / "dgtf_engine/dgtf_v2/agent_bridge.py").read_text(
            encoding="utf-8", errors="replace")
        return ("/v1/tools/search" in txt and "/v1/tools/fetch" in txt
                and (("backend: deepseek" in cfg) or ("backend: \"deepseek\"" in cfg))
                and "/v1/tools/search" in bridge and "/v1/tools/fetch" in bridge)
    except Exception:
        return False

_SF_LANDED = _search_fetch_landed()
rows=[]
for ln in p.read_text(encoding="utf-8",errors="replace").splitlines():
    if not ln.strip(): continue
    try: r=json.loads(ln)
    except Exception: continue
    t=(str(r.get("title") or "")+" "+str(r.get("query") or "")+" "+str(r.get("claim") or "")).lower()
    applies, action, applied, triage = "low", "", False, "observe"
    if "search / fetch" in t or "search/fetch" in t or "搜索" in t and "fetch" in t:
        applies="high"
        if _SF_LANDED:
            applied=True
            action="已落地：引擎/agent_bridge 双端点 /v1/tools/search + /v1/tools/fetch，dgtf_config.yaml backend=deepseek；保留离线失败分类与缓存"
            triage="already_applied"
        else:
            action="对比官方 Search/Fetch 与现有检索链路的成本、时延和证据格式，先离线兼容性验证"
            triage="actionable"
    elif "cadf" in t or "context-aware data fabric" in t or "context pruning" in t:
        applies="medium"; action="在上下文压缩处做 A/B，观察 token 降幅与答案质量"; triage="actionable"
    elif "pearl" in t or "learned orchestration" in t:
        applies="medium"; action="离线评估学习式 RAG 编排，不直接替换线上调度"; triage="evaluate"
    elif any(k in t for k in ("guardrails as scapegoats","rail guard","vepa","bounded autonomy","governed, self-evolving")):
        _guard_files = [
            "scripts/app_full_check.py",
            "scripts/outputs_library_audit.py",
            "scripts/propose_outputs_confirmations.py",
            "scripts/reassess_audit_proposals.py",
            "scripts/guard_policy_check.py",
        ]
        if all((root / x).is_file() for x in _guard_files):
            applies="high"
            applied=True
            action="已落地：App 全检查 + 产物库审计 + 人工确认提案 + 每轮复评 + 守护策略门禁"
            triage="already_applied"
        else:
            applies="medium"
            action="抽成 guard 审计指标或新增确定性检查，作为巡检自检项"
            triage="actionable"
    elif any(k in t for k in ("llm judge reliability","llm-as-a-judge","who grades the grader")):
        applies="high"; applied=True; action="已用于 V2.2.x 的 chance-corrected 一致性指标/确定性护栏"; triage="already_applied"
    elif "model-adaptive assessment" in t or "cost-efficient multi-agent rag" in t:
        applies="medium"; action="离线评估模型自适应评估，先看成本与判定一致性"; triage="evaluate"
    elif "deepseek-v4.1" in t or "deepseek v4.1" in t:
        applies="medium"; action="评估模型升级对质量/成本的影响，不在质量收口期切换"; triage="evaluate"
    elif "v4-flash-vision" in t or "vision" in t:
        applies="low"; action="仅图片附件场景评估，暂不接主链路"; triage="observe"
    elif any(k in t for k in ("self-evolving agent","multi-agent self-evolution","agent evolution","collaborative self-evolution","evomap","hiva","roleflow","knowledge intensive agents","multi-agent orchestrated rag","deepinfer","deepseek harness","deepseek harness")):
        applies="low"; action="作为架构/论文观察，不直接落地"; triage="observe"
    r["applicability"]=applies; r["action"]=action; r["applied"]=bool(applied); r["triage"]=triage
    rows.append(r)
# atomic
out=root/"dgtf_memory/agent_knowledge.jsonl"
fd,tmp=tempfile.mkstemp(prefix="agent_kn.",suffix=".tmp",dir=str(out.parent))
with os.fdopen(fd,"w",encoding="utf-8") as f:
    f.write("\n".join(json.dumps(r,ensure_ascii=False) for r in rows)+"\n")
os.replace(tmp,out)
from collections import Counter
print("triage",Counter(r.get("triage") for r in rows))
print("applicability",Counter(r.get("applicability") for r in rows))
for r in rows:
    if r.get("triage") in ("actionable","already_applied"):
        print(r.get("triage"),"|",str(r.get("title"))[:60],"|",r.get("action")[:80])

# 确定性知识门禁（RAIL/Guardrails 思路）：actionable 条目必须有落地动作。
_bad = [r for r in rows if r.get("triage") == "actionable" and not str(r.get("action") or "").strip()]
print("CHECK actionable_without_action=%d" % len(_bad))
if "--check" in sys.argv and _bad:
    for r in _bad:
        print("FAIL", str(r.get("title") or "")[:80])
    raise SystemExit(1)

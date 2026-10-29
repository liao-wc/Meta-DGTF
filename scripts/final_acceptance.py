# -*- coding: utf-8 -*-
"""最终验收串跑器（Round 73 起；2026-10-28 三态化 —— task-3）。

一条命令跑完所有零成本验收与护栏。**核心语义：「没跑」和「跑了判红」必须分开。**

三态（PASS / SKIP / FAIL）
--------------------------
- PASS：退出码 0，且（服务型/数据型步骤）没有显式的「SKIP」标记；
- SKIP：**没跑** —— 显式打印原因（前置服务未起 exit=2 / 输出 `SKIP:` 行 /
  `--skip-service` 显式跳过）。SKIP 在汇总里单列，默认**不算失败**，但绝不冒充绿；
- FAIL：跑了判红，或「没跑但当前模式要求必须跑」（`--with-service` 下的服务型步骤）。

历史缺陷（task-3 B）：e2e_app_local 的 exit=2 是「8772/8773 未起=没跑」，旧版当 FAIL
（假红）；而 judge_fastfail / generate_batch / graph_decode 在服务不可达时 exit 0 且
打印 `SKIP: 服务不可达`，旧版当 PASS（**假绿**）。现在两条都有明确归属。

用法：
  python scripts/final_acceptance.py                    # 不含本地服务检查（服务可能停机训练）
  python scripts/final_acceptance.py --with-service     # 含服务检查；服务缺失时服务型步骤判 FAIL
  python scripts/final_acceptance.py --skip-service     # 显式跳过依赖本地服务的步骤（记 SKIP，不执行；
                                                        # 用于 GPU 窗口/服务被其他任务独占时防误跑）
  python scripts/final_acceptance.py --require-all      # SKIP 也按失败处理（CI/有服务环境的严格模式）
  python scripts/final_acceptance.py --list-steps       # 只打印步骤清单与三态策略

退出码：0 = 没有 FAIL（默认 SKIP 不算失败）；1 = 有 FAIL 或 --require-all 下有 SKIP。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PASS, SKIP, FAIL = "PASS", "SKIP", "FAIL"

#: 步骤三态策略
#:   strict  —— 只认 exit 0 = PASS；其它一律 FAIL（默认；不吞任何「没跑」）
#:   service —— 依赖本地服务（8772/8773）：exit 0 且有 SKIP 标记 = SKIP；
#:              exit 2 = 服务未起/不可达（没跑）= SKIP；--with-service 时 SKIP 升级为 FAIL
#:   data    —— 依赖历史数据（packs 等）：exit 0 且有 SKIP 标记 = SKIP（与 mode 无关）
POLICY_STRICT = "strict"
POLICY_SERVICE = "service"
POLICY_DATA = "data"
_POLICY_LABEL = {POLICY_STRICT: "必须通过", POLICY_SERVICE: "依赖本地服务",
                 POLICY_DATA: "依赖历史数据"}

STEPS = [
    ("fast_gate", ["fast_gate.py"], POLICY_STRICT),
    ("v2_tests", ["scripts/run_v2_tests.py"], POLICY_STRICT),
    ("replay_guard", ["scripts/lead_offline_fact_replay.py"], POLICY_STRICT),
    ("process_gate_guard", ["scripts/lead_process_gate_audit.py"], POLICY_STRICT),
    ("app_plan_matrix", ["scripts/app_plan_matrix_check.py"], POLICY_STRICT),
    ("app_dual_judge_guard", ["scripts/app_dual_judge_guard_check.py"], POLICY_STRICT),
    ("compare_eval_selftest", ["scripts/local_model/test_compare_eval.py"], POLICY_STRICT),
    ("train_guard", ["scripts/local_model/test_train_guard.py"], POLICY_STRICT),
    ("app_cache_bypass", ["scripts/local_model/test_app_cache_bypass.py"], POLICY_STRICT),
    # ★ 依赖 8772：服务不可达时脚本 exit 0 + `SKIP: 服务不可达`（旧版被当 PASS = 假绿）。
    ("judge_fastfail", ["scripts/local_model/test_judge_fastfail.py"], POLICY_SERVICE),
    ("generate_batch", ["scripts/local_model/test_generate_batch.py"], POLICY_SERVICE),
    ("graph_decode", ["scripts/local_model/test_graph_decode.py"], POLICY_SERVICE),
    ("probe_cover_wide", ["scripts/local_model/test_probe_cover_wide.py"], POLICY_STRICT),
    ("ab_repeat_guard", ["scripts/local_model/test_ab_repeat_guard.py"], POLICY_STRICT),
    ("outputs_consistency", ["scripts/outputs_quality_consistency.py"], POLICY_STRICT),
    # 历史 packs 缺失时脚本自己 SKIP（没跑，不是假绿）
    ("fx_anchor_replay", ["scripts/fx_anchor_replay_check.py"], POLICY_DATA),
    ("scenario_matrix_guard", ["scripts/update_scenario_matrix.py"], POLICY_STRICT),
    # 零 API / 零 GPU / 不占端口：适配层协议判据（引擎 ↔ 本地服务互通）
    ("openai_shim", ["scripts/local_model/test_openai_shim.py"], POLICY_STRICT),
    # [V2.2.15] 本地服务 graph 采样/复用：零 GPU/零 HTTP（纯函数 + 源码结构 + 变异体自检）
    ("graph_sampling", ["scripts/local_model/test_graph_sampling.py"], POLICY_STRICT),
    # [V2.2.16] JSON 约束解码通道：零 GPU（纯函数 json_done/首token集合 + 三处接线 + 变异体）
    ("json_force", ["scripts/local_model/test_json_force.py"], POLICY_STRICT),
    # 显存碎片回收判据（纯函数 + 构造性验证；服务在线时只读 /metrics）
    ("mem_reclaim", ["scripts/local_model/test_mem_reclaim.py"], POLICY_STRICT),
    # 生成长度按 stage 压缩判据（纯函数 + 构造性证明打真 Handler）
    ("max_new_cap", ["scripts/local_model/test_max_new_cap.py"], POLICY_STRICT),
    # [V2.2.18] App selftest 自动门（自起临时 server；起不来 exit=2 = 没跑）
    ("app_selftest", ["scripts/app_selftest_gate.py"], POLICY_SERVICE),
    # [V2.2.22] 融合"更优"与动态最优配置：能力对等 + 实测矩阵对比 + 引擎 tick
    ("fused_optimal", ["scripts/local_model/test_fused_optimal.py"],
     POLICY_STRICT),
    # [V2.2.21] 融合后全链路真跑：App(auto→daosheng) → 引擎 → 本地模型 → 产物 → 读数
    ("fused_full_chain", ["scripts/local_model/test_fused_full_chain.py"],
     POLICY_SERVICE),
    # [V2.2.20] 道生支路接入统一模式体系（方案 A）：统一配置/rounds_locked/mode 透传
    ("daosheng_unified", ["scripts/local_model/test_daosheng_unified.py"],
     POLICY_STRICT),
    # [V2.2.19] 自动模式真跑：--mode auto 由题面选 fast / 专属配置落参 / 最优性可审计
    ("auto_mode_local", ["scripts/local_model/test_auto_mode_local.py"],
     POLICY_SERVICE),
    # ★ APP → 引擎 → 本地模型 端到端（零 API 成本；服务未起时退出码 2 = 没跑）
    ("e2e_app_local", ["scripts/local_model/e2e_app_local.py"], POLICY_SERVICE),
]

#: --with-service 时追加：服务在线性检查（服务不可达 ⇒ FAIL）
LOCAL_SERVICE_STEP = ("local_service", ["scripts/check_local_service.py"], POLICY_STRICT)

STEP_TIMEOUT = 1800
MAX_REASON = 160
SKIP_LINE_RE = re.compile(r"^\s*(?:·\s*)?SKIP\b")


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = (str(ROOT / "dgtf_engine") + os.pathsep + str(ROOT)
                         + os.pathsep + env.get("PYTHONPATH", ""))
    return env


def _last_line(out: str) -> str:
    for line in reversed((out or "").splitlines()):
        if line.strip():
            return line.strip()
    return ""


def _skip_line(out: str) -> str:
    """子进程自己打印的「没跑」标记（行首 SKIP / · SKIP）→ 原因；没有返回空串。"""
    for line in (out or "").splitlines():
        if SKIP_LINE_RE.match(line):
            return "[SKIP 标记] " + line.strip()[:MAX_REASON]
    return ""


def _no_run_reason(out: str) -> str:
    """exit=2 时从输出里挖出「为什么没跑」（e2e 打 ⚠ 行 / 含未起、不可达）。"""
    for line in (out or "").splitlines():
        s = line.strip()
        if s.startswith("⚠") or "未起" in s or "不可达" in s:
            return s[:MAX_REASON]
    return ""


def classify_step(rc: int, out: str = "", policy: str = POLICY_STRICT):
    """纯函数三段分类 → (PASS|SKIP|FAIL, reason)。不跑进程、不读环境（可被测试直打）。"""
    out = out or ""
    if rc == 0:
        if policy in (POLICY_SERVICE, POLICY_DATA):
            reason = _skip_line(out)
            if reason:
                return SKIP, reason
        return PASS, ""
    if rc == 2 and policy == POLICY_SERVICE:
        why = _no_run_reason(out)
        return SKIP, ("exit=2 前置服务未起/不可达（没跑）"
                      + (("：" + why) if why else ""))
    tail = _last_line(out)
    return FAIL, "exit=%d" % rc + (("：" + tail[:MAX_REASON]) if tail else "")


def apply_service_requirement(status: str, reason: str, policy: str,
                              with_service: bool):
    """--with-service 语义：服务型步骤的 SKIP 升级为 FAIL（服务缺失必须判红）。"""
    if status == SKIP and with_service and policy == POLICY_SERVICE:
        return FAIL, "--with-service 要求服务可用，但该步骤没跑：" + reason
    return status, reason


def build_steps(with_service: bool = False) -> list:
    steps = list(STEPS)
    if with_service:
        steps.append(LOCAL_SERVICE_STEP)
    return steps


def run_step(name: str, argv: list, policy: str, with_service: bool,
             skip_service: bool):
    """跑一个步骤 → (status, reason, 墙钟秒)。--skip-service 时服务型步骤不执行。"""
    if skip_service and policy == POLICY_SERVICE:
        return SKIP, "--skip-service 显式跳过（未执行）", 0.0
    t0 = time.time()
    try:
        r = subprocess.run(
            [sys.executable] + [str(ROOT / a) for a in argv],
            cwd=str(ROOT), env=_env(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=STEP_TIMEOUT)
    except subprocess.TimeoutExpired:
        return FAIL, "timeout %ds" % STEP_TIMEOUT, round(time.time() - t0, 1)
    except OSError as exc:  # 脚本不存在 / 无法启动：不是「没跑」，是配置坏
        return (FAIL, "%s: %s" % (type(exc).__name__, exc),
                round(time.time() - t0, 1))
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    status, reason = classify_step(r.returncode, out, policy)
    status, reason = apply_service_requirement(status, reason, policy, with_service)
    return status, reason, round(time.time() - t0, 1)


def _write_evidence(results, args, npass: int, nskip: int, nfail: int) -> None:
    """把本次验收结果写 docs/acceptance_latest.json（失败不阻断验收）。

    ★ DGTF_ACCEPTANCE_NO_EVIDENCE=1 时不写：tests_acceptance_semantics 会用打补丁的
      STEPS 直接调 main() 做三态判据，若允许写证据会把生产 evidence 覆盖成
      「PASS 2」的假读数（本轮真实事故：pre-commit 钩子跑 fast_gate → 语义测试 →
      docs/acceptance_latest.json 被污染成 PASS 2，发布流程门当场判红）。
    """
    if os.environ.get("DGTF_ACCEPTANCE_NO_EVIDENCE") == "1":
        return
    try:
        now = time.time()
        ev = {
            "schema": "dgtf.acceptance.v1",
            "ts": now,
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
            "with_service": bool(getattr(args, "with_service", False)),
            "skip_service": bool(getattr(args, "skip_service", False)),
            "require_all": bool(getattr(args, "require_all", False)),
            "passed": int(npass),
            "skipped": int(nskip),
            "failed": int(nfail),
            "steps": [{"name": n, "status": s, "sec": c, "reason": r}
                      for n, s, c, r in results],
            "ok": bool(nfail == 0 and not (
                getattr(args, "require_all", False) and nskip)),
        }
        p = ROOT / "docs" / "acceptance_latest.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ev, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _print_steps(steps: list) -> None:
    for i, (name, argv, policy) in enumerate(steps, 1):
        print("%2d  %-24s %-8s %-6s  %s"
              % (i, name, policy, _POLICY_LABEL[policy], " ".join(argv)))


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="最终验收串跑器（三态：PASS / SKIP / FAIL）")
    ap.add_argument("--with-service", action="store_true",
                    help="含本地服务检查；服务缺失时服务型步骤判 FAIL")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--skip-service", action="store_true",
                      help="显式跳过依赖本地服务的步骤（记 SKIP、不执行；防 GPU 误跑）")
    mode.add_argument("--require-all", action="store_true",
                      help="SKIP 也按失败处理（严格模式）")
    ap.add_argument("--list-steps", action="store_true",
                    help="只打印步骤清单与三态策略，不执行")
    args = ap.parse_args(argv)

    steps = build_steps(args.with_service)
    if args.list_steps:
        print("STEPS %d（--with-service 时 %d）"
              % (len(steps), len(build_steps(True))))
        _print_steps(steps)
        return 0

    results = []
    for name, step_argv, policy in steps:
        status, reason, cost = run_step(name, step_argv, policy,
                                        args.with_service, args.skip_service)
        results.append((name, status, cost, reason))
        print("%-4s  %-24s %6.1fs  %s" % (status, name, cost, reason))

    npass = sum(1 for _, st, _, _ in results if st == PASS)
    nskip = sum(1 for _, st, _, _ in results if st == SKIP)
    nfail = sum(1 for _, st, _, _ in results if st == FAIL)
    # ★ [V2.2.18] 证据出口：release_process_check 用它校验「验收新鲜度 + 三态计数」，
    #   同时让 README 的「一键验收 PASS/SKIP/FAIL」数字可被机器核对（防文档漂移）。
    _write_evidence(results, args, npass, nskip, nfail)
    print("\nFINAL ACCEPTANCE: PASS %d / SKIP %d / FAIL %d  (%d steps)"
          % (npass, nskip, nfail, len(results)))
    if nskip:
        print("SKIPPED（没跑，默认不算失败；原因见下）:")
        for name, st, _, reason in results:
            if st == SKIP:
                print("  - %-24s %s" % (name, reason))
    skipped = [name for name, st, _, _ in results if st == SKIP]
    failed = [name for name, st, _, _ in results if st == FAIL]
    if failed:
        print("FAILED:", failed)
        return 1
    if args.require_all and skipped:
        print("STRICT FAIL（--require-all）: %d 个 SKIP = %s" % (len(skipped), skipped))
        return 1
    if skipped:
        print("ALL GUARDS PASS（含 %d 个 SKIP 单列；--require-all 可把 SKIP 当失败）"
              % len(skipped))
    else:
        print("ALL GUARDS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

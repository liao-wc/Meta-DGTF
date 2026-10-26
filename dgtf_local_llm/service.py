# -*- coding: utf-8 -*-
"""Meta-DGTF-道生三阶模型 · 本地推理服务（HTTP 127.0.0.1:8772）。

定位
----
engine / app 通过本服务调用本地 Qwen2.5-1.5B-Instruct + 4 个 stage LoRA 适配器：
  stage ∈ {self_check, self_check_min, dual_judge, route}
本服务只做「本地草稿 / QC 建议」，不做真实 API 调用，不外联。

接口契约（与 Lead 约定）
------------------------
GET  /health
  200 {"ok":true,"status":"ready|loading|error","model":...,
       "adapters":{"self_check":bool,...},"gpu_mem_mb":int,
       "queue_depth":int,"uptime_sec":float,"warmup_ms":float|null}
  永远秒回（模型在后台线程加载，不阻塞 health）。

POST /generate
  body {
    "stage": "self_check|self_check_min|dual_judge|route",
    "text": "..."  或  "messages":[{"role","content"},...],   # 二选一
    "entry": "0|1|both|all",        # 可选，self_check/dual_judge 用，默认 "1"
    "variant": "full|min",          # 可选，self_check 用，默认 full
    "max_new_tokens": int,          # 可选，按 stage 默认
    "temperature": float,           # 0=贪心
    "timeout": float                # 秒，默认 60，最大 120
  }
  200 {"ok":true,"stage":...,"text":生成的原文,"json":解析后的 JSON|null,
       "ms":float,"adapter":...,"confidence":float|null,
       "gpu_mem_mb":int,"cached":bool,"queue_ms":float}
  503 {"ok":false,"error":{"code":"TIMEOUT|UNAVAILABLE|BAD_REQUEST|INTERNAL",
                           "message":...}}
  400 参数错误（同样结构化）。

GPU 独占：所有生成走单 worker 串行队列；请求在队列里按 timeout 截止。

生成策略（针对本机 1660 Ti 的实测优化）
--------------------------------------
SM75 无 tensor core，cuBLAS 12.6 的 fp16 HGEMM 仅 0.54 TFLOPS，而 fp32 GEMM
有 2.47 TFLOPS。因此：
  · prefill 阶段用 fp32 GEMM（`_set_fp32(True)`，输出仍 fp16）→ 469 tok/s
  · decode  阶段用纯 fp16（M=1 是带宽瓶颈，fp32-cast 反而只有 2.5 tok/s）
    → 10.4 tok/s
手写 prefill + KV-cache 逐 token 解码，中途切换模式，比 HuggingFace
`generate()` 直接跑（fp16 prefill 167 tok/s）快 2-3 倍。

用法：
  python dgtf_local_llm/service.py --port 8772
  （推荐）powershell -File scripts/local_model/start_local_llm.ps1
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import os
import queue
import re
import sys
import threading
import time
import traceback
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "local_model"))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402
from peft import PeftModel  # noqa: E402
from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: E402

import build_dgtf_stage_dataset as bds  # noqa: E402

# 底座：Qwen2.5-0.5B-Instruct。
# ★ 为什么不是 1.5B：GTX 1660 Ti 持续训练会降频（1845→1530MHz），1.5B 在
#   6GB 卡上 sustained fwd+bwd 只有 ~56 tok/s，时间盒内跑不出可用适配器；
#   0.5B 底座在同等时间下能多训 3-4 倍数据，且**推理快 2-3 倍**
#   （self_check_min 单次 ~1-2s，1.5B 是 ~6s）。1.5B 版本适配器路径保留在
#   llm_sft/adapter_dgtf_*_15b_v1（实验性，未纳入默认服务）。
DEFAULT_MODEL = ROOT / "local_model" / "models" / "Qwen2.5-0.5B-Instruct"
STAGES = ("self_check", "self_check_min", "dual_judge", "route")
# stage -> 适配器目录（self_check 与 self_check_min 共用同一个混训适配器）
# 每个 stage 的适配器候选（按优先级）：重训版 _v2 优先，第一轮 _v1 兜底
ADAPTER_CANDIDATES = {
    # ★ [Round 123] v9b（0.5B base 纠错后，min 230×2，lr6e-5，seed7）：
    #   val_loss 0.1989（优于 v6 0.2221 与 v8b 0.9895）；30 条 held-out 质量与 v8b 完全持平，
    #   p50 4774ms / p95 5690ms（比 v8b 5858/6340 更快）⇒ 默认 v9b，v8b 兜底。
    # ★ [Round 79] v8b（mixed 配方，168 样本×2 epochs）30 条 held-out 与 v6 质量持平
    #   （字段 0.589、escape 0.800、suspF1 -0.012 噪声内），p50/p95 更快（5858/6340 vs 6271/7474）
    #   ⇒ 默认 v8b，v6 兜底（val_loss 0.9895 较高，保留回退）。
    # ★ [Round 38] v6（230×2 epochs/lr8e-5）30 条 held-out：字段 0.589 vs 0.378、
    #   escape 0.800 vs 0.200、all3 0.033 vs 0.0、p50 6.27 vs 6.73s（suspF1 -0.012 噪声内）
    #   ⇒ 默认 v6，v5 兜底。
    # ★ [Round 21] v5（240 样本/len1900/fp32）在 30 条 held-out 上质量全面 ≥ v2：
    #   JSON 1.000 vs 0.967、字段 0.378 vs 0.367、suspF1 0.165 vs 0.161、
    #   ing 0.933 vs 0.900、escape 持平 0.200；p50 6.73s vs 6.02s（可接受）。
    #   默认 v5，v2 兜底；DGTF_LOCAL_ADAPTER 可覆盖。
    "self_check": ["llm_sft/adapter_dgtf_selfcheck_05b_v9b",
                   "llm_sft/adapter_dgtf_selfcheck_05b_v8b",
                   "llm_sft/adapter_dgtf_selfcheck_05b_v6",
                   "llm_sft/adapter_dgtf_selfcheck_05b_v5",
                   "llm_sft/adapter_dgtf_selfcheck_05b_v2",
                   "llm_sft/adapter_dgtf_selfcheck_05b_v1"],
    "self_check_min": ["llm_sft/adapter_dgtf_selfcheck_05b_v9b",
                       "llm_sft/adapter_dgtf_selfcheck_05b_v8b",
                       "llm_sft/adapter_dgtf_selfcheck_05b_v6",
                       "llm_sft/adapter_dgtf_selfcheck_05b_v5",
                       "llm_sft/adapter_dgtf_selfcheck_05b_v2",
                       "llm_sft/adapter_dgtf_selfcheck_05b_v1"],
    "dual_judge": ["llm_sft/adapter_dgtf_judge_05b_v2",
                   "llm_sft/adapter_dgtf_judge_05b_v1"],
    "route": ["llm_sft/adapter_qwen05b_v1"],
}
# 兼容旧引用（文档/评测只读展示用）；实际加载走 resolve_adapter()
ADAPTER_DIRS = {k: v[0] for k, v in ADAPTER_CANDIDATES.items()}


def _env_adapter_overrides() -> list[str]:
    """DGTF_LOCAL_ADAPTER：逗号分隔的适配器相对路径，优先级最高（默认空=不改行为）。

    用途：A/B 实验或灰度切换适配器（例如 v5）时无需改代码；
    默认仍走 ADAPTER_CANDIDATES（v2 优先），保证线上行为不变。
    """
    raw = str(os.environ.get("DGTF_LOCAL_ADAPTER") or "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()]


def resolve_adapter(stage: str, root: Path | None = None):
    """返回 (rel_path, abs_path)；不存在返回 (None, None)。"""
    base = root or ROOT
    for rel in _env_adapter_overrides() + list(ADAPTER_CANDIDATES.get(stage, [])):
        p = base / rel
        if (p / "adapter_config.json").exists():
            return rel, p
    return None, None
DEFAULT_MAX_NEW = {"self_check": 64, "self_check_min": 64,
                   "dual_judge": 224, "route": 96}
ROUTE_SYSTEM = (
    "你是元DGTF的调度规划器。阅读用户问题，输出严格 JSON："
    '{"route": ["0","1","both","all"] 的子集, '
    '"rounds": {"0":int,"1":int,"both":int,"all":int}, '
    '"why": "不超过20字的理由"}。route 只放需要的层；rounds 给每层圈数（1-8）；'
    "不要输出 JSON 以外内容。"
)



def salvage_stage_json(stage: str, text: str):
    """模型输出被截断/带杂音时，抢救出 stage 关键字段（尽力而为，不假装完整）。

    典型失败模式（实测）：self_check_min 输出
    {"suspicious_candidates":[10,11,12,... 一路喷到 token 上限，缺右括号。
    这里用正则把三个决策字段抠出来，保证调用方拿到**结构化**结果，
    同时返回 salvaged=True 让调用方知道这是抢救值。
    """
    if not text:
        return None
    if stage in ("self_check", "self_check_min"):
        m = re.search(r'"suspicious_candidates"\s*:\s*\[([^\]]*)', text)
        ing = re.search(r'"ing_rephrased"\s*:\s*(true|false)', text)
        esc = re.search(r'"unsaid_is_escape"\s*:\s*(true|false)', text)
        if not (m or ing or esc):
            return None
        cands = []
        if m:
            for x in re.findall(r"\d+", m.group(1))[:50]:
                try:
                    cands.append(int(x))
                except ValueError:
                    pass
        return {"suspicious_candidates": sorted(set(cands)),
                "ing_rephrased": bool(ing and ing.group(1) == "true"),
                "unsaid_is_escape": bool(esc and esc.group(1) == "true")}
    if stage == "dual_judge":
        js = []
        for m in re.finditer(
                r'"idx"\s*:\s*(\d+)[^{}]*?"position"\s*:\s*"?(0|1|both)', text):
            js.append({"idx": int(m.group(1)),
                       "position": m.group(2), "why_position": ""})
        if js:
            return {"judgments": js}
    return None
def jdump(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False).encode("utf-8")


def try_parse_json(text: str):
    """从生成文本里抠出第一个 JSON 对象（模型偶尔带解释/代码块）。"""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    for cand in (t, t[t.find("{"): t.rfind("}") + 1] if "{" in t and "}" in t
                 else ""):
        if not cand:
            continue
        try:
            return json.loads(cand)
        except Exception:
            continue
    return None


# ============================================================
# 模型 + 生成
# ============================================================
class LocalEngine:
    def __init__(self, args, autostart: bool = True):
        self.args = args
        self.model_path = str(args.model)
        self.tpl = None
        self.tok = None
        self.model = None
        self.patches: list = []
        self.adapter_names: dict[str, str] = {}
        self.adapter_paths: dict[str, str] = {}
        self.state = "loading"
        self.error = ""
        self.warmup_ms = None
        self.load_sec = None
        self.started_at = time.time()
        self.q: queue.Queue = queue.Queue()
        self.queue_depth = 0
        self.cache: OrderedDict = OrderedDict()
        self.cache_max = 200
        self._lock = threading.Lock()
        # ★ [Round 25] 可观测性统计（App/引擎动态调度用；线程安全）
        self._stats_lock = threading.Lock()
        self.stats = {"requests_total": 0, "by_stage": {}, "errors": 0,
                      "total_ms": 0.0, "max_ms": 0.0, "busy_now": False,
                  "dual_judge_fastfail": 0,
                      "last_ms": 0.0, "last_stage": "", "last_adapter": ""}
        # ★ [Round 65] 延迟分位数滑动窗口（最近 50 次真实生成耗时）
        import collections as _collections
        self._lat_window = _collections.deque(maxlen=50)
        if autostart:
            threading.Thread(target=self._load, daemon=True).start()
            threading.Thread(target=self._worker, daemon=True).start()

    # ---------- fp32 GEMM patch（prefill 用） ----------
    def _patch(self) -> None:
        def _fwd(self, x, *args, **kwargs):
            w = self.weight
            b = self.bias
            with torch.amp.autocast("cuda", enabled=False):
                y = F.linear(x.float(), w.float(),
                             b.float() if b is not None else None)
            return y.to(w.dtype)

        seen = set()
        for name, m in self.model.named_modules():
            if not isinstance(m, nn.Linear) or name.endswith("lm_head"):
                continue
            if id(m) in seen:  # named_modules 可能重复给出同一 module
                continue
            seen.add(id(m))
            self.patches.append((m, m.forward, functools.partial(_fwd, m)))

    def _set_fp32(self, on: bool) -> None:
        for m, orig, fast in self.patches:
            m.forward = fast if on else orig

    # ---------- 加载 ----------
    def _load(self) -> None:
        t0 = time.time()
        try:
            self.tpl = bds.load_engine_templates()
            self.tok = AutoTokenizer.from_pretrained(
                self.model_path, trust_remote_code=True,
                local_files_only=True)
            if self.tok.pad_token is None:
                self.tok.pad_token = self.tok.eos_token
            base = AutoModelForCausalLM.from_pretrained(
                self.model_path, dtype=torch.float16, trust_remote_code=True,
                local_files_only=True, attn_implementation="sdpa")
            base.to("cuda")
            base.eval()
            base.config.use_cache = True
            # 先挂第一个可用适配器，其余 load_adapter
            resolved = {}
            for stage in STAGES:
                rel, p = resolve_adapter(stage)
                if p is not None:
                    resolved[stage] = (rel, p)
            self.adapter_paths = {st: r for st, (r, _) in resolved.items()}
            first = None
            for stage, (rel, p) in resolved.items():
                first = (stage, p)
                break
            if first is not None:
                self.model = PeftModel.from_pretrained(
                    base, str(first[1]), adapter_name=first[0])
                self.adapter_names[first[0]] = first[0]
                by_path = {str(first[1]): first[0]}
                for stage, (rel, p) in resolved.items():
                    if stage in self.adapter_names:
                        continue
                    key = str(p)
                    try:
                        if key in by_path:
                            self.adapter_names[stage] = by_path[key]
                            continue
                        self.model.load_adapter(key, adapter_name=stage)
                        self.adapter_names[stage] = stage
                        by_path[key] = stage
                    except Exception as e:
                        print(f"[load] adapter {stage} 失败: {e}", flush=True)
            else:
                self.model = base
            self.model.eval()
            self._patch()
            self._set_fp32(True)
            self.load_sec = round(time.time() - t0, 1)
            # warmup：短 prefill + 4 token decode
            tw = time.time()
            ids = self.tok("【锚点】\n预热", return_tensors="pt")
            self.generate("route", ids["input_ids"], max_new_tokens=4,
                          temperature=0.0, deadline=time.time() + 120,
                          do_warmup=True)
            self.warmup_ms = round((time.time() - tw) * 1000, 1)
            self.state = "ready"
            print(f"[load] ready in {self.load_sec}s warmup={self.warmup_ms}ms "
                  f"adapters={list(self.adapter_names)}", flush=True)
        except Exception as e:
            self.state = "error"
            self.error = f"{type(e).__name__}: {e}"
            traceback.print_exc()
            print(f"[load] FAILED: {self.error}", flush=True)

    def stat_begin(self, stage: str) -> None:
        with self._stats_lock:
            self.stats["busy_now"] = True
            self.stats["last_stage"] = str(stage or "")

    def stat_end(self, stage: str, t0: float, adapter: str = "",
                 ok: bool = True) -> None:
        import time as _time
        ms = (_time.perf_counter() - t0) * 1000.0
        with self._stats_lock:
            self.stats["requests_total"] += 1
            self.stats["by_stage"][str(stage or "")] = int(
                self.stats["by_stage"].get(str(stage or ""), 0)) + 1
            if not ok:
                self.stats["errors"] += 1
            self.stats["total_ms"] = float(self.stats["total_ms"]) + ms
            self.stats["max_ms"] = max(float(self.stats["max_ms"]), ms)
            self.stats["last_ms"] = ms
            self.stats["last_adapter"] = str(adapter or "")
            self.stats["busy_now"] = False
            self._lat_window.append(ms)

    # ---------- 生成（prefill fp32 GEMM + decode fp16） ----------
    @torch.inference_mode()
    def generate(self, stage: str, input_ids, max_new_tokens: int,
                 temperature: float, deadline: float,
                 do_warmup: bool = False, use_adapter: bool = True) -> dict:
        ids = input_ids.to("cuda")
        L = ids.shape[1]
        attn = torch.ones((1, L), dtype=torch.long, device="cuda")
        if use_adapter and self.adapter_names and stage in self.adapter_names:
            self.model.set_adapter(self.adapter_names[stage])
        self._set_fp32(True)
        outs = self.model(input_ids=ids, attention_mask=attn,
                          use_cache=True)
        past = outs.past_key_values
        logits = outs.logits[:, -1, :].float()
        self._set_fp32(False)
        generated: list[int] = []
        logprobs: list[float] = []
        eos = self.tok.eos_token_id
        try:
            for step in range(max_new_tokens):
                if time.time() > deadline:
                    raise TimeoutError("生成超时")
                if temperature and temperature > 0:
                    probs = torch.softmax(logits / temperature, dim=-1)
                    nxt = torch.multinomial(probs, 1)
                else:
                    nxt = logits.argmax(-1, keepdim=True)
                lp = torch.log_softmax(logits, dim=-1)[0, int(nxt[0, 0])]
                logprobs.append(float(lp))
                generated.append(int(nxt[0, 0]))
                if eos is not None and int(nxt[0, 0]) == eos:
                    break
                if step + 1 >= max_new_tokens:
                    break
                attn = torch.cat(
                    [attn, torch.ones((1, 1), dtype=torch.long,
                                      device="cuda")], dim=1)
                o = self.model(input_ids=nxt, attention_mask=attn,
                               past_key_values=past, use_cache=True)
                past = o.past_key_values
                logits = o.logits[:, -1, :].float()
        finally:
            self._set_fp32(True)
        text = self.tok.decode(generated, skip_special_tokens=True)
        conf = None
        if logprobs:
            conf = round(float(torch.tensor(logprobs).mean().exp()), 4)
        del past, outs, logits, attn, ids
        return {"text": text, "confidence": conf,
                "gen_tokens": len(generated),
                "prompt_tokens": int(L)}

    # ---------- prompt 拼装 ----------
    def _stage_system(self, stage: str, entry: str, variant: str) -> str:
        phase = self.tpl["phases"][entry]
        if stage in ("self_check", "self_check_min"):
            v = "min" if stage == "self_check_min" else variant
            return bds.self_check_system(phase, v)
        if stage == "dual_judge":
            return bds.dual_judge_system(phase, self.tpl["no_fill"])
        return ROUTE_SYSTEM

    def _self_check_user(self, view: dict, variant: str) -> str:
        """按引擎 _self_check user 模板拼装（截断上限与数据集构建一致）。"""
        a = bds
        cands = [c for c in (view.get("candidates") or [])
                 if isinstance(c, dict)]
        amps = [c for c in (view.get("amps") or []) if isinstance(c, dict)]
        cand_lines = "\n".join(
            f"{i + 1}. [{c.get('attribute', '0')}×{c.get('position', '0')}] "
            f"{a._clip(a._norm_desc(c.get('desc')), a.SC_CAND_DESC_CAP)}"
            for i, c in enumerate(cands[:a.SC_CAND_MAX]))
        amp_lines = "\n".join(
            f"{i + 1}. [{c.get('type', '?')}] "
            f"{a._clip(a._norm_desc(c.get('desc')), a.SC_AMP_DESC_CAP)}"
            for i, c in enumerate(amps[:a.SC_AMP_MAX]))
        flags = [str(f) for f in (view.get("quality_flags") or [])][
            :a.SC_FLAGS_MAX]
        user = (
            f"【锚点】\n{a._clip(view.get('anchor') or '', a.SC_ANCHOR_CAP)}\n\n"
            f"【候选】\n{cand_lines or '（无）'}\n\n"
            f"【& 印记】\n{amp_lines or '（无）'}\n\n"
            f"【ing 输出】\n"
            f"{a._clip(view.get('collision') or '', a.SC_COLLISION_CAP)}\n\n"
            f"【view】\n"
            f"{a._clip(view.get('manifest') or '（未生）', a.SC_MANIFEST_CAP)}\n\n"
            f"【代码已发现的质量线索】\n{', '.join(flags) or '（无）'}\n")
        if any("too_many_amp_candidates" in f for f in flags):
            user += ("\n\n【★ 深究请求】本轮 amp 候选占比偏高。请专门判断：\n"
                     "  这是结构性一致（& 候选从不同角度指向同一结构），\n"
                     "  还是判断塌缩（属性与位置机械全反）？\n"
                     "  把结论写进 amp_ratio_verdict（≤40字）。\n")
        counted, where = a._count_unsaid(view)
        lim = int(self.tpl["unsaid_limit"])
        if counted:
            user += (f"\n\n【★ 代码统计】本圈产物里出现「{a._UNSAID_MARK}」"
                     f"{counted} 处，分布在：{where or '（未定位）'}。\n"
                     f"  你自己数的 unsaid_count 应与此接近；差太多请说明。\n")
            if lim > 0:
                user += (f"  超过 {lim} 处 → 这一圈的探针没真的往里推，"
                         f"unsaid_is_escape 填 true。\n")
        return user

    def _dual_judge_user(self, req: dict, entry: str) -> str:
        a = bds
        anchor = str(req.get("anchor") or req.get("text") or "")
        question = str(req.get("question") or "")
        if entry in ("0", "1"):
            ctx = (f"{a._clip(anchor, a.DJ_ANCHOR_CAP)}\n\n【原始问题】\n"
                   f"{a._clip(question, a.DJ_QUESTION_CAP)}")
        else:
            ctx = f"【问题（透传）】\n{a._clip(anchor, a.DJ_ANCHOR_CAP)}"
        dec = a._decidability_block(req.get("decidability") or {})
        raw = req.get("candidates") or []
        lines = []
        for i, c in enumerate(raw[:32]):
            if isinstance(c, str):
                lines.append(f"{i + 1}. [concept] {a._clip(c, a.DJ_DESC_CAP)}")
            else:
                lines.append(
                    f"{i + 1}. [{c.get('kind') or 'concept'}] "
                    f"{a._clip(a._norm_desc(c.get('desc')), a.DJ_DESC_CAP)}")
        return (f"【处境】\n{ctx}\n{dec}\n\n【候选列表】\n"
                + "\n".join(lines))

    def build_messages(self, req: dict) -> list[dict]:
        stage = req["stage"]
        entry = str(req.get("entry") or "1")
        if entry not in bds._ENTRIES:
            entry = "1"
        # ★ stage=self_check 默认走 min schema（3 个决策字段），保证 engine
        #   60s 超时内返回；要 11 字段全量请显式传 variant="full"。
        variant = str(req.get("variant") or
                      ("min" if stage == "self_check" else "full"))
        if req.get("messages"):
            msgs = [m for m in req["messages"] if isinstance(m, dict)]
            # ★ 默认由服务提供 stage system prompt（本地适配器只认自己训练过的
            #   模板）；调用方传进来的 user/assistant 内容保留。若确实要原样
            #   透传（含自己的 system），传 "preserve_system": true。
            if req.get("preserve_system"):
                out = list(msgs)
                if not out or out[0].get("role") != "system":
                    out = [{"role": "system",
                            "content": self._stage_system(stage, entry,
                                                          variant)}] + out
                return out
            keep = [m for m in msgs if m.get("role") != "system"]
            return [{"role": "system",
                     "content": self._stage_system(stage, entry, variant)}] \
                + keep
        text = str(req.get("text") or "")
        sysm = self._stage_system(stage, entry, variant)
        if stage in ("self_check", "self_check_min"):
            obj = None
            if text.strip().startswith("{"):
                obj = try_parse_json(text)
            if isinstance(obj, dict) and ("anchor" in obj
                                          or "candidates" in obj):
                user = self._self_check_user(obj, variant)
            else:
                user = text
        elif stage == "dual_judge":
            obj = try_parse_json(text) if text.strip().startswith("{") else None
            user = (self._dual_judge_user({**obj, "text": text}, entry)
                    if isinstance(obj, dict) and
                    ("candidates" in obj or "anchor" in obj) else text)
        else:
            user = text
        return [{"role": "system", "content": sysm},
                {"role": "user", "content": user}]

    # ---------- 单卡串行队列 ----------
    def submit(self, req: dict, timeout: float) -> dict:
        job = {"req": req, "ev": threading.Event(), "result": None,
               "err": None, "done_at": None, "queued_at": time.time()}
        with self._lock:
            self.queue_depth += 1
        self.q.put(job)
        got = job["ev"].wait(timeout)
        if not got:
            raise TimeoutError("排队/生成超时")
        if job["err"]:
            raise job["err"]
        res = job["result"] or {}
        res["queue_ms"] = round((job["dequeued_at"] - job["queued_at"]) * 1000, 1)
        return res

    def _worker(self) -> None:
        while True:
            job = self.q.get()
            with self._lock:
                self.queue_depth = max(0, self.queue_depth - 1)
            job["dequeued_at"] = time.time()
            try:
                job["result"] = self._handle(job["req"])
            except Exception as e:
                job["err"] = e
            finally:
                job["ev"].set()

    def _handle(self, req: dict) -> dict:
        t0 = time.time()
        stage = req["stage"]
        timeout = float(req.get("timeout") or 60)
        max_new = int(req.get("max_new_tokens") or DEFAULT_MAX_NEW[stage])
        max_new = max(1, min(1024, max_new))
        temp = req.get("temperature", 0.0)
        try:
            temp = float(temp)
        except (TypeError, ValueError):
            temp = 0.0
        # ---------- LRU 缓存（重复请求 0 GPU 开销） ----------
        try:
            key = hashlib.md5(json.dumps(
                {k: req.get(k) for k in (
                    "stage", "entry", "variant", "max_new_tokens",
                    "temperature", "text", "messages")},
                sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        except Exception:
            key = None
        if key and key in self.cache:
            self.cache.move_to_end(key)
            res = dict(self.cache[key])
            res["cached"] = True
            res["ms"] = round((time.time() - t0) * 1000, 1)
            res["gpu_mem_mb"] = self.gpu_mem_mb()
            return res
        msgs = self.build_messages(req)
        prompt = self.tok.apply_chat_template(msgs, tokenize=False,
                                             add_generation_prompt=True)
        ids = self.tok(prompt, return_tensors="pt",
                       truncation=True, max_length=2048)["input_ids"]
        deadline = time.time() + timeout
        out = self.generate(stage, ids, max_new, temp, deadline)
        text = out["text"]
        parsed = try_parse_json(text)
        salvaged = False
        if parsed is None:
            parsed = salvage_stage_json(stage, text)
            salvaged = parsed is not None
        res = {"ok": True, "stage": stage, "salvaged": salvaged,
               "text": text, "json": parsed,
               "ms": round((time.time() - t0) * 1000, 1),
               "adapter": self.adapter_paths.get(stage),
               "confidence": out["confidence"],
               "gen_tokens": out["gen_tokens"],
               "prompt_tokens": out["prompt_tokens"],
               "gpu_mem_mb": self.gpu_mem_mb(),
               "cached": False}
        if key:
            self.cache[key] = dict(res)
            while len(self.cache) > self.cache_max:
                self.cache.popitem(last=False)
        return res

    def gpu_mem_mb(self) -> int:
        try:
            return int(torch.cuda.memory_allocated() / 1024 / 1024)
        except Exception:
            return -1

    def health(self) -> dict:
        return {"ok": self.state == "ready", "status": self.state,
                "model": self.model_path,
                "adapter": (list(self.adapter_names)
                            if self.adapter_names else []),
                "adapters": {s: (s in self.adapter_names) for s in STAGES},
                "adapter_paths": self.adapter_paths,
                "gpu_mem_mb": self.gpu_mem_mb(),
                "queue_depth": self.queue_depth,
                "uptime_sec": round(time.time() - self.started_at, 1),
                "load_sec": self.load_sec,
                "warmup_ms": self.warmup_ms,
                "error": self.error or None}


# ============================================================
# HTTP
# ============================================================
class Handler(BaseHTTPRequestHandler):
    engine: LocalEngine = None  # type: ignore
    server_version = "dgtf-local-llm/1.0"

    def log_message(self, fmt, *args):  # 安静一点
        print(f"[http] {self.address_string()} {fmt % args}", flush=True)

    def _send(self, code: int, body: dict) -> None:
        data = jdump(body)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.split("?")[0] == "/metrics":
            h = self.engine.health()
            st = dict(getattr(self.engine, "stats", {}) or {})
            n = max(1, int(st.get("requests_total") or 0))
            _lat = sorted(getattr(self.engine, "_lat_window", []) or [])
            def _pct(q: float) -> float:
                if not _lat:
                    return 0.0
                _i = min(len(_lat) - 1, int(round((len(_lat) - 1) * q)))
                return round(_lat[_i], 1)
            payload = {
                "ok": True,
                "state": h.get("status") or h.get("state") or "ready",
                "model": h.get("model"),
                "adapter_paths": h.get("adapter_paths"),
                "stats": st,
                "avg_ms": round(float(st.get("total_ms") or 0) / n, 1),
                "latency": {"n": len(_lat), "p50": _pct(0.50),
                            "p95": _pct(0.95),
                            "mean": round(sum(_lat) / len(_lat), 1)
                            if _lat else 0.0},
            }
            self._send(200, payload)
            return
        if self.path.split("?")[0] in ("/health", "/healthz", "/"):
            self._send(200, self.engine.health())
        elif self.path.split("?")[0] == "/":
            self._send(200, {"ok": True, "service": "dgtf_local_llm",
                             "endpoints": ["/health", "/generate", "/metrics"]})
        else:
            self._send(404, {"ok": False, "error": {"code": "NOT_FOUND",
                                                    "message": self.path}})

    def do_POST(self):
        if self.path.split("?")[0] != "/generate":
            self._send(404, {"ok": False, "error": {"code": "NOT_FOUND",
                                                    "message": self.path}})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            req = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._send(400, {"ok": False, "error": {
                "code": "BAD_REQUEST", "message": f"JSON 解析失败: {e}"}})
            return
        if not isinstance(req, dict) or req.get("stage") not in STAGES:
            self._send(400, {"ok": False, "error": {
                "code": "BAD_REQUEST",
                "message": f"stage 必须是 {STAGES}"}})
            return
        if not (req.get("text") or req.get("messages")):
            self._send(400, {"ok": False, "error": {
                "code": "BAD_REQUEST", "message": "需要 text 或 messages"}})
            return
        if self.engine.state == "loading":
            self._send(503, {"ok": False, "error": {
                "code": "UNAVAILABLE", "message": "模型仍在加载，请稍后重试"}})
            return
        if self.engine.state != "ready":
            self._send(503, {"ok": False, "error": {
                "code": "UNAVAILABLE",
                "message": self.engine.error or "模型不可用"}})
            return
        timeout = float(req.get("timeout") or 60)
        timeout = max(1.0, min(120.0, timeout))
        import time as _time
        _t0 = _time.perf_counter()
        _stage = str(req.get("stage") or "")
        # ★ [Round 125] dual_judge 快失败：本地 judge 吞吐低，忙/排队时直接 503 BUSY，
        #   引擎侧立即回退 llm（避免等满 120s timeout）。
        if _stage == "dual_judge":
            try:
                _busy = (int(getattr(self.engine, "queue_depth", 0) or 0) > 0
                         or bool(self.engine.stats.get("busy_now")))
            except Exception:  # noqa: BLE001
                _busy = False
            if _busy:
                try:
                    with self.engine._stats_lock:
                        self.engine.stats["dual_judge_fastfail"] = int(
                            self.engine.stats.get("dual_judge_fastfail", 0)) + 1
                except Exception:  # noqa: BLE001
                    pass
                self._send(503, {"ok": False, "error": {
                    "code": "BUSY",
                    "message": "dual_judge busy：本地 judge 吞吐不足，快速回退 llm"}})
                return
        _adapter = ""
        _ok = False
        self.engine.stat_begin(_stage)
        try:
            res = self.engine.submit(req, timeout + 2.0)
            _adapter = str((res or {}).get("adapter") or "")
            _ok = True
            self._send(200, res)
        except TimeoutError:
            self._send(503, {"ok": False, "error": {
                "code": "TIMEOUT",
                "message": f"生成超过 timeout={timeout}s"}})
        except Exception as e:
            self._send(503, {"ok": False, "error": {
                "code": "INTERNAL", "message": f"{type(e).__name__}: {e}"}})
        finally:
            try:
                self.engine.stat_end(_stage, _t0, adapter=_adapter, ok=_ok)
            except Exception:
                pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8772)
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    args = ap.parse_args()
    eng = LocalEngine(args)
    Handler.engine = eng
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    print(f"[serve] http://{args.host}:{args.port}  "
          f"model={args.model}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("[serve] bye", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

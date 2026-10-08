# -*- coding: utf-8 -*-
"""[v1.23.0 W1] 核心联网 · 基础设施 —— 打补丁脚本（唯一事实源）。

本阶段**不接入任何环节**：只建 Gate / Client / Cache / 独立 logger / 配置段。
三条卡点是回写后的设计（见 `_v123_taskbook.md` §零）：
  · [修正 B2] logger_web.propagate = False
  · [修正 B3] note_failure() 显式置 disabled
  · 缓存目录 cache/websearch/（不复用 cache/anchors/）
幂等：哨兵串。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.23.0.py"
SENTINEL = "[v1.23.0 W1]"

src = TARGET.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF"
src = src.replace("\r\n", "\n")
if SENTINEL in src:
    print("== 已打过 W1 补丁，跳过 =="); sys.exit(0)


def sub_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    return text.replace(old, new)


# ---------------------------------------------------------------- 1 标题 / 版本
src = sub_once(src, "\n元 DGTF · v1.22.2\n", "\n元 DGTF · v1.23.0\n", "标题")
src = sub_once(src, '__version__ = "1.22.2"\n', '__version__ = "1.23.0"\n', "版本号")

# ---------------------------------------------------------------- 2 changelog
CHANGELOG = """v1.23.0 W1 ── 核心联网 · 基础设施（骨架 / 客户端 / 缓存 / 独立通道 / 配额三层）

  ★ 本 Phase **不接入任何环节**（research_decompose 等全部「只配不接」）。
    验收通过即成 W1 门；未通过不许进入 W2。

  【前置】W 系列任务书本身先经过核验（v1.22.2 阶段 0 范式），
    3 处卡点已回写成执行版 `_v123_taskbook.md`：
    · [修正 B1] W2 的判据「apply_decidability_change(evidence=[W#], to=partial)
      → applied」依赖「W# 进 _citation_table」——原方案把这一项排在 W4，
      判据与交付物不同阶段 = **判据不可达**。已把该项移到 **W2 前置**。
    · [修正 B2] `dgtf.websearch` 是 `dgtf` 的**子 logger**，propagate 默认 True
      ⇒「所有 web 日志只进这个 logger」这条红线无法成立。已加 `propagate = False`。
    · [修正 B3] 原 §6.3 声称「连续 3 次失败 → disabled = True」，但代码片段里
      **没有任何一处**给 disabled 赋值（allow() 只返回 False）⇒ 产物里读不到
      「本跑已降级」。已让 `note_failure()` 显式置位并留痕 `[W-DISABLED]`。

  【新增配置段】`DEFAULT_CONFIG["web_search"]`（加性；`external_anchor` 一键未动）
    · enabled=False（默认关：不显式打开 = 零调用）
    · quota 三层：per_stage_round / per_stage_total / per_run_total
    · stages：修行层 term_calibration 与 stop_criteria 默认 **False**
    · backend / api_key_env / timeout / max_retries / backoff / cache_ttl_hours
    · auto_disable_after_failures = 3

  【新增符号】
    · `logger_web` = logging.getLogger("dgtf.websearch")，**propagate=False**
    · `WEB_FAIL_KINDS` = timeout / rate_limit / empty / dirty / api_error（五档）
    · `WebSearchCache`：sha256 + TTL，`cache/websearch/`
      —— **不复用** `cache/anchors/`（那是锚点快照的命名空间，混用会污染其语义）
    · `WebSearchClient`：超时 / 重试 / 退避；`search()` 返回 `(results, fail_kind)`，
      **失败分类返回而不是抛裸异常**（否则「0 条」与「超时」在调用方长得一样）
    · `WebSearchGate`：授权 + 三层配额 + 连续失败降级（三个否定方向都给可读理由）
    · `build_web_search(config)`：从配置造一套，**不发起任何调用**

  【与既有组件的关系】
    · 不合并 `AnchorRetriever`（锚点 = 事先落盘的冻结事实）与 `WebSearchClient`
      （联网 = 运行时活检索）；编号 `X#` / `W#` 不互换。
    · `_overlap_coef` / `_UNTRACED_OVERLAP` / `0.6` 等阈值一律未动。

  【本 Phase 不做】任何环节接入；W# 进 `_citation_table`（属 W2）；三池（属 W2/W3）。

"""
src = sub_once(src, "\nv1.22.2 ── 收尾补充",
               "\n" + CHANGELOG + "v1.22.2 ── 收尾补充", "changelog")

# ---------------------------------------------------------------- 3 配置段
CFG_OLD = (
    '        # 检索后端。当前只有 snapshot 真实现，其它取值抛错不静默降级\n'
    '        "retriever": "snapshot",\n'
    '    },\n'
    '}\n'
)
CFG_NEW = (
    '        # 检索后端。当前只有 snapshot 真实现，其它取值抛错不静默降级\n'
    '        "retriever": "snapshot",\n'
    '    },\n'
    '    # ============================================================\n'
    '    # [v1.23.0 W1] 核心联网（W 系列）。★ 加性：不动上面 external_anchor 一键。\n'
    '    #   【它是什么】运行时**发起**的检索，与 external_anchor（事先落盘的\n'
    '    #     冻结事实快照）是两件事。两套编号 X# / W# **不互换**。\n'
    '    #   【红线】按环节授权（不是全局 ON/OFF）；检索结果只作**参照**，\n'
    '    #     一律不进 view.candidates / 不进 _ing / 不进对撞第三者；\n'
    '    #     失败走独立 logger（dgtf.websearch）。\n'
    '    # ============================================================\n'
    '    "web_search": {\n'
    '        # 【用途】全局总闸。【默认】false —— 不显式打开就是**零调用**。\n'
    '        "enabled": False,\n'
    '        # 【用途】检索后端（key 走环境变量，不落盘）。\n'
    '        "backend": "tavily",\n'
    '        "api_key_env": "TAVILY_API_KEY",\n'
    '        # 【用途】单次请求超时（秒）/ 重试次数 / 退避基数（秒）。\n'
    '        "timeout_seconds": 30,\n'
    '        "max_retries": 2,\n'
    '        "backoff_seconds": 1.8,\n'
    '        # 【用途】检索结果缓存小时数（sha256 落 cache/websearch/）。\n'
    '        "cache_ttl_hours": 24,\n'
    '        # 【配额三层】每环节每圈 / 每环节全程 / 每跑总。三层都过才允许调用。\n'
    '        "quota": {\n'
    '            "per_stage_round": 2,\n'
    '            "per_stage_total": 8,\n'
    '            "per_run_total": 30,\n'
    '        },\n'
    '        # 【环节授权】逐个环节的开关。修行层与停止判据**默认关**\n'
    '        #   （修行层动了会污染「输入是形状不是数据」这条宪法级特性）。\n'
    '        "stages": {\n'
    '            "practice_term_calibration": False,\n'
    '            "research_decompose": True,\n'
    '            "research_evidence": True,\n'
    '            "research_precedent": True,\n'
    '            "duel_arbitration": True,\n'
    '            "meta_clean_check": True,\n'
    '            "stop_criteria": False,\n'
    '        },\n'
    '        # 【引用授权】off / record / crosscheck / evidence / gate。\n'
    '        "as_evidence": "crosscheck",\n'
    '        "tier_floor": 2,\n'
    '        # 【失败降级】连续失败达到此值 → 本跑联网关闭（留痕 [W-DISABLED]）。\n'
    '        "auto_disable_after_failures": 3,\n'
    '    },\n'
    '}\n'
)
src = sub_once(src, CFG_OLD, CFG_NEW, "配置段")

# ---------------------------------------------------------------- 4 基础设施
CLASSES = '''# ============================================================
# [v1.23.0 W1] 核心联网 · 基础设施（不接入任何环节）
# ============================================================
# ★ 三条红线（都是**核验后回写**的，原方案在这里各有一处会静默失败）：
#   · logger_web.propagate = False —— 否则 "dgtf"（父 logger）会一起收，
#     「联网失败走独立通道、不淹没普通错误」这条红线就是空话；
#   · note_failure() 必须**显式**置 disabled —— 否则「本跑已降级」读不到；
#   · 缓存目录 cache/websearch/，**不复用** cache/anchors/
#     （那是锚点快照的命名空间，混用会把两种语义搅在一起）。
logger_web = logging.getLogger("dgtf.websearch")
logger_web.setLevel(logging.INFO)
logger_web.propagate = False
# ★ 独立通道的意义：检索失败（超时/限流/脏数据）是**高频、可预期**的，
#   混进主线日志会让一次网络抖动淹没整份跑圈痕迹。

# [v1.23.0 W1] 失败分类五档。★ 空结果 `empty` 与「请求失败」必须分开 ——
#   前者说明「外部确实没有」，后者说明「这次没问到」，语义完全不同。
WEB_FAIL_KINDS = ("timeout", "rate_limit", "empty", "dirty", "api_error")


class WebSearchCache:
    """[v1.23.0 W1] sha256 + TTL 检索缓存。**只省调用，不入池。**"""

    def __init__(self, ttl_hours: float = 24.0, root: str = "cache/websearch"):
        self.ttl = float(ttl_hours or 24.0) * 3600.0
        self.root = Path(root)
        self.hits = 0
        self.misses = 0

    def key(self, backend: str, query: str) -> str:
        return hashlib.sha256(
            (str(backend) + ":" + str(query)).encode("utf-8")).hexdigest()[:24]

    def path_for(self, backend: str, query: str) -> Path:
        return self.root / (self.key(backend, query) + ".json")

    def get(self, backend: str, query: str):
        """命中返回 results（可能是空 list）；未命中 / 过期返回 None。"""
        p = self.path_for(backend, query)
        try:
            if p.is_file():
                d0 = json.loads(p.read_text(encoding="utf-8"))
                if time.time() - float(d0.get("_ts") or 0) < self.ttl:
                    self.hits += 1
                    return list(d0.get("results") or [])
        except Exception:
            pass                    # 缓存坏了不是错误，重查一遍即可
        self.misses += 1
        return None

    def put(self, backend: str, query: str, results) -> None:
        p = self.path_for(backend, query)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"_ts": time.time(),
                                     "results": list(results or [])},
                                    ensure_ascii=False, indent=2),
                         encoding="utf-8")
        except Exception as exc:    # 缓存写失败不影响本次结果
            logger_web.warning("[W-CACHE-WRITE] %s", exc)


class WebSearchClient:
    """[v1.23.0 W1] HTTP 客户端：超时 / 重试 / 退避 / **五类失败**。

    ★ 与 `AnchorRetriever._tavily` 的区别：那个抓的是**锚点快照**（一次性、
      无重试、无分类）；本类是**运行时**检索，必须把失败**分类**返回 ——
      否则调用方看到的是「0 条」，分不清「外部没有」和「这次没问到」。
    ★ `_http()` 是**可打桩的缝**：探针 / 冒烟覆写它就能离线测全部五档失败，
      不需要网络。
    """

    def __init__(self, backend: str, api_key: str, timeout: float = 30,
                 max_retries: int = 2, backoff: float = 1.8,
                 cache: Optional["WebSearchCache"] = None):
        self.backend = str(backend or "tavily").strip().lower()
        self.api_key = api_key or ""
        self.timeout = float(timeout or 30)
        self.max_retries = int(max_retries or 0)
        self.backoff = float(backoff or 0)
        self.cache = cache
        self.calls = 0              # 真打网络的次数（缓存命中不计）
        self.cache_hits = 0
        self.fail_counts: Dict[str, int] = {}

    def _endpoint(self) -> str:
        if self.backend == "tavily":
            return "https://api.tavily.com/search"
        # ★ 与 `AnchorRetriever` 同款纪律：未知后端**抛错留痕**，不静默降级。
        raise RuntimeError(
            "web_search.backend=" + repr(self.backend)
            + " 尚未实现（当前只有 'tavily'）；不静默降级")

    def _http(self, query: str, max_n: int) -> Tuple[list, str]:
        """真打网络。返回 `(results, fail_kind)`；成功时 fail_kind == ""。"""
        import urllib.error
        import urllib.request
        body = json.dumps({"api_key": self.api_key, "query": query,
                           "max_results": int(max_n)}).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint(), data=body,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read().decode("utf-8")
        except TimeoutError:
            return [], "timeout"
        except urllib.error.HTTPError as exc:
            if int(getattr(exc, "code", 0) or 0) == 429:
                return [], "rate_limit"
            return [], "api_error"
        except urllib.error.URLError as exc:
            if isinstance(getattr(exc, "reason", None), TimeoutError):
                return [], "timeout"
            return [], "api_error"
        except OSError:
            return [], "api_error"
        try:
            data = json.loads(raw)
        except Exception:
            return [], "dirty"
        if not isinstance(data, dict):
            return [], "dirty"
        out: List[dict] = []
        for it in (data.get("results") or []):
            if not isinstance(it, dict):
                continue
            _c = str(it.get("content", "") or "").strip()
            if not _c:
                continue
            out.append({"claim": _c[:400],
                        "url": str(it.get("url", ""))[:300],
                        "source": str(it.get("url", ""))[:200],
                        "kind": "web", "tier": 3})
        return out, ("" if out else "empty")

    def search(self, query: str, max_n: int = 8) -> Tuple[list, str]:
        """检索一条 query。返回 `(results, fail_kind)`。

        · 缓存命中 → 直接返回，**不计 calls**；
        · `empty` 是**终态**（外部确实没有），不重试、不算「连续失败」；
        · 其余失败档按 `max_retries` 重试（线性退避），全失败则返回最后一档。
        """
        if self.cache is not None:
            hit = self.cache.get(self.backend, query)
            if hit is not None:
                self.cache_hits += 1
                return hit, ""
        kind = "api_error"
        for attempt in range(self.max_retries + 1):
            self.calls += 1
            res, kind = self._http(query, max_n)
            self.fail_counts[kind] = self.fail_counts.get(kind, 0) + 1
            if kind in ("", "empty"):
                if kind == "" and self.cache is not None:
                    self.cache.put(self.backend, query, res)
                return res, kind
            logger_web.warning("[W-%s] query=%s attempt=%d/%d",
                               kind.upper(), str(query)[:80],
                               attempt + 1, self.max_retries + 1)
            if attempt < self.max_retries:
                time.sleep(self.backoff * (attempt + 1))
        return [], kind


class WebSearchGate:
    """[v1.23.0 W1] 授权 + 配额三层 + 连续失败降级。

    ★ 三个否定方向（未启用 / 未授权 / 配额或降级）都必须给出**可读理由**，
      并且 `allow()` 的 reason 与 `disabled` **状态一致** —— 否则产物里
      只能从每次 reason 猜「本跑到底降级没有」。
    """

    def __init__(self, config: dict, run_id: str = ""):
        self.cfg = ((config or {}).get("web_search") or {})
        self.run_id = run_id
        self.stage_counts: Dict[str, int] = {}
        self.round_counts: Dict[Tuple[str, int], int] = {}
        self.run_total = 0
        self.consecutive_failures = 0
        self.disabled = not bool(self.cfg.get("enabled", False))
        self.disable_reason = "" if not self.disabled else "web_search 未启用"

    def _q(self, k: str, d: int) -> int:
        try:
            return int((self.cfg.get("quota") or {}).get(k, d) or d)
        except (TypeError, ValueError):
            return d

    def _i(self, k: str, d: int) -> int:
        _v = self.cfg.get(k, d)
        try:
            return int(d if _v is None else _v)
        except (TypeError, ValueError):
            return d

    def allow(self, stage: str, round_no: int) -> Tuple[bool, str]:
        if not bool(self.cfg.get("enabled", False)):
            return False, "web_search 未启用（默认关）"
        if not bool((self.cfg.get("stages") or {}).get(stage, False)):
            return False, "stage " + repr(stage) + " 未授权"
        if self.disabled:
            return False, ("本跑已降级（连续失败 "
                           + str(self.consecutive_failures) + " 次）")
        if self.run_total >= self._q("per_run_total", 30):
            return False, "本次运行总配额用尽"
        if self.stage_counts.get(stage, 0) >= self._q("per_stage_total", 8):
            return False, "stage " + repr(stage) + " 全程配额用尽"
        if self.round_counts.get((stage, round_no), 0) >= \
                self._q("per_stage_round", 2):
            return False, "stage " + repr(stage) + " 本圈配额用尽"
        return True, ""

    def note_call(self, stage: str, round_no: int) -> None:
        self.stage_counts[stage] = self.stage_counts.get(stage, 0) + 1
        self.round_counts[(stage, round_no)] = \
            self.round_counts.get((stage, round_no), 0) + 1
        self.run_total += 1

    def note_failure(self, kind: str = "") -> bool:
        """记一次失败。返回**是否因此被降级**（调用方据此留痕）。"""
        self.consecutive_failures += 1
        _lim = self._i("auto_disable_after_failures", 3)
        if self.consecutive_failures >= _lim and not self.disabled:
            self.disabled = True
            self.disable_reason = ("连续失败 " + str(self.consecutive_failures)
                                   + " 次（限 " + str(_lim) + "），本跑联网关闭")
            logger_web.warning("[W-DISABLED] %s", self.disable_reason)
            return True
        return False

    def note_success(self) -> None:
        self.consecutive_failures = 0

    def summary(self) -> dict:
        return {"enabled": bool(self.cfg.get("enabled", False)),
                "disabled": self.disabled,
                "disable_reason": self.disable_reason,
                "run_total": self.run_total,
                "stage_counts": dict(self.stage_counts),
                "consecutive_failures": self.consecutive_failures}


def build_web_search(config: dict, run_id: str = "") -> Tuple[WebSearchGate,
                                                              WebSearchClient]:
    """[v1.23.0 W1] 从配置造一套（Gate + Client + Cache）。**不发起任何调用。**

    `enabled=False` 时同样返回可用对象 —— 只是 `gate.allow()` 恒 False，
    于是调用点不需要写 `if enabled` 这种会被漏掉的判断。
    """
    cfg = ((config or {}).get("web_search") or {})
    gate = WebSearchGate(config, run_id)
    cache = WebSearchCache(cfg.get("cache_ttl_hours", 24))
    _env = str(cfg.get("api_key_env") or "").strip()
    client = WebSearchClient(
        backend=cfg.get("backend", "tavily"),
        api_key=(os.environ.get(_env, "") if _env else ""),
        timeout=cfg.get("timeout_seconds", 30),
        max_retries=cfg.get("max_retries", 2),
        backoff=cfg.get("backoff_seconds", 1.8),
        cache=cache)
    return gate, client


'''

ANCHOR = (
    '        return out\n'
    '\n'
    '\n'
    'def _compute_rephrase_streak(view, state) -> int:\n'
    '    """[v122 P6 G6.3] 「ing 连续几圈在复述」的唯一实现。\n'
)
NEW = (
    '        return out\n'
    '\n'
    '\n'
    + CLASSES
    + 'def _compute_rephrase_streak(view, state) -> int:\n'
    '    """[v122 P6 G6.3] 「ing 连续几圈在复述」的唯一实现。\n'
)
src = sub_once(src, ANCHOR, NEW, "基础设施")

# ---------------------------------------------------------------- 写回
out = src.replace("\n", "\r\n")
b = out.encode("utf-8")
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert b.count(b"\r") == b.count(b"\r\n"), "出现裸 CR"
TARGET.write_bytes(b)
print("OK: v1.23.0 W1 补丁已写入")
print("  配置段 web_search / logger_web(propagate=False) / WebSearchCache / "
      "WebSearchClient / WebSearchGate / build_web_search")

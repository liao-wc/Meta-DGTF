# -*- coding: utf-8 -*-
"""[v1.23.1] 遗留收尾补丁：round_no 真圈号 + tier 提案（待审）+ 版本段。

纪律（见 skill dgtf-version-bump）：
  · 先复制 v1.23.0 → v1.23.1（不覆盖源文件）；
  · 一律 read_bytes / write_bytes，双向断言 CRLF；禁用 write_text；
  · 每个锚点断言 count == 1（重复插入是真实事故）；
  · 断言用字面串，不用正则。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE / "元DGTF-V1.23.0.py"
NEW = HERE / "元DGTF-V1.23.1.py"

if NEW.exists():
    print("[skip] %s 已存在，直接用现有内容做补丁" % NEW.name)
    src = NEW.read_bytes().decode("utf-8")
else:
    src = OLD.read_bytes().decode("utf-8")
    print("[copy] %s -> %s" % (OLD.name, NEW.name))

assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF"
src = src.replace("\r\n", "\n")


def sub_once(text, old, new, tag, expect=1):
    n = text.count(old)
    assert n == expect, "[%s] 锚点命中 %d 次（应为 %d）" % (tag, n, expect)
    print("  · %s" % tag)
    return text.replace(old, new)


# =============================================================== 1 版本号（两处）
src = sub_once(src, "元 DGTF · v1.23.0", "元 DGTF · v1.23.1", "docstring 标题")
src = sub_once(src, '__version__ = "1.23.0"', '__version__ = "1.23.1"',
               "__version__")

# =============================================================== 2 changelog
CL_OLD = "  【W5-fix】`Pool.to_dict()` 是**显式白名单**，W2/W3 新增的 5 个联网字段"
CL_NEW = """v1.23.1 ── 遗留收尾（真圈号 / tier 提案待审 / 三场景 + 三票正交度实证）

  【遗留3 · round_no 换真圈号】原先所有环节的 round 都取「拆解序号」
    （`_web_prep_seq`）—— 拆解每跑只发生一次 ⇒ 所有 round 恒为 1 ⇒
    `quota.per_stage_round`（任务书写明「每环节**每圈**」）退化成
    「每环节每跑」，**三层配额实际只剩两层**。这是语义名不对带来的
    **实质**后果，不只是命名问题。
    改法：`_web_evidence_hook` 用 `update_deferrals` 传进来的真圈号；
    `_web_duel_arbitration` / `_web_meta_clean_check` 加 `round_no` 形参，
    由 `_finalize_layer_common` 传 `r_actual + 1`；拆解前置（圈循环之前，
    确实没有圈号）统一为 **0**，并在每条 W# 上留 `round_kind`（pre/in）
    与 `pre_seq` —— 让「前置」与「圈内 1..N」在产物里可区分。

  【遗留2 · 联网结果 tier 提案（**待审**）】W# 的 tier 现在一律是客户端
    初值 3（= 未知），`tier_floor` 是 2 ⇒ 这批材料的 tier **没有信息量**。
    但直接让它自动判 tier 比没有更危险（一条 tier=1 的二手转述能支撑
    →decidable）。所以只做**提案**：
    · 新增纯函数 `_web_tier_proposal(results, cfg, known_domains)`，
      按 `domain_tier_rules`（前缀 → tier）给建议档；未知域名保守取 3；
      返回 `{url, domain, proposed_tier, why, first_seen, confirmed: False}`。
    · 新增 `WebSearchCache.domains_load()/domains_save()`：首次出现的域名
      落 `cache/websearch/_domains.json`（**只登记，不判 tier**）。
    · 结果写 `pool.web_tier_proposals` + 池级留痕 `[W-TIER?] ...（待审，未生效）`。
    · ★ `web_search.tier_proposal` **默认 False**（= 与 v1.23.0 逐字相同）；
      即便打开，也**绝不**改 `item["tier"]`、**绝不**进任何判定路径 ——
      判据带着变异体（把提案写进 item["tier"] ⇒ 判红）。

  【遗留1 · 三场景命中率 + 三票正交度】按项目口径「每题只跑 2 次」设计
    最小可判实验：3 场景 × 2 跑（联网 ON）+ 1 场景 × 2 跑（联网 OFF
    负对照）。命中率 = 「联网结果与场景预期一致」的跑数占比；
    正交度用两两一致率矩阵（agree12 / agree13 / agree23）——
    只有**组间差 ≥ 组内极差**才许下结论，否则如实写「不可判定」。

  【遗留4 · v1.22.2 遗留的两条 `P2.4.a/b`】判据的锚是
    `outputs/p2_run{1,2,3}`（v1.22.1 时点的产物，本机已被清理）⇒
    「缺失即判红」。按本版口径用**当前版**重跑这 3 题补齐产物，
    判据在**当代码**上重新为真（不是冻结快照）。

v1.23.0 W5-fix ── 池出口白名单 + 成功留痕

  【W5-fix】`Pool.to_dict()` 是**显式白名单**，W2/W3 新增的 5 个联网字段"""
src = sub_once(src, CL_OLD, CL_NEW, "changelog 段 + W5-fix 补头")

# =============================================================== 3 配置段（加性）
CFG_OLD = """        # 【失败降级】连续失败达到此值 → 本跑联网关闭（留痕 [W-DISABLED]）。
        "auto_disable_after_failures": 3,
    },
}"""
CFG_NEW = """        # 【失败降级】连续失败达到此值 → 本跑联网关闭（留痕 [W-DISABLED]）。
        "auto_disable_after_failures": 3,
        # 【tier 提案】[v1.23.1 遗留2] 是否给联网结果提「建议 tier」。
        #   ★ 默认 False = 与 v1.23.0 逐字相同（零副作用）。
        #   ★ 即便 True 也只写**待审**建议：绝不改 item["tier"]、
        #     绝不进任何判定路径 —— 由人确认后才谈 tier 生效。
        "tier_proposal": False,
        # 【域名启发式】提案依据表：`[子串, tier]`，tier 越小越硬。
        #   未知域名保守取 3（> 默认 tier_floor 2 ⇒ 进不了引用表）。
        "domain_tier_rules": [
            [".gov.cn", 1], [".gov", 1], [".edu", 2],
            ["iso.org", 1], ["standard", 1], ["wikipedia.org", 3],
            ["blog", 4], ["forum", 4],
        ],
    },
}"""
src = sub_once(src, CFG_OLD, CFG_NEW, "DEFAULT_CONFIG.web_search +2 键")

# =============================================================== 4 新模块级函数
FUNC_OLD = "def _web_digest_block(results) -> str:"
FUNC_NEW = '''_WEB_TIER_FALLBACK = 3


def _web_domain_of(url) -> str:
    """[v1.23.1 遗留2] 从 URL 取域名（小写、去 www.）。取不到返回 ""。"""
    _u = str(url or "").strip().lower()
    if not _u:
        return ""
    _u = _u.split("://", 1)[-1]
    _u = _u.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    _u = _u.split("@", 1)[-1].split(":", 1)[0]
    if _u.startswith("www."):
        _u = _u[4:]
    return _u.strip(".")


def _web_tier_proposal(results, cfg, known_domains=None) -> List[dict]:
    """[v1.23.1 遗留2] 给联网结果提「**建议** tier」，供**人工确认**。

    【为什么需要】W# 的 tier 现在一律是客户端给的初值 3（= 未知），
      而 `tier_floor` 是 2 —— 这批材料的 tier **没有任何信息量**。
      要让它有意义就得先回答「这条来自哪、算几档」；但**自动应用**比
      不判更危险（一条 tier=1 的二手转述能支撑 →decidable）。
      所以本版只做**提案**：写进待审队列，不进任何判定路径。

    【纯函数】不改入参、不读盘、不写盘（`known_domains` 由调用方给）。
      返回 `[{url, domain, proposed_tier, why, first_seen, confirmed}]`。
      ★ `first_seen=True` = 本跑首次见到该域名 ⇒ 一定进待审队列。
      ★ 返回的 tier **不会**被写回 `item["tier"]`（判据带变异体钉住）。
    """
    _cfg = cfg or {}
    _rules = _cfg.get("domain_tier_rules") or []
    _known = {str(x) for x in (known_domains or ()) if str(x)}
    _seen = set()
    out: List[dict] = []
    for it in (results or []):
        _u = str((it or {}).get("url", "") or "")
        _d = _web_domain_of(_u)
        if not _d or _d in _seen:
            continue
        _seen.add(_d)
        _t = _WEB_TIER_FALLBACK
        _why = "未知域名 → 保守取 " + str(_WEB_TIER_FALLBACK)
        for _pair in _rules:
            try:
                _pat, _val = str(_pair[0]).lower(), int(_pair[1])
            except Exception:  # noqa: BLE001
                continue
            if _pat and _pat in _d:
                _t, _why = _val, "命中域名规则 " + _pat
                break
        out.append({"url": _u[:300], "domain": _d, "proposed_tier": _t,
                    "why": _why, "first_seen": _d not in _known,
                    "confirmed": False})
    return out


def _web_digest_block(results) -> str:'''
src = sub_once(src, FUNC_OLD, FUNC_NEW, "新增 _web_domain_of / _web_tier_proposal")

# =============================================================== 5 缓存：域名登记
CACHE_OLD = """        except Exception as exc:    # 缓存写失败不影响本次结果
            logger_web.warning("[W-CACHE-WRITE] %s", exc)"""
CACHE_NEW = """        except Exception as exc:    # 缓存写失败不影响本次结果
            logger_web.warning("[W-CACHE-WRITE] %s", exc)

    def domains_load(self) -> set:
        \"\"\"[v1.23.1 遗留2] 已见域名集合（tier 提案的「首次出现」判据）。

        ★ 只登记域名，**不存 tier** —— tier 由人确认，不由这里定。
        坏文件 / 不存在 → 空集（缓存坏了不是错误）。
        \"\"\"
        p = self.root / "_domains.json"
        try:
            if p.is_file():
                d0 = json.loads(p.read_text(encoding="utf-8"))
                return {str(x) for x in (d0.get("domains") or []) if str(x)}
        except Exception:  # noqa: BLE001
            pass
        return set()

    def domains_save(self, new_domains) -> None:
        \"\"\"把新域名并进 `cache/websearch/_domains.json`。写失败只告警。\"\"\"
        _all = sorted(self.domains_load()
                      | {str(x) for x in (new_domains or []) if str(x)})
        p = self.root / "_domains.json"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(json.dumps({"_ts": time.time(), "domains": _all},
                                     ensure_ascii=False, indent=2)
                          .encode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger_web.warning("[W-DOMAIN-WRITE] %s", exc)"""
src = sub_once(src, CACHE_OLD, CACHE_NEW,
               "WebSearchCache +domains_load/domains_save")

# =============================================================== 6 Pool 字段
POOL_FIELD_OLD = """    web_arbitration: List[dict] = field(default_factory=list)
    web_clean_check: List[dict] = field(default_factory=list)
"""
POOL_FIELD_NEW = """    web_arbitration: List[dict] = field(default_factory=list)
    web_clean_check: List[dict] = field(default_factory=list)
    # ---- [v1.23.1 遗留2] tier **提案**（待审）。★ 它不是产物、不是判决：
    #   只记「这个域名建议算几档」，`item["tier"]` 一字不改，也不进
    #   任何判定路径 —— 由人确认后才谈 tier 生效。
    web_tier_proposals: List[dict] = field(default_factory=list)
"""
src = sub_once(src, POOL_FIELD_OLD, POOL_FIELD_NEW, "Pool +web_tier_proposals")

POOL_TD_OLD = """        if self.web_clean_check:
            d["web_clean_check"] = self.web_clean_check
        return d"""
POOL_TD_NEW = """        if self.web_clean_check:
            d["web_clean_check"] = self.web_clean_check
        # [v1.23.1 遗留2] tier 提案（待审）。加性：没有提案时一个键都不加
        #   —— 关闭态 packed 与 v1.23.0 逐字相同。
        if self.web_tier_proposals:
            d["web_tier_proposals"] = self.web_tier_proposals
        return d"""
src = sub_once(src, POOL_TD_OLD, POOL_TD_NEW, "Pool.to_dict +提案出口")

# =============================================================== 7 round_no 语义
RR_OLD = '''    def _research_round_no(self) -> int:
        """[W2] 研究层的圈序号（拆解每圈发生一次，用它当配额口径的 round）。"""
        return int(getattr(self, "_web_prep_seq", 0) or 0)'''
RR_NEW = '''    def _research_round_no(self) -> int:
        """[v1.23.1 遗留3] **前置**检索的圈号 = 0（与圈内 1..N 分开）。

        ★ 原先这里返回「拆解序号」（`_web_prep_seq`）并拿它当配额口径的
          round —— 不只是命名问题：拆解每跑只发生一次 ⇒ 所有环节的 round
          恒为 1 ⇒ `quota.per_stage_round`（任务书是「每环节**每圈**」）
          退化成「每环节每跑」，**三层配额实际只剩两层**。
        ★ 拆解确实发生在圈循环**之前**，没有圈号；用 0 明确表示「前置」。
          圈内一律用 `layer_no`：`_web_evidence_hook` 的 `layer`、
          `_finalize_layer_common` 的 `r_actual + 1`。
        """
        return 0'''
src = sub_once(src, RR_OLD, RR_NEW, "_research_round_no → 前置口径 0")

WS_SIG_OLD = """    def _web_search(self, stage: str, queries, round_no: int,
                    used_as: str = "evidence") -> List[dict]:"""
WS_SIG_NEW = """    def _web_search(self, stage: str, queries, round_no: int,
                    used_as: str = "evidence", pre_seq: int = 0) -> List[dict]:"""
src = sub_once(src, WS_SIG_OLD, WS_SIG_NEW, "_web_search +pre_seq 形参")

WS_DOC_OLD = """        【enabled=False】调用点不必写 `if enabled`：本方法直接返回 []，
        且**一次 Gate 都不判**（零调用是可验证的）。
        \"\"\""""
WS_DOC_NEW = """        【enabled=False】调用点不必写 `if enabled`：本方法直接返回 []，
        且**一次 Gate 都不判**（零调用是可验证的）。
        【round_no 口径 · v1.23.1 遗留3】**圈内**传真圈号（1..N）；
          **前置**（圈循环之前的拆解/存在性检索）传 0，
          并把序号走 `pre_seq`。产物上另留 `round_kind`（pre/in）把两者
          分开 —— 配额三层的 `per_stage_round` 这才真的是「每圈」。
        \"\"\""""
src = sub_once(src, WS_DOC_OLD, WS_DOC_NEW, "_web_search docstring 口径")

WS_ITEM_OLD = """                        "used_as": used_as, "round": int(round_no)}"""
WS_ITEM_NEW = """                        "used_as": used_as, "round": int(round_no),
                        "round_kind": ("pre" if int(round_no) <= 0 else "in"),
                        "pre_seq": int(pre_seq or 0)}"""
src = sub_once(src, WS_ITEM_OLD, WS_ITEM_NEW, "W# 条目 +round_kind/pre_seq")

WS_TAIL_OLD = """                + "、".join(str(x.get("id")) for x in out[:4])
                + ("…" if len(out) > 4 else "") + "）")
        return out"""
WS_TAIL_NEW = """                + "、".join(str(x.get("id")) for x in out[:4])
                + ("…" if len(out) > 4 else "") + "）")
        # [v1.23.1 遗留2] tier **提案**（默认关）。★ 只写建议，不改任何字段：
        #   提案进 `pool.web_tier_proposals` + 池级留痕，域名进
        #   `cache/websearch/_domains.json`。**不进任何判定路径**。
        try:
            _ws_cfg = (self.config or {}).get("web_search") or {}
            if out and bool(_ws_cfg.get("tier_proposal")):
                _ck = getattr(client, "cache", None)
                _known = _ck.domains_load() if _ck is not None else set()
                _pr = _web_tier_proposal(out, _ws_cfg, _known)
                if _pr:
                    if pool is not None:
                        pool.web_tier_proposals.extend(_pr)
                        pool.meta.append(
                            "[W-TIER?] 建议 tier " + str(len(_pr)) + " 条"
                            "（其中新域名 "
                            + str(sum(1 for x in _pr if x.get("first_seen")))
                            + " 条）："
                            + "、".join(str(x.get("domain")) + "→"
                                        + str(x.get("proposed_tier"))
                                        for x in _pr[:4])
                            + "（**待审**，未生效；不改任何判定）")
                    if _ck is not None:
                        _ck.domains_save([x.get("domain") for x in _pr])
        except Exception as _etp:  # noqa: BLE001
            logger_web.warning("[W-TIER-EXC] %s", _etp)
        return out"""
src = sub_once(src, WS_TAIL_OLD, WS_TAIL_NEW, "_web_search 尾部 tier 提案")

PREP_OLD = """        self._web_prep_seq = int(getattr(self, "_web_prep_seq", 0) or 0) + 1
        _rn = self._research_round_no()
        pool = self.pools.get("1")
        _r1 = self._web_search("research_decompose",
                               _research_decompose_queries(question, pool), _rn)"""
PREP_NEW = """        self._web_prep_seq = int(getattr(self, "_web_prep_seq", 0) or 0) + 1
        # [v1.23.1 遗留3] 前置：圈循环之前 ⇒ 圈号 0；序号走 pre_seq。
        _rn = self._research_round_no()
        _pre = self._web_prep_seq
        pool = self.pools.get("1")
        _r1 = self._web_search("research_decompose",
                               _research_decompose_queries(question, pool), _rn,
                               pre_seq=_pre)"""
src = sub_once(src, PREP_OLD, PREP_NEW, "_research_web_prep 前置口径")

PREP2_OLD = """        _r2 = self._web_search("research_precedent",
                               _research_precedent_queries(_und), _rn,
                               used_as="record")"""
PREP2_NEW = """        _r2 = self._web_search("research_precedent",
                               _research_precedent_queries(_und), _rn,
                               used_as="record", pre_seq=_pre)"""
src = sub_once(src, PREP2_OLD, PREP2_NEW, "_research_web_prep precedent 前置")

DUEL_SIG_OLD = "    def _web_duel_arbitration(self, view) -> List[dict]:"
DUEL_SIG_NEW = ("    def _web_duel_arbitration(self, view, round_no: int = 0)"
                " -> List[dict]:")
src = sub_once(src, DUEL_SIG_OLD, DUEL_SIG_NEW, "_web_duel_arbitration +round_no")

DUEL_CALL_OLD = """        _res = self._web_search("duel_arbitration", _qs,
                                self._research_round_no(), used_as="arbitration")"""
DUEL_CALL_NEW = """        # [v1.23.1 遗留3] 真圈号（由 `_finalize_layer_common` 传 r_actual+1）。
        _res = self._web_search("duel_arbitration", _qs,
                                max(1, int(round_no or 1)),
                                used_as="arbitration")"""
src = sub_once(src, DUEL_CALL_OLD, DUEL_CALL_NEW, "对撞仲裁用真圈号")

META_SIG_OLD = ("    def _web_meta_clean_check(self, view, uncovered)"
                " -> List[dict]:")
META_SIG_NEW = ("    def _web_meta_clean_check(self, view, uncovered,\n"
                "                            round_no: int = 0) -> List[dict]:")
src = sub_once(src, META_SIG_OLD, META_SIG_NEW, "_web_meta_clean_check +round_no")

META_CALL_OLD = """        _res = self._web_search("meta_clean_check", _qs,
                                self._research_round_no(), used_as="clean_check")"""
META_CALL_NEW = """        # [v1.23.1 遗留3] 真圈号（同上）。
        _res = self._web_search("meta_clean_check", _qs,
                                max(1, int(round_no or 1)),
                                used_as="clean_check")"""
src = sub_once(src, META_CALL_OLD, META_CALL_NEW, "元层核对用真圈号")

HOOK_OLD = '''    def _web_evidence_hook(self, prop: dict, layer: int) -> List[dict]:
        """[W2] `research_evidence`：给「迁向 partial」的提案先配一次外部检索。"""
        _qs = _research_evidence_queries(prop)
        if not _qs:
            return []
        return self._web_search("research_evidence", _qs,
                                self._research_round_no(), used_as="evidence")'''
HOOK_NEW = '''    def _web_evidence_hook(self, prop: dict, layer: int) -> List[dict]:
        """[W2] `research_evidence`：给「迁向 partial」的提案先配一次外部检索。

        [v1.23.1 遗留3] `layer` 是 `update_deferrals` 传进来的**真圈号**
          （它两处调用点给的都是 `layer_no`）。原先这里忽略它、改用
          拆解序号 —— 配额口径又不对了。
        """
        _qs = _research_evidence_queries(prop)
        if not _qs:
            return []
        _rn = int(layer or 0) or 1        # 只在圈内被调；保险起见 ≥ 1
        return self._web_search("research_evidence", _qs, _rn,
                                used_as="evidence")'''
src = sub_once(src, HOOK_OLD, HOOK_NEW, "_web_evidence_hook 用真圈号")

FIN_OLD = """            if entry == "both":
                self._web_duel_arbitration(view)
            elif entry == "all":
                self._web_meta_clean_check(
                    view, list(getattr(view, "uncovered_aspects", None)
                               or []))"""
FIN_NEW = """            # [v1.23.1 遗留3] `r_actual` 是 0 基的最后一圈下标 ⇒ +1 得圈号。
            if entry == "both":
                self._web_duel_arbitration(view, r_actual + 1)
            elif entry == "all":
                self._web_meta_clean_check(
                    view, list(getattr(view, "uncovered_aspects", None)
                               or []), r_actual + 1)"""
src = sub_once(src, FIN_OLD, FIN_NEW, "_finalize_layer_common 传真圈号")

# =============================================================== 写回
out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 CRCRLF（多级转义中招）"
assert out.count(b"\r") == out.count(b"\r\n"), "出现裸 CR"
NEW.write_bytes(out)
print("[done] %s  %d 行" % (NEW.name, out.count(b"\n") + 1))

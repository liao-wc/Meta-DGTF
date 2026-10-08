# -*- coding: utf-8 -*-
"""[v1.23.0 W2] 研究层接入（decompose / evidence / precedent）+ W# 编号 + 引用门 + 硬约束。

按 `_v123_taskbook.md` 执行，含 [修正 B1]（`_citation_table` 收 W# 提到本阶段）。
两条通道（serial / parallel）共用**同一个实现** `_research_decompose_with_web`，
不各写一份。幂等：哨兵串。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.23.0.py"
SENTINEL = "[v1.23.0 W2]"

src = TARGET.read_bytes().decode("utf-8")
assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF"
src = src.replace("\r\n", "\n")
if SENTINEL in src:
    print("== 已打过 W2 补丁，跳过 =="); sys.exit(0)


def sub_once(text, old, new, tag):
    n = text.count(old)
    assert n == 1, f"[{tag}] 锚点出现 {n} 次（应为 1）"
    return text.replace(old, new)


# =============================================================== 1 Pool 字段
P_OLD = (
    '    # 本次是否授权锚点作为**可引用对象**（进 _citation_table）。\n'
    '    # ★ 默认 False：进了引用表就自动获得支撑 →decidable 的资格\n'
    '    #   （apply_decidability_change 只拦「全是 d_ 开头」的一种情况），\n'
    '    #   那是**行为变化**，不是加性。先量后改。\n'
    '    anchor_as_evidence: bool = False\n'
)
P_NEW = (
    P_OLD
    + '    # ---- [v1.23.0 W2] 联网检索（W#）。与 anchors（X#，事先落盘）**分开**。\n'
    '    #   为什么单独一组字段而不是复用 anchors：锚点是**冻结事实**\n'
    '    #   （可复现、tier 已定），联网是**运行时活检索**（质量不稳、\n'
    '    #   tier 只给初值）。混在一组里，`_citation_table` 就分不出该按\n'
    '    #   哪套纪律约束。\n'
    '    web_results: List[dict] = field(default_factory=list)\n'
    '    web_errors: List[dict] = field(default_factory=list)\n'
    '    # 本次是否授权 W# 作为**可引用对象**（进 _citation_table）。\n'
    '    # ★ 默认 False；由 web_search.as_evidence ∈ {evidence, gate} 打开。\n'
    '    #   即便进了表，W# 也**只允许支撑 →partial**（硬约束见\n'
    '    #   apply_decidability_change 里的 W# 特例）。\n'
    '    web_as_evidence: bool = False\n'
)
src = sub_once(src, P_OLD, P_NEW, "Pool 字段")

# =============================================================== 2 模块级助手
HELPERS = '''# ============================================================
# [v1.23.0 W2] 联网 · 研究层接入的模块级助手
# ============================================================
def _next_web_id(pool) -> str:
    """W# 编号（跨层全局唯一）。"""
    return "W" + str(len(getattr(pool, "web_results", None) or []) + 1)


def _web_evidence_gate(cfg) -> bool:
    """`web_search.as_evidence` 是否属于「允许 W# 进引用表」的两档。

    ★ 与 `_anchor_tier`（external_anchor 的五档）同款纪律：未知取值 → 关，
      不静默放开。「进了引用表就能作证据」是行为变化，不是加性。
    """
    _a = str(((cfg or {}).get("web_search") or {}).get("as_evidence", "")
             or "").strip().lower()
    return _a in ("evidence", "gate")


def _research_decompose_queries(question: str, pool) -> List[str]:
    """[W2·research_decompose] 拆解前的检索词：原问题 + 池内结构型印记补强。"""
    _q = str(question or "").strip()
    if not _q:
        return []
    out = [_q[:200]]
    for a in (getattr(pool, "amps", None) or [])[:2]:
        _d = str((a or {}).get("desc", "")).strip()
        if _d:
            out.append((_q[:80] + " " + _d[:80])[:200])
    return [x for x in out if x.strip()][:2]


def _research_evidence_queries(prop: dict) -> List[str]:
    """[W2·research_evidence] 给一条「迁向 partial」的提案配检索词。

    ★ 只对 `to == "partial"` 发 —— `→undecidable` 是「答不出」的结论，
      检索命中与否**不能**作为它成立的依据（方向反了）。
    """
    if str((prop or {}).get("to", "")).strip().lower() != "partial":
        return []
    _sq = str((prop or {}).get("_sq_text") or "").strip()
    if not _sq:
        return []
    return [_sq[:120]]


def _research_precedent_queries(und_aspects) -> List[str]:
    """[W2·research_precedent] 把结构标签为 [外] 的不可判定方面改造成存在性问句。"""
    out: List[str] = []
    for a in (und_aspects or []):
        s = str(a).strip()
        if s.startswith("[外]"):
            out.append(
                ("是否存在 " + s[3:].strip()[:80] + " 的官方指引？")[:160])
        if len(out) >= 3:
            break
    return out


def _web_digest_block(results) -> str:
    """把 W# 渲染成**参照**段（不是内容）。空 → 空串（加性：不开时逐字不变）。"""
    _r = [x for x in (results or []) if str((x or {}).get("claim", "")).strip()]
    if not _r:
        return ""
    lines = ["",
             "【外部检索摘要】（★ **参照**，不是内容；不得当候选、"
             "不得据此改写问题）"]
    for x in _r[:6]:
        lines.append("- " + str(x.get("id", "W?")) + "（"
                     + str(x.get("stage", "")) + "，tier "
                     + str(x.get("tier", 3)) + "）："
                     + str(x.get("claim", ""))[:200])
    lines.append("★ 以上**不是**本层产物；只在判断「已知 / 未知」边界时参考。")
    return "\\n".join(lines)


'''
A2 = 'def _compute_rephrase_streak(view, state) -> int:\n    """[v122 P6 G6.3] 「ing 连续几圈在复述」的唯一实现。\n'
src = sub_once(src, A2, HELPERS + A2, "模块级助手")

# =============================================================== 3 _citation_table 收 W#
C_OLD = (
    '            _xi += 1\n'
    '            out.append((f"X{_xi}", str(_xa.get("claim", ""))))\n'
    '            if _xi >= 12:\n'
    '                break\n'
    '    return [(c, t) for c, t in out if str(t).strip()]\n'
)
C_NEW = (
    '            _xi += 1\n'
    '            out.append((f"X{_xi}", str(_xa.get("claim", ""))))\n'
    '            if _xi >= 12:\n'
    '                break\n'
    '    # [v1.23.0 W2] 联网编号 W#（[修正 B1]：本项从 W4 提前到 W2 ——\n'
    '    #   否则 W2 的判据「evidence=[W#] → partial 应 applied」恒 rejected）。\n'
    '    #   ★ 与 X# 同款纪律：只在**授权**时进表；进表后能不能作证据，\n'
    '    #     由 apply_decidability_change 的 W# 特例决定（只许 →partial）。\n'
    '    if getattr(pool, "web_as_evidence", False):\n'
    '        _wi = 0\n'
    '        for _w in (getattr(pool, "web_results", None) or []):\n'
    '            if not str((_w or {}).get("claim", "")).strip():\n'
    '                continue\n'
    '            _wi += 1\n'
    '            out.append((str(_w.get("id") or ("W" + str(_wi))),\n'
    '                        str(_w.get("claim", ""))[:120]))\n'
    '            if _wi >= 20:\n'
    '                break\n'
    '    return [(c, t) for c, t in out if str(t).strip()]\n'
)
src = sub_once(src, C_OLD, C_NEW, "citation_table")

# =============================================================== 4 W# 硬约束
D_OLD = (
    '    if ent["to"] != "undecidable" and all(\n'
    '            str(r.get("resolved_to", "")).startswith("d_")\n'
    '            for r in resolved):\n'
    '        return _reject("债务编号只能作为迁向不可判定的依据，"\n'
    '                       f"不能用来支撑 →{ent[\'to\']}")\n'
)
D_NEW = (
    D_OLD
    + '    # [v1.23.0 W2] 联网编号 W# 的硬约束：**只允许支撑 →partial**。\n'
    '    #   · 不许支撑 →decidable：网络检索质量不稳（tier 只给初值、\n'
    '    #     新域名要人确认），拿它把「可判定的位置」占掉比"没证据"更危险；\n'
    '    #   · 不许支撑 →undecidable：「能查到」证明不了「答不出」，方向反了。\n'
    '    #   ★ 口径用 `all(...)`（与上面 d_ 那条一致）：证据里**混了**池内\n'
    '    #     编号时，池内那条才是承重墙 —— W# 只是旁证，不因此驳整条提案。\n'
    '    if ent["to"] != "partial" and all(\n'
    '            str(r.get("resolved_to", "")).startswith("W")\n'
    '            for r in resolved):\n'
    '        return _reject("联网编号（W#）只能支撑 →partial，不能支撑 "\n'
    '                       f"→{ent[\'to\']}（网络检索质量不稳；"\n'
    '                       "且「能查到」证明不了「答不出」）")\n'
)
src = sub_once(src, D_OLD, D_NEW, "W# 硬约束")

# =============================================================== 5 update_deferrals 钩子
E0_OLD = 'def update_deferrals(pool, view, layer: int, cfg: dict) -> dict:\n'
E0_NEW = ('def update_deferrals(pool, view, layer: int, cfg: dict,\n'
          '                     web_hook=None) -> dict:\n')
src = sub_once(src, E0_OLD, E0_NEW, "update_deferrals 签名")

E1_OLD = (
    '    for pr in props:\n'
    '        try:\n'
    '            sid = int(pr["sub_id"])\n'
    '        except (TypeError, ValueError):\n'
    '            continue\n'
    '        ent = apply_decidability_change(\n'
)
E1_NEW = (
    '    for pr in props:\n'
    '        try:\n'
    '            sid = int(pr["sub_id"])\n'
    '        except (TypeError, ValueError):\n'
    '            continue\n'
    '        # [v1.23.0 W2] `research_evidence` 接入点：提案在**应用之前**\n'
    '        #   先做一次外部证据检索（只对 →partial）。\n'
    '        #   ★ 检索**不改提案本身** —— 判定仍由下面这条唯一入口按证据做。\n'
    '        #   ★ hook 崩了只留痕，绝不把结算带走（它是一次锦上添花）。\n'
    '        if web_hook is not None:\n'
    '            try:\n'
    '                _pr2 = dict(pr)\n'
    '                _pr2["_sq_text"] = str(\n'
    '                    (sub_by_id.get(sid) or {}).get("question", ""))\n'
    '                web_hook(_pr2, layer)\n'
    '            except Exception as _ew:  # noqa: BLE001\n'
    '                logger_web.warning("[W-HOOK] %s", _ew)\n'
    '        ent = apply_decidability_change(\n'
)
src = sub_once(src, E1_OLD, E1_NEW, "update_deferrals 钩子")

# =============================================================== 6 MetaDGTF 方法
METHODS = '''    def _research_round_no(self) -> int:
        """[W2] 研究层的圈序号（拆解每圈发生一次，用它当配额口径的 round）。"""
        return int(getattr(self, "_web_prep_seq", 0) or 0)

    def _web_search(self, stage: str, queries, round_no: int,
                    used_as: str = "evidence") -> List[dict]:
        """[W2] 联网检索的**唯一实现**。返回这次真的收进来的 W# 列表。

        【做四件事】授权/配额（Gate）→ 检索（Client）→ 编号入池（W#）→
        失败留痕（独立 logger + pool.meta + pool.web_errors）。
        【enabled=False】调用点不必写 `if enabled`：本方法直接返回 []，
        且**一次 Gate 都不判**（零调用是可验证的）。
        """
        gate = getattr(self, "_web_gate", None)
        client = getattr(self, "_web_client", None)
        if gate is None or client is None:
            return []
        pool = self.pools.get("1")
        if pool is not None:
            # 引用授权门每次同步（配置在跑内不变，但显式摆在这里可读）。
            pool.web_as_evidence = _web_evidence_gate(self.config)
        out: List[dict] = []
        for q in [str(x) for x in (queries or []) if str(x).strip()]:
            ok, why = gate.allow(stage, int(round_no))
            if not ok:
                if pool is not None:
                    pool.meta.append("[W-SKIP] " + stage + "：" + str(why))
                break
            gate.note_call(stage, int(round_no))
            try:
                res, kind = client.search(q[:200])
            except Exception as exc:  # noqa: BLE001
                res, kind = [], "api_error"
                logger_web.warning("[W-EXC] %s", exc)
            if kind == "empty":
                # ★ 空结果 = 「外部确实没有」，是**终态**：不算失败、不降级。
                gate.note_success()
                if pool is not None:
                    pool.meta.append("[W-EMPTY] " + stage + " q=" + q[:60])
                continue
            if kind:
                gate.note_failure(kind)
                logger_web.warning("[W-%s] stage=%s q=%s", kind.upper(),
                                   stage, q[:80])
                if pool is not None:
                    pool.meta.append("[W-" + kind.upper() + "] " + stage
                                     + " q=" + q[:60])
                    pool.web_errors.append({
                        "stage": stage, "query": q[:120],
                        "kind": kind, "round": int(round_no)})
                continue
            gate.note_success()
            for it in res[:3]:
                wid = _next_web_id(pool) if pool is not None else "W?"
                item = {"id": wid, "stage": stage, "query": q[:120],
                        "claim": str((it or {}).get("claim", ""))[:400],
                        "url": str((it or {}).get("url", ""))[:300],
                        "source": str((it or {}).get("source", ""))[:200],
                        "tier": int((it or {}).get("tier", 3) or 3),
                        "used_as": used_as, "round": int(round_no)}
                if pool is not None:
                    pool.web_results.append(item)
                out.append(item)
        return out

    def _research_web_prep(self, question: str, _unused: int = 0) -> str:
        """[W2] 研究层拆解前的联网准备（**唯一实现**，两条通道共用）。

        做两类检索：`research_decompose`（已知/未知边界）+
        `research_precedent`（[外] 标签的存在性）。
        返回可注入 prompt 的**参照**串；`enabled=False` 时返回空串
        （⇒ prompt 逐字与 v1.22.2 相同，加性成立）。
        """
        if not bool((self.config.get("web_search") or {}).get("enabled")):
            return ""
        self._web_prep_seq = int(getattr(self, "_web_prep_seq", 0) or 0) + 1
        _rn = self._research_round_no()
        pool = self.pools.get("1")
        _r1 = self._web_search("research_decompose",
                               _research_decompose_queries(question, pool), _rn)
        _und = []
        _dr = getattr(self, "decidability_result", None)
        if isinstance(_dr, dict):
            _und = list(_dr.get("undecidable_aspects") or [])
        _r2 = self._web_search("research_precedent",
                               _research_precedent_queries(_und), _rn,
                               used_as="record")
        return _web_digest_block(_r1 + _r2)

    def _research_decompose_with_web(self, question: str, d0, zero_view,
                                     use_internal: bool):
        """[W2] 研究层拆解的**唯一实现**（串行 / 并行两条通道共用）。

        ★ 为什么必须收成一处：这段逻辑原先在 `_run_layer`(serial) 与
          `_b_pre_layer`(parallel) 里**各写一份**（本项目同类问题已 7 次）。
          加联网参照必然让两份分叉 —— 收口后两条通道的差异只剩「传哪个
          question / 哪个 view」。
        """
        _digest = self._research_web_prep(question)
        try:
            d0._web_digest = _digest
        except Exception:  # noqa: BLE001
            pass
        if use_internal:
            _zp = self.pools.get("0") or Pool()
            return d0._decompose_from_pool(question, _zp, zero_view), \\
                "修行池内部"
        return d0._decompose_question(question, self.decidability_result), \\
            "外部评估"

    def _web_evidence_hook(self, prop: dict, layer: int) -> List[dict]:
        """[W2] `research_evidence`：给「迁向 partial」的提案先配一次外部检索。"""
        _qs = _research_evidence_queries(prop)
        if not _qs:
            return []
        return self._web_search("research_evidence", _qs,
                                self._research_round_no(), used_as="evidence")

'''
M_OLD = (
    '    def _write_tri_stability(self, subs, mode: str, from_votes: bool) -> None:\n'
)
src = sub_once(src, M_OLD, METHODS + M_OLD, "MetaDGTF 方法")

# =============================================================== 7 run() 造基建
R_OLD = '        self._load_anchors()\n'
R_NEW = (
    '        self._load_anchors()\n'
    '        # [v1.23.0 W2] 联网基础设施：**每跑造一套**（配额与连续失败都是\n'
    '        #   跑内状态，跨跑累积没有意义）。enabled=False 时 gate.allow()\n'
    '        #   恒 False ⇒ 零调用，与 v1.22.2 行为逐字相同。\n'
    '        self._web_gate, self._web_client = build_web_search(self.config)\n'
    '        self._web_prep_seq = 0\n'
)
src = sub_once(src, R_OLD, R_NEW, "run 基建")

# =============================================================== 8 摘要注入 prompt
# ★ `_decompose_normal` 与 `_decompose_hybrid` 的 user 块**逐字相同**（各 1 处），
#   所以这里是有意地一次替换 2 处 —— 摘要要同时进这两条拆解路径。
J1_OLD = (
    '        user = (f"【原始问题】\\n{question}\\n\\n"\n'
    '                f"【评估阶段识别的可判定方面】\\n{dec_hint}\\n\\n"\n'
    '                f"【评估阶段识别的不可判定方面】\\n{und_hint}")\n'
)
J1_NEW = (
    '        user = (f"【原始问题】\\n{question}\\n\\n"\n'
    '                f"【评估阶段识别的可判定方面】\\n{dec_hint}\\n\\n"\n'
    '                f"【评估阶段识别的不可判定方面】\\n{und_hint}"\n'
    '                # [v1.23.0 W2] 外部检索摘要（**参照**）。未开联网时\n'
    '                #   它是空串 ⇒ prompt 逐字不变（加性）。\n'
    '                + (getattr(self, "_web_digest", "") or ""))\n'
)
_n1 = src.count(J1_OLD)
assert _n1 == 2, "normal/hybrid 的 user 块命中 %d 次（应为 2）" % _n1
src = src.replace(J1_OLD, J1_NEW)
print("  已注入 normal + hybrid（2 处）")

J2_OLD = (
    '            f"【修行层 · ing 输出】\\n{ing_text or \'（此处未生）\'}"\n'
    '        )\n'
)
J2_NEW = (
    '            f"【修行层 · ing 输出】\\n{ing_text or \'（此处未生）\'}"\n'
    '            # [v1.23.0 W2] 外部检索摘要（**参照**）。空串 = 逐字不变。\n'
    '            + (getattr(self, "_web_digest", "") or "")\n'
    '        )\n'
)
src = sub_once(src, J2_OLD, J2_NEW, "注入 from_pool")

J3_OLD = '            raw = self.llm.call(system, f"【原始问题】\\n{question}",\n'
J3_NEW = ('            raw = self.llm.call(\n'
          '                system, f"【原始问题】\\n{question}"\n'
          '                + (getattr(self, "_web_digest", "") or ""),\n')
src = sub_once(src, J3_OLD, J3_NEW, "注入 koan")

# =============================================================== 9 两条通道收口
S_OLD = (
    '            if use_internal:\n'
    '                zero_pool = self.pools.get("0") or Pool()\n'
    '                subs = d0._decompose_from_pool(\n'
    '                    question, zero_pool, zero_view)\n'
    '                src_label = "修行池内部"\n'
    '            else:\n'
    '                subs = d0._decompose_question(\n'
    '                    question, self.decidability_result)\n'
    '                src_label = "外部评估"\n'
)
S_NEW = (
    '            # [v1.23.0 W2] 拆解 + 联网参照：**唯一实现**（两条通道共用）。\n'
    '            #   检索摘要只进 prompt，**不进子问题文本** —— 宪法级：\n'
    '            #   「输入是形状不是数据」。\n'
    '            subs, src_label = self._research_decompose_with_web(\n'
    '                question, d0, zero_view, use_internal)\n'
)
src = sub_once(src, S_OLD, S_NEW, "serial 收口")

S2_OLD = (
    '            if use_internal:\n'
    '                zero_pool = self.pools.get("0") or Pool()\n'
    '                subs = d0._decompose_from_pool(\n'
    '                    self._question, zero_pool, zero_view)\n'
    '                src_label = "修行池内部"\n'
    '            else:\n'
    '                subs = d0._decompose_question(\n'
    '                    self._question, self.decidability_result)\n'
    '                src_label = "外部评估"\n'
)
S2_NEW = (
    '            # [v1.23.0 W2] 与串行通道**同一个实现**（见\n'
    '            #   `_research_decompose_with_web` 的 docstring）。\n'
    '            subs, src_label = self._research_decompose_with_web(\n'
    '                self._question, d0, zero_view, use_internal)\n'
)
src = sub_once(src, S2_OLD, S2_NEW, "parallel 收口")

# =============================================================== 10 两处 update_deferrals 接钩子
HOOK_PAIRS = (
    ("serial",
     "                st = update_deferrals(\n"
     "                    self.pools[entry], view, layer_no, sp)\n",
     "                st = update_deferrals(\n"
     "                    self.pools[entry], view, layer_no, sp,\n"
     "                    web_hook=self._web_evidence_hook)\n"),
    ("parallel",
     "            st = update_deferrals(self.pools[entry], view, r, sp)\n",
     "            st = update_deferrals(self.pools[entry], view, r, sp,\n"
     "                                  web_hook=self._web_evidence_hook)\n"),
)
for _tag, _o, _nw in HOOK_PAIRS:
    _c = src.count(_o)
    assert _c == 1, "[%s] update_deferrals 调用点命中 %d 次（应为 1）" % (_tag, _c)
    src = src.replace(_o, _nw)
    print("  已接钩子：" + _tag)

# =============================================================== 写回
out = src.replace("\n", "\r\n")
b = out.encode("utf-8")
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert b.count(b"\r") == b.count(b"\r\n"), "出现裸 CR"
TARGET.write_bytes(b)
print("OK: v1.23.0 W2 补丁已写入")

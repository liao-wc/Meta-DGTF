# -*- coding: utf-8 -*-
"""
v1.21.74 -> v1.21.75

按外部评审方案（DeepSeek 分享 0lfxjgv2aws2xyu913）重做锚点接入：

  1. Pool.anchors   锚点成为**池对象**（原来只在 MetaDGTF 上挂着，池里看不见）
  2. _citation_table 打通：锚点可被 evidence 引用（编号 X#）
     ★ 但这**不是**评审说的"纯加性"——它给了锚点支撑 →decidable 的资格，
       所以默认关闭（as_evidence=False），先量后改。
  3. 圈循环里触发检索并入池（retriever=snapshot，零额外调用）
  4. 锚点摊进 _assess_decidability_from_pool_view（池判，不是外判）
  5. 分诊降级（triage）默认关 —— 评审自己要求"先量后改"
  6. 检索调用纳预算（v1.21.74 的收尾对照漏算，这里一并补）

不改：_normalize_decidability / _untraced_undecidable / _check_input_sanity
      （评审明确列为"不要碰"）
不加：confidence 0-1 数值字段（会被下游当可计算量，实际是主观标注；
      保留 kind 文字性质标注）
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.74.py"
DST = HERE / "元DGTF-V1.21.75.py"

# ---------------------------------------------------------------- 新代码块

# (A) Pool 字段
OLD_POOL_FIELD = (
    "    decidable_channel: dict = field(default_factory=dict)\n"
    "    undecidable_channel: dict = field(default_factory=dict)\n"
    "\n"
    "    def merge(self, amps, threads, meta, probes=None, suspensions=None):\n"
)
NEW_POOL_FIELD = (
    "    decidable_channel: dict = field(default_factory=dict)\n"
    "    undecidable_channel: dict = field(default_factory=dict)\n"
    "    # [v1.21.75] 外部锚点**入池**。原来只在 MetaDGTF 上挂一份，池里\n"
    "    #   看不见 —— 于是候选/对偶判断/ing 全读不到它，evidence 也引不了。\n"
    "    #   入池后它是池对象，能被渲染、能被引用。\n"
    "    anchors: List[dict] = field(default_factory=list)\n"
    "    # 本次是否授权锚点作为**可引用对象**（进 _citation_table）。\n"
    "    # ★ 默认 False：进了引用表就自动获得支撑 →decidable 的资格\n"
    "    #   （apply_decidability_change 只拦「全是 d_ 开头」的一种情况），\n"
    "    #   那是**行为变化**，不是加性。先量后改。\n"
    "    anchor_as_evidence: bool = False\n"
    "\n"
    "    def merge(self, amps, threads, meta, probes=None, suspensions=None):\n"
)

# (B) to_dict —— 条件挂键（关闭态逐字同前版）
OLD_TO_DICT = (
    "                \"decidable_channel\": self.decidable_channel,\n"
    "                \"undecidable_channel\": self.undecidable_channel}\n"
)
NEW_TO_DICT = (
    "                \"decidable_channel\": self.decidable_channel,\n"
    "                \"undecidable_channel\": self.undecidable_channel}\n"
    "        # [v1.21.75] 只在真有锚点时挂键 —— 关闭态 packed 与前版逐字相同。\n"
    "        #   （度量用的入池条数不在这里，无条件写在 external_anchor.pooled）\n"
    "        if self.anchors:\n"
    "            d[\"anchors\"] = self.anchors\n"
    "        return d\n"
)
# to_dict 原来是 `return {...}`，要改成 `d = {...}` —— 单独处理行首
OLD_TO_DICT_HEAD = "    def to_dict(self) -> dict:\n        return {\"amps\": self.amps, \"threads\": self.threads,\n"
NEW_TO_DICT_HEAD = "    def to_dict(self) -> dict:\n        d = {\"amps\": self.amps, \"threads\": self.threads,\n"

# (C) _citation_table 加 X#
OLD_CITE_TAIL = (
    "        if coll and coll != \"（此处未生）\":\n"
    "            out.append((\"ing\", coll))\n"
    "    return [(c, t) for c, t in out if str(t).strip()]\n"
)
NEW_CITE_TAIL = (
    "        if coll and coll != \"（此处未生）\":\n"
    "            out.append((\"ing\", coll))\n"
    "    # [v1.21.75] 外部锚点编号 X#。★ 只在 anchor_as_evidence 为真时进表：\n"
    "    #   进了表它就能被 apply_decidability_change 解析成证据，从而支撑\n"
    "    #   →decidable / →partial。这是**行为变化**，默认不给。\n"
    "    #   编号沿用现有单字母前缀风格（P#/A#/T#/S#/C#），不用评审建议的\n"
    "    #   X_001 —— 那个下划线风格会和债务编号 d_00X 混。\n"
    "    if getattr(pool, \"anchor_as_evidence\", False):\n"
    "        for _xi, _xa in enumerate(\n"
    "                (getattr(pool, \"anchors\", None) or [])[:12], 1):\n"
    "            out.append((f\"X{_xi}\", str(_xa.get(\"claim\", \"\"))))\n"
    "    return [(c, t) for c, t in out if str(t).strip()]\n"
)

# (D) 圈循环插入检索并入池
OLD_ROUND = (
    "            self._print_polarity_snapshot(pool, entry, layer_no)\n"
    "\n"
    "            if entry == \"0\" or entry == \"1\":\n"
)
NEW_ROUND = (
    "            self._print_polarity_snapshot(pool, entry, layer_no)\n"
    "            # [v1.21.75] 外部锚点：本圈检索并入池。\n"
    "            #   位置按评审建议 —— MetaDGTF 的圈循环里（`DGTF` 是纯\n"
    "            #   生成器，不该知道外部世界；调度归 MetaDGTF）。\n"
    "            self._anchor_round(entry, pool, r)\n"
    "\n"
    "            if entry == \"0\" or entry == \"1\":\n"
)

# (E) 池判：分诊 sys + 锚点 ctx
OLD_ING = (
    "        ing_text = str(view.collision or \"\")[:1500]\n"
    "\n"
    "        system = (\n"
)
NEW_ING = (
    "        ing_text = str(view.collision or \"\")[:1500]\n"
    "\n"
    "        # [v1.21.75] 锚点进池判（不是外判）。评审明确说：外判是「另一个\n"
    "        #   LLM 看问题」，跟锚点是两回事，别混 —— v1.21.73/74 恰恰混了，\n"
    "        #   两次跑动 claims 全判无对应。这里改接**池判**。\n"
    "        _triage_sys = self._anchor_triage_sys()\n"
    "        _anchor_ctx = self._anchor_view_ctx()\n"
    "\n"
    "        system = (\n"
)

OLD_TRIAGE_ANCHOR = (
    "            \"undecidable_aspects **只放\\\"原则判不出\\\"的**；未决的不要放进去。\\n\"\n"
    "            \"\\n\"\n"
    "            \"严格 JSON：\\n\"\n"
)
NEW_TRIAGE_ANCHOR = (
    "            \"undecidable_aspects **只放\\\"原则判不出\\\"的**；未决的不要放进去。\\n\"\n"
    "            + _triage_sys +\n"
    "            \"\\n\"\n"
    "            \"严格 JSON：\\n\"\n"
)

OLD_USER_TAIL = (
    "            f\"【ing 输出】\\n{ing_text or '（此处未生）'}\"\n"
    "        )\n"
)
NEW_USER_TAIL = (
    "            f\"【ing 输出】\\n{ing_text or '（此处未生）'}\"\n"
    "            + _anchor_ctx\n"
    "        )\n"
)

# (F) 预算纳管
OLD_BUDGET = (
    "        b = int(getattr(self, \"_call_budget\", 0) or 0)\n"
    "        if b <= 0:\n"
    "            return False\n"
    "        return int(getattr(self.llm, \"total_calls\", 0) or 0) >= b\n"
)
NEW_BUDGET = (
    "        b = int(getattr(self, \"_call_budget\", 0) or 0)\n"
    "        if b <= 0:\n"
    "            return False\n"
    "        # [v1.21.75] 锚点检索调用也计入预算（v1.21.73/74 漏算：收尾对照\n"
    "        #   那次调用发生在打包阶段，压根不在圈循环内，守卫看不见）。\n"
    "        used = (int(getattr(self.llm, \"total_calls\", 0) or 0)\n"
    "                + int(getattr(self, \"_anchor_calls\", 0) or 0))\n"
    "        return used >= b\n"
)

# (G) 产物渲染：入池计数
OLD_RENDER = (
    "                            f\"（用到锚点 {_sm.get('anchor_used', 0)}/\"\n"
    "                            f\"{_ea.get('anchors', 0)}）\\n\\n\")\n"
)
NEW_RENDER = (
    "                            f\"（用到锚点 {_sm.get('anchor_used', 0)}/\"\n"
    "                            f\"{_ea.get('anchors', 0)}）\\n\\n\")\n"
    "                f.write(f\"**锚点入池**：{_ea.get('pooled', 0)} 条\"\n"
    "                        f\"（{'已获证据资格' if _ea.get('as_evidence')\n"
    "                            else '仅记录，不作证据'}）\\n\\n\")\n"
)

# (H) 配置新增键
OLD_CFG = "        \"crosscheck\": True,\n"
NEW_CFG = (
    "        \"crosscheck\": True,\n"
    "        # [v1.21.75] 每圈投放几条（模拟逐步检索；snapshot 模式零调用）\n"
    "        \"per_round\": 2,\n"
    "        # ★ 是否授权锚点进引用表、从而可支撑 →decidable。默认关（先量后改）\n"
    "        \"as_evidence\": False,\n"
    "        # ★ 分诊降级（undecidable 因「信息不足」降为 decidable）。默认关\n"
    "        \"triage\": False,\n"
    "        # 检索后端。当前只有 snapshot 真实现，其它取值抛错不静默降级\n"
    "        \"retriever\": \"snapshot\",\n"
)

# (I) 新方法：插在 _load_anchors 定义之前
OLD_LOAD_DEF = "    def _load_anchors(self) -> List[dict]:\n"

NEW_METHODS = '''    # ---------------------------------------------------------- 检索适配层
    def _anchor_round(self, entry: str, pool: "Pool", rno: int) -> None:
        """[v1.21.75] 本圈检索 → 锚点入池。

        ★ 当前 `retriever=\"snapshot\"` **零额外调用**：锚点已在 run 开头
          一次性读进来（`_load_anchors`），这里只按 `per_round` 配额**分圈
          投放**，模拟"逐步检索"的节奏，顺便让不同圈看到不同锚点。

        为什么不做成真联网：引擎现在没有联网能力。**假装搜过比承认没搜
        更糟** —— 所以非 snapshot 的取值一律抛错留痕，不静默降级。

        元层（all）不检索 —— 它的活是清算，不是核对。
        """
        cfg = self.config.get("external_anchor") or {}
        if not cfg.get("enabled") or entry == "all" or not self._anchors:
            return
        per = int(cfg.get("per_round", 2) or 0)
        if per <= 0:
            return
        try:
            queries = self._build_anchor_queries(entry, pool)
            self._retrieve_anchors(queries)
        except Exception as exc:
            # 宪法级：失败必须留痕，不静默跳过
            self._anchor_err = f"锚点检索失败（第 {rno + 1} 圈）：{exc}"
            logger.warning("外部锚点检索失败：%s", exc)
            pool.meta.append(f"[外部锚点] 检索失败：{exc}")
            return
        already = {str(a.get("id")) for a in (pool.anchors or [])}
        rest = [a for a in self._anchors
                if str(a.get("id")) not in already]
        picked = rest[:per]
        for a in picked:
            pool.anchors.append(dict(a))
        pool.anchor_as_evidence = bool(cfg.get("as_evidence", False))
        if picked:
            pool.meta.append(
                f"[外部锚点] 第 {rno + 1} 圈入池 {len(picked)} 条"
                f"（累计 {len(pool.anchors)}，"
                f"{'作证据' if pool.anchor_as_evidence else '仅记录'}）")
        self.vp(f"   ⚓ 锚点入池 +{len(picked)}"
                f"（累计 {len(pool.anchors)}）")

    def _build_anchor_queries(self, entry: str, pool: "Pool") -> List[str]:
        """[v1.21.75] 本圈"该查什么"。

        按评审建议，query 从池里现成的东西取，不额外造：
          · 研究层(1)：sub_questions 里 status=open 的前 2 条
          · 对撞层(both)：未清偿债务的 revisit_condition（"缺什么"就是 query）
          · 修行层(0)：probes / 悬空线头
        snapshot 模式下这些 query **不发起调用**，只留痕（将来接真检索时
        接口已经在这里了）。
        """
        out: List[str] = []
        if entry == "1":
            for sq in (pool.sub_questions or []):
                if str(sq.get("status", "")).lower() in ("open", ""):
                    q = str(sq.get("question", "")).strip()
                    if q:
                        out.append(q)
                if len(out) >= 2:
                    break
        elif entry == "both":
            for d in (pool.deferrals or []):
                if d.get("status") == "deferred":
                    q = str(d.get("revisit_condition", "")).strip()
                    if q:
                        out.append(q)
                if len(out) >= 2:
                    break
        else:
            for p in (pool.probes or [])[:2]:
                q = str(p.get("question", "")).strip()
                if q:
                    out.append(q)
        return out

    def _retrieve_anchors(self, queries: List[str]) -> List[dict]:
        """[v1.21.75] 检索适配层。

        ★ 当前**只有一个真实现**：`snapshot`。其它取值抛错留痕，
          不静默降级 —— 留给将来接真搜索 API 的接口位，但现在不假装。
        """
        cfg = self.config.get("external_anchor") or {}
        mode = str(cfg.get("retriever") or "snapshot").strip().lower()
        if mode != "snapshot":
            raise RuntimeError(
                f"external_anchor.retriever={mode!r} 尚未实现"
                f"（当前只有 'snapshot'）；不静默降级")
        return list(self._anchors or [])

    def _anchor_pooled_total(self) -> int:
        """本次各层池子里累计入池的锚点条数（不去重，如实报）。"""
        n = 0
        for p in (self.pools or {}).values():
            n += len(getattr(p, "anchors", None) or [])
        return n

    def _anchor_triage_sys(self) -> str:
        """[v1.21.75] 分诊判据段（triage 默认关 —— 先量后改）。"""
        cfg = self.config.get("external_anchor") or {}
        if not cfg.get("enabled") or not cfg.get("triage"):
            return ""
        return (
            "\\n"
            "[v1.21.75] 【外部锚点分诊】\\n"
            "若一条 undecidable 的理由是「信息不足 / 需外部动作」，\\n"
            "而【外部锚点】里**有**能回答它的材料 → 该条不算不可判定，\\n"
            "降为 decidable 或 partial。\\n"
            "若理由是「自指循环 / 无共同参照系 / 本体论判断」 → 检索无关，\\n"
            "**保持 undecidable**，不许降级。\\n"
            "★ 只在这两种情况里动；其余一律不动。\\n"
        )

    def _anchor_view_ctx(self) -> str:
        """[v1.21.75] 摊进池判 prompt 的锚点块（空串 = 一个字都不加）。"""
        cfg = self.config.get("external_anchor") or {}
        if not cfg.get("enabled"):
            return ""
        pool = (self.pools or {}).get("0")
        anchors = getattr(pool, "anchors", None) or []
        if not anchors:
            return ""
        lines = "\\n".join(
            f"  X{i}: {str(a.get('claim', ''))[:100]}"
            f"（源：{str(a.get('source', ''))[:40]}）"
            for i, a in enumerate(anchors[:10], 1))
        return ("\\n\\n【外部锚点（本圈已入池 "
                + str(len(anchors)) + " 条）】\\n" + lines
                + ("\\n（这些锚点**仅作对照**，你不必迁就它们；"
                   "判据仍以池内形状为准）" if not cfg.get("triage")
                   else "\\n（已开启分诊：按上面的分诊判据处理）"))

'''

# (J) packed 里加度量字段（无条件写）
OLD_PACK_KEYS = (
    "            \"retriever\": (self._anchor_source or {}).get(\"retriever\", \"\"),\n"
)
NEW_PACK_KEYS = (
    "            \"retriever\": (self._anchor_source or {}).get(\"retriever\", \"\"),\n"
    "            # [v1.21.75] 入池度量 —— **无条件写**（0 也写），否则分不清\n"
    "            #   「入池了 0 条」和「没这个字段」。\n"
    "            \"pooled\": self._anchor_pooled_total(),\n"
    "            \"as_evidence\": bool((self.config.get(\"external_anchor\")\n"
    "                                  or {}).get(\"as_evidence\", False)),\n"
    "            \"anchor_calls\": int(getattr(self, \"_anchor_calls\", 0) or 0),\n"
)

# ---------------------------------------------------------------- 执行


def main() -> None:
    raw = SRC.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "源文件不是纯 CRLF"
    t = raw.decode("utf-8").replace("\r\n", "\n")
    lines = t.split("\n")
    assert not any("\n" in l for l in lines)

    def sub1(old: str, new: str, tag: str) -> None:
        nonlocal t
        c = t.count(old)
        assert c == 1, f"[{tag}] 锚点命中 {c} 次，应为 1"
        t = t.replace(old, new)
        print(f"  [{tag}] ✓")

    print("打补丁：")
    sub1(OLD_POOL_FIELD, NEW_POOL_FIELD, "A Pool.anchors")
    sub1(OLD_TO_DICT_HEAD, NEW_TO_DICT_HEAD, "B1 to_dict 头")
    sub1(OLD_TO_DICT, NEW_TO_DICT, "B2 to_dict 尾")
    sub1(OLD_CITE_TAIL, NEW_CITE_TAIL, "C 引用表 X#")
    sub1(OLD_ROUND, NEW_ROUND, "D 圈循环检索")
    sub1(OLD_ING, NEW_ING, "E1 池判 ctx")
    sub1(OLD_TRIAGE_ANCHOR, NEW_TRIAGE_ANCHOR, "E2 分诊 sys")
    sub1(OLD_USER_TAIL, NEW_USER_TAIL, "E3 池判 user")
    sub1(OLD_BUDGET, NEW_BUDGET, "F 预算纳管")
    sub1(OLD_RENDER, NEW_RENDER, "G 产物渲染")
    sub1(OLD_CFG, NEW_CFG, "H 配置新键")
    sub1(OLD_PACK_KEYS, NEW_PACK_KEYS, "J 入池度量")

    # 新方法插在 _load_anchors 之前
    c = t.count(OLD_LOAD_DEF)
    assert c == 1, f"_load_anchors 定义命中 {c} 次"
    t = t.replace(OLD_LOAD_DEF, NEW_METHODS + OLD_LOAD_DEF)
    print("  [I 新方法] ✓")

    # 版本号两处
    c = t.count("元 DGTF · v1.21.74")
    assert c == 1, f"标题版本号命中 {c} 次"
    t = t.replace("元 DGTF · v1.21.74", "元 DGTF · v1.21.75")
    c = t.count('__version__ = "1.21.74"')
    assert c == 1, f"__version__ 命中 {c} 次"
    t = t.replace('__version__ = "1.21.74"', '__version__ = "1.21.75"')
    print("  [版本号] ✓")

    # changelog：插在 v1.21.74 段之前
    idx = next(i for i, l in enumerate(t.split("\n"))
               if "v1.21.74" in l)
    lines = t.split("\n")
    entry = [
        "v1.21.75 ── 按外部评审方案**重做**锚点接入（接入点从「外判」改到「池」）",
        "",
        "  ★ 前提：v1.21.73/74 把锚点塞进了 `_assess_decidability`（外判，",
        "    题面级）。评审明确列为「不要碰」——外判是另一个 LLM 看问题，锚点是",
        "    外部事实，两回事。两次真跑 claims 全判「无对应」印证了这个判断。",
        "",
        "  1. `Pool.anchors` —— 锚点成为**池对象**。原来只在 MetaDGTF 上挂一份，",
        "     池里看不见，候选/对偶/ing 全读不到，evidence 也引不了。",
        "  2. `_citation_table` 打通 `X#` 编号，锚点可被证据引用。",
        "     ★ 评审把这步写成「纯加性」，**它不是**：进了引用表就自动获得支撑",
        "       →decidable 的资格（`apply_decidability_change` 只拦「全是 d_ 开头」一种情况）。所以默认关（`as_evidence=False`），先量后改。",
        "     编号用 `X1..Xn` 而非评审建议的 `X_001`：现有风格是 P#/A#/T#/S#/C#，",
        "     `X_001` 的下划线会和债务编号 `d_00X` 混。",
        "  3. 圈循环里触发检索并入池（`MetaDGTF._run_layer`，`DGTF` 保持纯生成器）。",
        "     ★ `retriever` 目前**只有 `snapshot` 一个真实现**（零额外调用）；",
        "     其它取值抛错留痕，**不静默降级** —— 引擎没有联网能力，假装搜过",
        "     比承认没搜更糟。分圈投放 `per_round` 条模拟逐步检索。元层不检索。",
        "  4. 锚点摊进 `_assess_decidability_from_pool_view`（池判）+ 分诊判据。",
        "     分诊（`triage`）**默认关**，评审自己要求「先量后改」。",
        "  5. 检索调用纳预算 —— v1.21.73/74 的收尾对照发生在打包阶段，压根不在",
        "     圈循环内，守卫看不见（评审点名的坑，实测确认漏算）。",
        "",
        "  不改：`_normalize_decidability` / `_untraced_undecidable` /",
        "      `_check_input_sanity`（评审列为「不要碰」，实测均未动）。",
        "  不加：`confidence: 0.0-1.0`。给了数字下游就会当可计算量用，实际那是",
        "      主观标注；保留 `kind` 文字性质标注（行业媒体转述/企业自述/设备商",
        "      口径），判读时按来源打折这件事不会因为写了个 0.7 就变客观。",
        "",
        "  验证：关闭态 packed 键集合 / prompt / 产物文案与 v1.21.74 **逐字相同**",
        "     （加性成立）；开启态 `pooled` 无条件写入。`anchor_calls` 计入预算。",
        "",
    ]
    lines[idx:idx] = entry
    t = "\n".join(lines)

    # CRLF 往返
    out = t.replace("\n", "\r\n")
    bb = out.encode("utf-8")
    assert bb.count(b"\n") == bb.count(b"\r\n"), "输出不是纯 CRLF"
    DST.write_bytes(bb)
    print(f"\n已生成 {DST.name}：{len(bb)} 字符（v1.21.74 为 {len(raw)}）")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
v1.21.75 -> v1.21.76

来源：独立复核 7 项（2 硬伤 A + 5 中等 B）+ 上一轮未完成项 2 项（M1 / S1）。

  A1  `_anchor_round` 只挂在 serial 通道（`_run_layer`），B/C/D-H 七模式
      走 `_run_one_round_B` 等入口，压根没有锚点入池 → `pooled` 恒 0。
      改前实测：`self._anchor_round(` 全源码 1 处、`_before_round` 0 处。
      修：抽 `_before_round(entry, pool, layer_no)` 作统一圈前入口。
  A2  `_anchor_calls` **从未被赋值**（改前实测：2 处读、0 处写）——
      `_budget_exhausted` 里 `+ _anchor_calls` 是恒为 0 的挂空档，
      packed 里 `anchor_calls` 永远写 0。v1.21.75 宣称"检索调用纳预算"
      实际是空的。修：显式初始化 + 从 `_budget_exhausted` 移除 +
      在 `_anchor_crosscheck` 里做独立预算判断并真正自增。
  B1  changelog 说"重做锚点接入（接入点从外判改到池）"—— 实际外判接入点
      还在（`_assess_decidability` 仍收 anchors），是**新增**池接入点。
  B2  `per_round` 分圈投放，但池判只在评估阶段跑一次、只读第 1 圈池
      （2 条）—— 分圈的意义没有被池判看到。
  B3  `Pool.anchor_as_evidence` 内部赋值、**无任何出口**。
  B4  `_retrieve_anchors` 的返回值没人接（真正入池的是从 `self._anchors`
      里挑的）—— 死参数。
  B5  分诊判据写在 system 段，而 user 段（`_anchor_view_ctx`）说"按上面的
      分诊判据处理"—— 跨段引用。

  M1（上一轮未完成）`_anchor_claims` 只取成品答案 + 已答子问题，两处都是
      认识论层；引擎的领域论断在 `views[*].candidates`。三轮 6 题 claims
      全判「无对应」的根因在此。★ 这是 M1 口径变更，会改变对照结果。
  S1（上一轮未完成）`_check_input_sanity` 补「形似标准记号的非标准记号」
      判据 —— 负对照实测它漏报了 `P=PN`，而那正是它被造出来的原因。

不做：真联网 / 池判逐圈重跑 / confidence 数值 / 动 `_normalize_decidability`
      等三处 / 合并 auto_plan / 改 per_round 默认值。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.75.py"
DST = HERE / "元DGTF-V1.21.76.py"

R = []          # (tag, old, new)


def add(tag, old, new):
    R.append((tag, old, new))


# ---------------------------------------------------------------- A1
add("A1a 新增 _before_round",
    '''            self.vp(header)
            for b in bits:
                self.vp(b)

    def _check_structure_saturation(
''',
    '''            self.vp(header)
            for b in bits:
                self.vp(b)

    def _before_round(self, entry: str, pool: "Pool",
                      layer_no: int) -> None:
        """[v1.21.76 A1] 圈前统一动作：极性快照 + 锚点入池。

        ★ A1 根因：`_anchor_round` 原来只挂在 `_run_layer`（serial 通道）
          里。B/C/D-H 七个模式走的是 `_run_one_round_B` 等入口，它们只调
          `_print_polarity_snapshot`、不调 `_anchor_round` —— 于是**非
          serial 模式下锚点池恒为空**，`pooled` 永远是 0，收尾对照拿不到
          锚点。改前实测：全源码 `self._anchor_round(` 只有 1 处调用点，
          `_before_round` 0 处；`_run_one_round_B` 函数体含
          `_print_polarity_snapshot` 但不含 `_anchor_round`。

        做成一个方法而不是在两处各写一份，是为了防止这个坑再出现
        第十次（本项目「同一条逻辑两条通道各写一份」已发生过 7 次以上）。

        `layer_no` 是 **1-based**（调用方传圈号），`_anchor_round` 收
        **0-based**，这里做 -1 转换。
        """
        self._print_polarity_snapshot(pool, entry, layer_no)
        self._anchor_round(entry, pool, layer_no - 1)

    def _check_structure_saturation(
''')

add("A1b _run_layer 改走统一入口",
    '''            snap_threads = [str(t.get("desc", "")) for t in pool.threads]
            self._print_polarity_snapshot(pool, entry, layer_no)
            # [v1.21.75] 外部锚点：本圈检索并入池。
            #   位置按评审建议 —— MetaDGTF 的圈循环里（`DGTF` 是纯
            #   生成器，不该知道外部世界；调度归 MetaDGTF）。
            self._anchor_round(entry, pool, r)
''',
    '''            snap_threads = [str(t.get("desc", "")) for t in pool.threads]
            # [v1.21.76 A1] 统一走 `_before_round`（极性快照 + 锚点入池），
            #   与 B/C/D-H 通道共用同一处入口 —— 原先这里写死两行，
            #   别的通道只抄了快照那一行，锚点就漏了。
            self._before_round(entry, pool, layer_no)
''')

add("A1c _run_one_round_B 改走统一入口",
    '''        state["next_role"] = ""
        self._print_polarity_snapshot(pool, entry, r)

        self._b_pre_layer(entry, r)
''',
    '''        state["next_role"] = ""
        # [v1.21.76 A1] B 通道原来只打极性快照、**不入锚点** —— 补上统一
        #   入口（B 通道的 r 是 1-based，`_before_round` 内部做 -1 转换）。
        self._before_round(entry, pool, r)

        self._b_pre_layer(entry, r)
''')

# ---------------------------------------------------------------- A2
add("A2a __init__ 显式初始化 _anchor_calls",
    '''        self._anchor_report: Optional[dict] = None
        # v1.21.50 并行改造
''',
    '''        self._anchor_report: Optional[dict] = None
        # [v1.21.76 A2] 这个字段 v1.21.75 只在两处被 `getattr` **读**过
        #   （`_budget_exhausted` 与 packed 输出），**从来没有被写过** ——
        #   于是「把锚点调用计入预算」是一句空话，packed 里 `anchor_calls`
        #   永远写 0。现在显式初始化，并由 `_anchor_crosscheck` 真正自增。
        self._anchor_calls: int = 0
        # v1.21.50 并行改造
''')

add("A2b _budget_exhausted 只算 llm.total_calls",
    '''        b = int(getattr(self, "_call_budget", 0) or 0)
        if b <= 0:
            return False
        # [v1.21.75] 锚点检索调用也计入预算（v1.21.73/74 漏算：收尾对照
        #   那次调用发生在打包阶段，压根不在圈循环内，守卫看不见）。
        used = (int(getattr(self.llm, "total_calls", 0) or 0)
                + int(getattr(self, "_anchor_calls", 0) or 0))
        return used >= b
''',
    '''        b = int(getattr(self, "_call_budget", 0) or 0)
        if b <= 0:
            return False
        # [v1.21.76 A2] 这里**只算 `llm.total_calls`**。
        #   v1.21.75 曾在此 `+ _anchor_calls`，而那个字段当时从不被赋值
        #   （改前实测：2 处读、0 处写）—— 加了个恒为 0 的项，看着像修了
        #   其实没修，还让 packed 里的 `anchor_calls` 永远是 0。
        #   锚点的调用发生在**收尾对照**里（打包阶段，不在圈循环内），
        #   由 `_anchor_crosscheck` 自己做独立预算判断，不该混进这个守卫。
        return int(getattr(self.llm, "total_calls", 0) or 0) >= b
''')

add("A2c crosscheck 加独立预算判断",
    '''        if not (self.config.get("external_anchor") or {}).get("crosscheck", True):
            base["error"] = "crosscheck 已关闭，只载入锚点不做对照"
            return base
        a_lines = []
''',
    '''        if not (self.config.get("external_anchor") or {}).get("crosscheck", True):
            base["error"] = "crosscheck 已关闭，只载入锚点不做对照"
            return base
        # [v1.21.76 A2] 独立预算判断：收尾对照这次调用**不在圈循环里**，
        #   `_budget_exhausted` 那个守卫管不到它（v1.21.73/74 的漏算就在
        #   这里）。预算已用尽就跳过，并且**留痕** —— 不能让产物看起来
        #   "对照过了但没结果"。
        _b = int(getattr(self, "_call_budget", 0) or 0)
        if _b > 0 and int(getattr(self.llm, "total_calls", 0) or 0) >= _b:
            base["error"] = ("收尾对照跳过：预算已用尽（"
                             + str(getattr(self.llm, "total_calls", 0))
                             + "/" + str(_b) + "）")
            self.vp("\\n⚓ 外部锚点：" + base["error"])
            return base
        a_lines = []
''')

add("A2d crosscheck 调用前计数",
    '''        try:
            raw = self.llm.call(system, user, 0.2, 1800, json_mode=True,
                                stage="anchor_crosscheck")
''',
    '''        # [v1.21.76 A2] 真正把这次调用记进 `_anchor_calls`（v1.21.75 只读
        #   不写）。挂在"马上就要调用"的位置，而不是函数入口 ——
        #   上面那几条早退分支并没有真的花钱。
        self._anchor_calls = int(getattr(self, "_anchor_calls", 0) or 0) + 1
        base["anchor_calls"] = self._anchor_calls
        try:
            raw = self.llm.call(system, user, 0.2, 1800, json_mode=True,
                                stage="anchor_crosscheck")
''')

# ---------------------------------------------------------------- B3
add("B3 to_dict 挂 anchor_as_evidence",
    '''        if self.anchors:
            d["anchors"] = self.anchors
        return d
''',
    '''        if self.anchors:
            d["anchors"] = self.anchors
            # [v1.21.76 B3] 这个字段原来只有内部赋值、**没有任何出口** ——
            #   产物里看不出"锚点到底有没有被授权当证据"。跟着 anchors 一起
            #   挂（仍是加性：没锚点时一个键都不加）。
            d["anchor_as_evidence"] = self.anchor_as_evidence
        return d
''')

# ---------------------------------------------------------------- B4
add("B4a _anchor_round 检索层只在非 snapshot 走",
    '''        try:
            queries = self._build_anchor_queries(entry, pool)
            self._retrieve_anchors(queries)
        except Exception as exc:
            # 宪法级：失败必须留痕，不静默跳过
            self._anchor_err = f"锚点检索失败（第 {rno + 1} 圈）：{exc}"
            logger.warning("外部锚点检索失败：%s", exc)
            pool.meta.append(f"[外部锚点] 检索失败：{exc}")
            return
''',
    '''        # [v1.21.76 B4] `_retrieve_anchors` 原来是**死参数**：调了它、返回
        #   值没人接（真正入池的是下面从 `self._anchors` 里挑的那批）。
        #   现在只有**真检索后端**才走这一层；snapshot 是"零调用读快照"，
        #   不需要经过检索层，直接跳过（接口位保留给将来接真搜索 API）。
        _mode = str(cfg.get("retriever") or "snapshot").strip().lower()
        if _mode != "snapshot":
            try:
                queries = self._build_anchor_queries(entry, pool)
                self._retrieve_anchors(queries)
            except Exception as exc:
                # 宪法级：失败必须留痕，不静默跳过
                self._anchor_err = f"锚点检索失败（第 {rno + 1} 圈）：{exc}"
                logger.warning("外部锚点检索失败：%s", exc)
                pool.meta.append(f"[外部锚点] 检索失败：{exc}")
                return
''')

add("B4b _anchor_round docstring 补 B4",
    '''        为什么不做成真联网：引擎现在没有联网能力。**假装搜过比承认没搜
        更糟** —— 所以非 snapshot 的取值一律抛错留痕，不静默降级。

        元层（all）不检索 —— 它的活是清算，不是核对。
        """
''',
    '''        为什么不做成真联网：引擎现在没有联网能力。**假装搜过比承认没搜
        更糟** —— 所以非 snapshot 的取值一律抛错留痕，不静默降级。

        ★ [v1.21.76 B4] 检索层的返回值当前**不消费**：走真后端时
          `_retrieve_anchors(queries)` 只作"接口位 + 失败留痕"，
          真正入池的锚点是下面按 `per_round` 从已加载快照里挑的那批。
          这不是遗漏 —— snapshot 与真检索的入池路径目前是两条，
          等真后端落地时再合并（已在 changelog 的"刻意不做"里点名）。

        元层（all）不检索 —— 它的活是清算，不是核对。
        """
''')

# ---------------------------------------------------------------- B5
add("B5a _anchor_triage_sys 退化成空壳",
    '''    def _anchor_triage_sys(self) -> str:
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
''',
    '''    def _anchor_triage_sys(self) -> str:
        """[v1.21.76 B5] **空壳**，永远返回空串。

        原先这里返回分诊判据段，被拼进 `_assess_decidability_from_pool_view`
        的 **system**；而"分诊判据"要生效，模型必须同时看到 user 段里的
        锚点清单，于是 user 段写了句"按上面的分诊判据处理"—— 跨段引用，
        模型两段看到的顺序并不保证。

        现在判据整段挪到 `_anchor_view_ctx`（user 段），与锚点清单同处一
        段，不再有跨段引用。这个方法**保留**只为兼容外部脚本对它的调用，
        不删。
        """
        return ""
''')

add("B5b _anchor_view_ctx 整合分诊 + 说清可见性",
    '''    def _anchor_view_ctx(self) -> str:
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
''',
    '''    def _anchor_view_ctx(self) -> str:
        """[v1.21.76] 摊进池判 prompt 的锚点块（空串 = 一个字都不加）。

        ★ [B2] **可见性说清**：池判
          （`_assess_decidability_from_pool_view`）在一次运行里**只跑一次**
          （评估阶段），读的是**当时**的池 —— 也就是**第 1 圈结束后的
          状态**。所以哪怕 `per_round=2`、后面几圈还在继续入池，池判看到
          的永远是最早那 2 条（受 `max_items` 上限约束）。
          这不是 bug，是"评估先于展开"的结构决定的；写在这里免得下次
          有人以为"分圈投放 = 池判能看到全部"。

        ★ [B5] 分诊判据**挪到本段**（原来在 system 段，靠 user 段的
          "按上面的判据处理"跨段引用）。判据与锚点清单同段，模型一次读完。
        """
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
        body = ("\\n\\n【外部锚点（本圈已入池 "
                + str(len(anchors)) + " 条）】\\n" + lines)
        if cfg.get("triage"):
            body += (
                "\\n\\n【分诊判据（triage=on）】\\n"
                "若一条 undecidable 的理由是「信息不足 / 需外部动作」，\\n"
                "而上面【外部锚点】里**有**能回答它的材料 → 该条不算\\n"
                "不可判定，降为 decidable 或 partial。\\n"
                "若理由是「自指循环 / 无共同参照系 / 本体论判断」 → 检索\\n"
                "无关，**保持 undecidable**，不许降级。\\n"
                "★ 只在这两种情况里动；其余一律不动。\\n")
        else:
            body += ("\\n（这些锚点**仅作对照**，你不必迁就它们；"
                     "判据仍以池内形状为准）")
        return body
''')

# ---------------------------------------------------------------- M1
add("M1 _anchor_claims 纳入 candidates（领域事实层）",
    '''        """[v1.21.73] 收集本次要拿去对照的**结论条目**（只读，不改任何池）。

        取两处：各层 view 的 `decidable_product.answer`（成品答案）与研究
        池里状态为 answered 的子问题。都空就返回空列表 —— 产物里会写
        「本次没有可对照的结论条目」，而不是假装对照过。
        """
        out: List[str] = []
        for k in ("1", "both", "all", "0"):
            v = (results or {}).get(k)
            if v is None:
                continue
            dp = getattr(v, "decidable_product", None) or {}
            ans = str(dp.get("answer") or "").strip()
            if ans:
                out.append(ans[:300])
''',
    '''        """[v1.21.76 M1] 收集本次要拿去对照的**结论条目**（只读，不改任何池）。

        ★ M1 根因（v1.21.73/74/75 三轮、6 道题实测）：原来只取两处 ——
          各层 view 的 `decidable_product.answer` 与研究池里 answered 的
          子问题。这两处产出的全是**认识论层**的句子（"序关系能否单独
          裁决""能否用现有记录做区间估计"），而锚点在**领域事实层**
          （回本周期、稼动率红线、GDPR 条款）。两者永远不同层 ——
          所以 6/6 题、32 条 claims 全部判「无对应」，`anchor_used` 全 0。
          **那不是锚点没用，是抽取器取错了地方。**

          引擎真正的领域论断在 `views[*].candidates` 里（探索实测：同一份
          已跑完的 packed、同一份锚点、同一把尺，只换取值处 ——
          沾边 0/5 → 7/12，用到锚点 0 → 9/12）。

        ★ 口径变更声明：这是 **M1 口径变更**，会改变对照结果，按项目预
          注册纪律单独记录（`_anchor_prereg.json`）。candidates 排在
          最前 —— 它们是领域层，优先占满 `[:12]` 的配额。

        取三处（candidates 优先）：
          1. `views[*].candidates[].desc` —— 领域论断（本次新增）
          2. `views[*].decidable_product.answer` —— 成品答案
          3. 研究池 sub_questions 里 status=answered 的
        都空就返回空列表，产物里写「本次没有可对照的结论条目」。
        """
        out: List[str] = []
        for k in ("1", "0", "both", "all"):
            v = (results or {}).get(k)
            if v is None:
                continue
            for c in (getattr(v, "candidates", None) or []):
                if not isinstance(c, dict):
                    continue
                d = str(c.get("desc") or "").strip()
                if d:
                    out.append(d[:300])
        for k in ("1", "both", "all", "0"):
            v = (results or {}).get(k)
            if v is None:
                continue
            dp = getattr(v, "decidable_product", None) or {}
            ans = str(dp.get("answer") or "").strip()
            if ans:
                out.append(ans[:300])
''')

# ---------------------------------------------------------------- S1
add("S1 输入自检补『形似标准记号的非标准记号』判据",
    '''            "★ 只报真的悬空的。不要质疑正常术语，不要建议改写，\\n"
            "  不要把「这个问题很难」当成符号问题。\\n"
            "★ 没有问题就返回空数组，这是最常见的情况。\\n"
''',
    '''            "★ 只报真的悬空的。不要质疑正常术语，不要建议改写，\\n"
            "  不要把「这个问题很难」当成符号问题。\\n"
            "★ [v1.21.76 S1] 特别检查「**形似标准记号的非标准记号**」：\\n"
            "  看起来像某个公认缩写 / 标准编号 / 复杂度类，但拼出来并不\\n"
            "  存在的那种。例：把 NP 写成 PN、把 ISO 27001 写成\\n"
            "  ISO-27001x。这类**最容易被当成已知对象收下**，也最难被\\n"
            "  察觉 —— 一旦收下，后面所有推理都建在一个不存在的东西上。\\n"
            "  负对照实测（v1.21.75）：本检查项曾把 `P=PN` 判成\\n"
            "  「P与PN均为标准术语」而放行 —— 而它正是为 P=PN 那次\\n"
            "  事故才建的。所以这条必须显式写出来，不能靠通用判断。\\n"
            "★ 没有问题就返回空数组，这是最常见的情况。\\n"
''')

# ---------------------------------------------------------------- 版本号
add("版本号-标题",
    "元 DGTF · v1.21.75",
    "元 DGTF · v1.21.76")
add("版本号-__version__",
    '__version__ = "1.21.75"',
    '__version__ = "1.21.76"')

# ---------------------------------------------------------------- B1 changelog 措辞
add("B1a changelog 首行",
    "v1.21.75 ── 按外部评审方案**重做**锚点接入（接入点从「外判」改到「池」）",
    "v1.21.75 ── 按外部评审方案**新增池接入点**（原有的外判接入点保留、但不再是主接入点）")

add("B1b changelog 第 3 条",
    '''  3. 圈循环里触发检索并入池（`MetaDGTF._run_layer`，`DGTF` 保持纯生成器）。
     ★ `retriever` 目前**只有 `snapshot` 一个真实现**（零额外调用）；
     其它取值抛错留痕，**不静默降级** —— 引擎没有联网能力，假装搜过
     比承认没搜更糟。分圈投放 `per_round` 条模拟逐步检索。元层不检索。
''',
    '''  3. 圈循环里触发检索并入池（`MetaDGTF._run_layer`，`DGTF` 保持纯生成器）。
     ★ `retriever` 目前**只有 `snapshot` 一个真实现**（零额外调用）；
     其它取值抛错留痕，**不静默降级** —— 引擎没有联网能力，假装搜过
     比承认没搜更糟。分圈投放 `per_round` 条模拟逐步检索。元层不检索。
     ★ **这句当时是错的**：`_run_layer` 只是 serial 通道，B/C/D-H 七模式
     走别的入口，压根没接上 —— 已在 v1.21.76 A1 修（抽 `_before_round`）。
     另：`per_round` 分圈投放与「池判只跑一次」并不矛盾，但池判只看得见
     **第 1 圈**那批（受 `max_items` 约束），v1.21.76 B2 已写进 docstring。
''')

add("B1c changelog 第 5 条",
    '''  5. 检索调用纳预算 —— v1.21.73/74 的收尾对照发生在打包阶段，压根不在
     圈循环内，守卫看不见（评审点名的坑，实测确认漏算）。
''',
    '''  5. 检索调用纳预算 —— v1.21.73/74 的收尾对照发生在打包阶段，压根不在
     圈循环内，守卫看不见（评审点名的坑，实测确认漏算）。
     ★ **这条当时没实现**：它在 `_budget_exhausted` 里加了个 `+ _anchor_calls`，
     而那个字段从头到尾没被赋过值（实测 2 处读、0 处写）—— 恒为 0 的项。
     已在 v1.21.76 A2 重做（初始化 + 从守卫移除 + 收尾对照独立判断并自增）。
''')

add("B1d changelog 验证段",
    '''  验证：关闭态 packed 键集合 / prompt / 产物文案与 v1.21.74 **逐字相同**
     （加性成立）；开启态 `pooled` 无条件写入。`anchor_calls` 计入预算。
''',
    '''  验证：关闭态 packed 键集合 / prompt / 产物文案与 v1.21.74 **逐字相同**
     （加性成立）；开启态 `pooled` 无条件写入。
     ★ 「`anchor_calls` 计入预算」在 v1.21.75 是**名义上的**（该字段无写入），
     实际生效在 v1.21.76 A2。
''')


V76_LOG = [
    "v1.21.76 ── 独立复核（7 项）落地 + 上一轮两处未完成项",
    "",
    "  ★ 来源：对 v1.21.75 的独立复核，逐条**先核对再改**（7 项：2 硬伤 +",
    "    4 中等 + 1 组轻微）。**不改阈值/常量**，只修接线与出口。",
    "",
    "  【A1】`_anchor_round` 只挂在 serial 通道（硬伤）",
    "    改前实测：全源码 `self._anchor_round(` 只有 **1 处**调用点（在",
    "    `_run_layer` 里），`_before_round` **0 处**；`_run_one_round_B`",
    "    函数体含 `_print_polarity_snapshot` 但**不含** `_anchor_round`。",
    "    后果链：B/C/D-H 七模式跑动 → 锚点从不入池 → `pooled` 恒 0 →",
    "    收尾对照拿不到锚点 → 那条链上的所有锚点读数全是假的（不是",
    "    「没效果」，是「没接上」）。",
    "    做法：抽 `_before_round(entry, pool, layer_no)` 作**统一圈前入口**",
    "    （极性快照 + 锚点入池），`_run_layer` 与 `_run_one_round_B` 都调它。",
    "    做成一个方法而不是两处各写一份 —— 本项目「同一条逻辑两条通道",
    "    各写一份」已发生过 7 次以上，这是第 8 次的防线。",
    "    判据：`check_v76_anchor_two_channels`。",
    "",
    "  【A2】`_anchor_calls` 从未被赋值（硬伤）",
    "    改前实测：`_anchor_calls` 全源码出现 **2 次，都是读**",
    "    （`_budget_exhausted` 的 `getattr` + packed 输出），**0 次写**。",
    "    后果：v1.21.75 宣称的「检索调用纳预算」是**空转**——恒为 0 的项；",
    "    同时 packed 里 `anchor_calls` 永远写 0，看起来像「没花过钱」。",
    "    做法 3 条：① `__init__` 显式 `self._anchor_calls: int = 0`；",
    "    ② `_budget_exhausted` 里**只算 `llm.total_calls`**（收尾对照不在",
    "    圈循环内，不该混进这个守卫）；③ `_anchor_crosscheck` 里做**独立",
    "    预算判断**（用尽则跳过并留痕），并在真正发起调用前自增。",
    "    判据：`check_v76_anchor_calls`。",
    "",
    "  【B1】changelog 措辞与实现不符：原来写「重做锚点接入（接入点从外判",
    "    改到池）」，但外判接入点**还在**（`_assess_decidability` 仍收",
    "    anchors）—— 实际是**新增**池接入点。已改措辞。",
    "  【B2】`per_round` 分圈投放与「池判只跑一次」的关系没写清：池判在",
    "    评估阶段只跑一次、只读**第 1 圈**的池，后面几圈继续入池它看不到。",
    "    写进 `_anchor_view_ctx` docstring。",
    "  【B3】`Pool.anchor_as_evidence` 只有内部赋值、**无任何出口** ——",
    "    产物里看不出锚点有没有被授权当证据。已在 `to_dict` 里跟着",
    "    `anchors` 一起挂（仍是加性）。",
    "  【B4】`_retrieve_anchors` 的返回值是**死参数**（调了不接）。现在只有",
    "    真检索后端才走那一层，snapshot 直接跳过（接口位保留）。",
    "  【B5】分诊判据原先在 **system** 段，靠 user 段的「按上面的判据处理」",
    "    跨段引用。已整段挪进 `_anchor_view_ctx`（user 段），",
    "    `_anchor_triage_sys` 退化成空壳（保留，仅供外部脚本调用）。",
    "",
    "  【M1】上一轮未完成项：`_anchor_claims` 的**取值处**",
    "    三轮（v73/v74/v75）× 6 道题实测：32 条 claims 全部判「无对应」、",
    "    `anchor_used` 全 0。根因不是锚点没用 —— 是抽取器只取「成品答案 +",
    "    已答子问题」，两处都是**认识论层**；引擎的领域论断在",
    "    `views[*].candidates`。同一份已跑完的 packed、同一份锚点、同一把尺，",
    "    只换取值处：沾边 0/5 → **7/12**、用到锚点 0 → **9/12**。",
    "    今起 candidates 作为**第一来源**（领域层优先占满 12 条配额）。",
    "    ★ 这是 M1 口径变更，会改变对照结果，按预注册纪律单独记录。",
    "  【S1】上一轮未完成项：输入自检补「形似标准记号的非标准记号」判据。",
    "    负对照实测（v1.21.75）：`P=PN` 被判成「P与PN均为标准术语」放行。",
    "    —— 而 `_check_input_sanity` 正是为 `P=PN` 那次事故才建的。",
    "    它防住了别的笔误，唯独没防住让它诞生的案例。",
    "",
    "  刻意不做（6 条）：不加真联网 / 不让池判逐圈重跑 / 不加 confidence",
    "    数值 / 不动 `_normalize_decidability` 等三处 / 不合并 `auto_plan`",
    "    双实现 / 不动 `per_round` 默认值。",
    "",
    "  验证：前置量化探针 `_probe_v75_anchor.py`（P1..P6 对表）+ 冒烟 7 条",
    "    `check_v76_*`（各带负对照）+ 判别力验证（SRC 指回 v1.21.75 时",
    "    `check_v76_changelog_wording` 必须判红）+ 真跑 1 次 B 模式。",
    "    ★ **未跑 serial 对照** —— A1 修的是「B 也能跑」，serial 那条改前",
    "    就通，再跑一次买不到新信息。如实记录，不假装做过。",
    "",
]


def main() -> None:
    raw = SRC.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "源文件不是纯 CRLF"
    t = raw.decode("utf-8").replace("\r\n", "\n")
    assert "\r" not in t.replace("\r\n", "")

    for tag, old, new in R:
        c = t.count(old)
        assert c == 1, f"[{tag}] 锚点命中 {c} 次，应为 1"
        t = t.replace(old, new)
        print(f"  [{tag}] OK")

    # v1.21.76 changelog 段插在 v1.21.75 段之前
    anchor = "v1.21.75 ── 按外部评审方案**新增池接入点**"
    i = t.find(anchor)
    assert i > 0, "找不到 v1.21.75 段首"
    t = t[:i] + "\n".join(V76_LOG) + "\n" + t[i:]
    print("  [v1.21.76 changelog 段] OK")

    out = t.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\n") == out.count(b"\r\n"), "输出不是纯 CRLF"
    DST.write_bytes(out)
    print(f"\n已生成 {DST.name}：{len(out)} 字符（v1.21.75 为 {len(raw)}）")


if __name__ == "__main__":
    main()

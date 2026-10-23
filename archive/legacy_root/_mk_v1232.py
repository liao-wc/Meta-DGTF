# -*- coding: utf-8 -*-
"""[v1.23.2] 整体性检查 + §十 遗留收尾补丁。

分六段：
  S1 版本号两处
  S2 changelog（v1.23.2 段）
  S3 模块级：登记表常量 + `_ws_cfg` / `_thinking_stage` / tier 确认门
  S4 15 处 thinking stage 接线（审计发现它们**永远选不中**）
  S5 遗留4：W4 第三票 `used_as` arbitration → tri_vote
  S6 遗留3：tier 确认生效（`tier_confirmed` + W# tier 门，默认零差异）
  S7 遗留1：空票重试（`actions.tri_vote_retry_empty`）

纪律：read_bytes / write_bytes、CRLF 双向断言、锚点 count==1、
      换行一律 chr(10) 拼（不用字面反斜杠）。
"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE / "元DGTF-V1.23.1.py"
NEW = HERE / "元DGTF-V1.23.2.py"
NL = chr(10)

if NEW.exists():
    src = NEW.read_bytes().decode("utf-8")
    print("[reuse] %s 已存在，直接在其上打补丁" % NEW.name)
else:
    src = OLD.read_bytes().decode("utf-8")
    print("[copy] %s -> %s" % (OLD.name, NEW.name))
assert src.count("\r\n") == src.count("\n"), "源文件不是纯 CRLF"
src = src.replace("\r\n", "\n")


def sub_once(text, old, new, tag, expect=1):
    n = text.count(old)
    assert n == expect, "[%s] 锚点命中 %d 次（应为 %d）" % (tag, n, expect)
    print("  · " + tag)
    return text.replace(old, new)


# =============================================================== S1 版本
if "元 DGTF · v1.23.2" not in src:
    src = sub_once(src, "元 DGTF · v1.23.1", "元 DGTF · v1.23.2", "S1 docstring 标题")
    src = sub_once(src, '__version__ = "1.23.1"', '__version__ = "1.23.2"',
                   "S1 __version__")
else:
    print("  · S1 版本已改，跳过")

# =============================================================== S2 changelog
CL_OLD = "v1.23.1 ── 遗留收尾（真圈号 / tier 提案待审 / 三场景 + 三票正交度实证）"
CL_NEW = """v1.23.2 ── 整体性检查 + `v1231_报告.md` §十 遗留全清

  【整体审计】新增 `_probe_v1232_audit.py`：对**整份工程**做 8 类机械检查
    （出口完整性 / 死类 / 白名单四处一致 / 版本一致 / 宪法红线 / 圈号口径 /
    used_as 枚举 / 配置键可达性），自带 **3 个变异体**证明审计有判别力
    （抠掉 `to_dict` 出口、抠掉 `dec_norm` 白名单行、把圈号换回拆解序号
    —— 对应判据都必须判红）。审计报出 6 类真问题，本版**全部处置**：

  【★ 15 个 `api.thinking.stages.*` 键永远选不中（装饰品 + 静默）】
    `thinking_stages.get(stage)` 只在 `stage` 非空时才生效，而
    `_decompose_normal` / `_probe_*` / `_settle_research` / `re_anchor` …
    **一共 16 个调用点根本没传 `stage=`** ⇒ 一律掉回 `thinking_default`。
    后果：用户把 `decompose_normal` 改成 `enabled` 会**毫无效果**，
    且没有任何提示。修法：新增 `_thinking_stage(cfg, name)`（**以配置为准**：
    只在键已声明时返回该名，拼错就返回 None），并给 16 个站点接线。
    ★ **行为不变的可机器验证证明**：这 15 个键的出厂值都是 `disabled`，
      与 `thinking.default` 相同 ⇒ 接线前后解析出的 `th` 逐字相同
      （判据 `K2` 用 DEFAULT_CONFIG 直接证）。

  【★ `web_search.stages` 里两个键是「声明了不做」】`practice_term_calibration`
    与 `stop_criteria` 永远不会被调用（任务书 §七 明确不做）⇒ 进豁免表
    `_AUDIT_CONFIG_EXEMPT`（**两向对账**：未登记判红 + 过期登记判红）。

  【★ 死类 `Amp` / `Probe`】定义后**零引用**。按项目纪律**不删**，
    登记进 `_AUDIT_DEAD_CLASSES`（只标不删，且下次审计不会再当新发现）。

  【遗留3 · tier 确认生效（人确认后才生效）】新增
    `web_search.tier_confirmed`（域名 → tier 的人工确认表，**默认空**）
    + `_web_tier_confirmed` / `_web_tier_floor` / `_web_enters_citation`。
    · W# 进引用表加 **tier 门**（与 X# 同纪律：有效 tier ≤ floor）；
    · 命中确认表时挂 `item["tier_effective"]`（**不改** `tier` 本身）；
    · `web_search.tier_floor` 由 2 改 3 —— 它此前**从未被读过**（又一个
      装饰品键），改成 3 后与 v1.23.1 行为一致（客户端初值 3 仍可进表），
      而人把某域名确认成 4（博客/论坛）就会被挡在引用表外；
    · ★ **从提案到生效没有自动路径**：`_web_tier_confirmed` 只读人写的
      确认表，绝不读 `tier_proposal` 的产物（判据 + 变异体钉住）。
    · 留痕 `[W-TIER✓] 人工确认表生效 N 条`（关闭态不出现 ⇒ 加性）。

  【遗留4 · `used_as` 语义】W4 第三票的检索原标 `arbitration`，而它的
    `stage` 是 `research_evidence` —— 两个标签对不上，读者无从判断
    「这条给谁用」。新增 `_WEB_USED_AS` 枚举（封闭集合）并改为 `tri_vote`。
    ★ 澄清一个事实（审计顺带查清）：`used_as` **没有程序消费方**，
      它是写给**读者与分析脚本**的；枚举化的价值在于「不得出现未登记取值」。

  【遗留1 · 空票重试】新增 `actions.tri_vote_retry_empty`（默认 1）：
    某票返回**合法 dict 但 `judgments` 为空**时重试一次 —— 空票是**失败**
    不是弃权（实测 10 跑里 4 跑因此只有 2 票可用）。留痕改成报
    **重试后**的可用票数。★ 不改 `ok_votes` 的位置（「三票全失败」分支不变）。

  【声明】本版对**离线验收集**（冒烟 / 6 份探针 / 验收档）与
    `dgtf_config.yaml` 都做了同步；`--phase all` 目标 0 FAIL。

v1.23.1 ── 遗留收尾（真圈号 / tier 提案待审 / 三场景 + 三票正交度实证）"""
if "v1.23.2 ── 整体性检查" not in src:
    src = sub_once(src, CL_OLD, CL_NEW, "S2 changelog 段")
else:
    print("  · S2 changelog 已加，跳过")

# =============================================================== S3 模块级
S3_ANCHOR = "class WebSearchCache:"
S3 = '''# ============================================================
# [v1.23.2 整体审计] 登记表 + 联网 tier 门 + thinking stage 解析
# ============================================================
# 【为什么把登记表放在**源码里**而不是审计脚本里】
#   本项目两次踩「清单型机制无声腐烂」（配置键 / AST 符号）。登记表若只存在
#   于审计脚本，它自己就成了第二个事实源 —— 放源码里，判据做**两向对账**：
#   未登记判红 + **过期登记也判红**（登记的东西已经不存在了）。
_AUDIT_DEAD_CLASSES = ("Amp", "Probe")
#   定义后零引用、按纪律**不删**的类。`Amp`/`Probe` 是 dataclass，
#   实际跑批里 amp/probe 都以 dict 形态流动（`pool.amps` / `pool.probes`），
#   所以这两个类只剩历史意义。**只标不删** —— 删了会丢掉「曾经有这个形态」
#   的线索，而留着需要登记才不会每次审计都被当成新发现。
_AUDIT_EXPORT_EXEMPT = {}
#   形如 {"类名": ("允许不出口的字段",)}。当前**无豁免**：
#   `Candidate` / `Probe` / `View` / `Pool` 的全部字段都必须出现在 to_dict()
#   （这是本项目的第 3 类高频坑：显式白名单漏字段 = 静默吞掉）。
_AUDIT_CONFIG_EXEMPT = (
    "web_search.stages.practice_term_calibration",
    "web_search.stages.stop_criteria",
)
#   声明了「不做」的配置键（任务书 §七：不做修行层联网、不做停止判据联网）。
#   它们**永远不会**被 `_web_search(stage=...)` 调用到 ⇒ 属「声明了不做」，
#   不是漏接线。登记在这里，两向对账防它悄悄变成真装饰品。
_WEB_USED_AS = ("evidence", "record", "arbitration", "clean_check", "tri_vote")
#   `web_results[*]["used_as"]` 的**取值枚举**（封闭集合）。
#   ★ 它没有程序消费方：它写给**读者**（产物里能看出这条给谁用）与
#     分析脚本（`_w6_analyze.py`）。枚举化是为了钉住「不得出现未登记取值」——
#     原先它是自由字符串，于是 W4 第三票写着 `arbitration` 而 stage 是
#     `research_evidence`，两个标签对不上，读者无从判断。


def _ws_cfg(cfg) -> dict:
    """把「完整 config」或「config["web_search"] 子段」归一成子段。

    ★ 两种写法在本项目**都**出现（`WebSearchGate(config)` 收完整、
      `pool._web_cfg` 存子段）——只认一种会让另一种**静默**读不到配置
      （v1.23.1 的 `_web_tier_proposal` 就踩过一次）。
    """
    if isinstance(cfg, dict) and isinstance(cfg.get("web_search"), dict):
        return cfg["web_search"]
    return cfg if isinstance(cfg, dict) else {}


def _web_tier_confirmed(cfg, url):
    """[v1.23.2 遗留3] 人工确认表里该 URL 的域名有没有被确认过 tier。

    返回 int 或 None。★ **只读** `web_search.tier_confirmed`（人写的），
    **绝不**读 `tier_proposal` 的产物 —— 从提案到生效**没有自动路径**。
    """
    _d = _web_domain_of(url)
    if not _d:
        return None
    _conf = _ws_cfg(cfg).get("tier_confirmed") or {}
    if not isinstance(_conf, dict) or _d not in _conf:
        return None
    try:
        return int(_conf[_d])
    except (TypeError, ValueError):
        return None


def _web_tier_floor(cfg) -> int:
    """[v1.23.2] W# 进引用表的 tier 门。

    ★ 本键（`web_search.tier_floor`）在 v1.23.1 及以前**从未被读过**
      —— 又一个「定义了没人读」的装饰品键（审计 J 类抓出来的）。
      默认改为 **3**：客户端初值 3 可进表 ⇒ 与 v1.23.1 行为一致。
    """
    try:
        return int(_ws_cfg(cfg).get("tier_floor", 3) or 3)
    except (TypeError, ValueError):
        return 3


def _web_tier_effective(item) -> int:
    """W# 的**有效** tier：人工确认值优先，否则取它自带的 tier（默认 3）。"""
    _v = (item or {}).get("tier_effective")
    if _v is None:
        _v = (item or {}).get("tier", 3)
    try:
        return int(3 if _v is None else _v)
    except (TypeError, ValueError):
        return 3


def _web_enters_citation(item, cfg) -> bool:
    """[v1.23.2 遗留3] W# 是否够格进引用表（与 X# 同纪律：tier ≤ floor）。"""
    return _web_tier_effective(item) <= _web_tier_floor(cfg)


def _thinking_stage(cfg, name):
    """[v1.23.2 整体审计] 环节名 → thinking 的 stage 键；**只在声明过时**返回。

    【为什么需要】审计发现 15 个 `api.thinking.stages.*` 键**永远选不中**：
      `_decompose_normal` / `_probe_*` / `_settle_research` / `re_anchor` …
      共 16 个调用点根本没传 `stage=` ⇒ 一律掉回 `thinking_default`。
      用户把 `decompose_normal` 改成 `enabled` 会**毫无效果**（静默装饰品）。
    【为什么以配置为准】写死字符串会有拼写错；拼错 = 静默掉回 default，
      与没接线一样。这里「键必须已声明」才返回，拼错返回 None，并可被
      判据（`_probe_v1232_audit.py` K 类）抓出来。
    """
    _st = ((cfg or {}).get("api") or {}).get("thinking") or {}
    return name if name in (_st.get("stages") or {}) else None


class WebSearchCache:'''
if "\n_AUDIT_DEAD_CLASSES = (" not in src:
    src = sub_once(src, S3_ANCHOR, S3, "S3 模块级登记表 + tier 门 + stage 解析")
else:
    print("  · S3 已加，跳过")

# =============================================================== S4 stage 接线
# ★ 用**函数名**定位，不用行号 —— 行号会被 S2 的 changelog 插入整体平移
#   （第一版就因此「@9272 找不到调用」）。函数名是稳定锚。
SITE_FNS = (
    "_re_anchor", "_decompose_normal", "_decompose_hybrid", "_decompose_koan",
    "_decompose_from_pool", "_probe_research", "_probe_duel", "_probe_meta",
    "_phase_probe", "_ask_missing_polarity", "_self_check",
    "_check_structure_saturation", "_settle_research", "_decide_parallel_mode",
    "_check_input_sanity",
)
if "stage=_thinking_stage(self.config" not in src and "stage=_thinking_stage(getattr(d" not in src:
    _lines = src.split("\n")
    _tree = ast.parse(src)
    _targets = []          # (end_ln, end_col, stage_name, cfg_expr)
    for _fn in SITE_FNS:
        _defn = None
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.FunctionDef) and _n.name == _fn:
                _defn = _n
                break
        assert _defn is not None, "S4 找不到函数 %s" % _fn
        for _c in ast.walk(_defn):
            if not (isinstance(_c, ast.Call)
                    and isinstance(_c.func, ast.Attribute)
                    and _c.func.attr in ("call", "_call_long")):
                continue
            if any(k.arg == "stage" for k in _c.keywords):
                continue
            _srctxt = ast.get_source_segment(src, _c) or ""
            # `d.llm.call` 用的是局部 DGTF 实例的 config，不是 self.config
            _cfgx = ("getattr(d, 'config', None)" if _srctxt.startswith("d.llm.call")
                     else "self.config")
            _targets.append((_c.end_lineno, _c.end_col_offset, _fn.lstrip("_"),
                             _cfgx))
    # 从后往前插，避免位置漂移
    _targets.sort(reverse=True)
    for _el, _ec, _stg, _cfgx in _targets:
        _line = _lines[_el - 1]
        assert _line[_ec - 1] == ")", (
            "S4 %s 结尾不是 )：%r" % (_stg, _line[max(0, _ec - 8):]))
        _k = _ec - 2
        while _k >= 0 and _line[_k] in " \t":
            _k -= 1
        _sep = " " if _k >= 0 and _line[_k] == "," else ", "
        _ins = "%sstage=_thinking_stage(%s, %r)" % (_sep, _cfgx, _stg)
        _lines[_el - 1] = _line[:_ec - 1] + _ins + ")"
    src = "\n".join(_lines)
    ast.parse(src)
    print("  · S4 已接线 %d 个调用点（按函数名定位）" % len(_targets))
else:
    print("  · S4 已接线，跳过")

# =============================================================== S5 used_as
U_OLD = '''                _research_evidence_queries({"to": "partial",
                                            "_sq_text": question[:120]}),
                self._research_round_no(), used_as="arbitration")'''
U_NEW = '''                _research_evidence_queries({"to": "partial",
                                            "_sq_text": question[:120]}),
                self._research_round_no(),
                # [v1.23.2 遗留4] 这处的 stage 是 `research_evidence`，原先却标
                #   `used_as="arbitration"` —— 两个标签对不上，读者无从判断
                #   「这条到底给谁用」。改标 `tri_vote`（= 给第三票当裁判材料）。
                used_as="tri_vote")'''
if 'used_as="tri_vote"' not in src:
    src = sub_once(src, U_OLD, U_NEW, "S5 W4 第三票 used_as → tri_vote")
else:
    print("  · S5 已改，跳过")

# =============================================================== S6 遗留3
# S6a 配置：tier_floor 2 -> 3，并加 tier_confirmed
if '"tier_confirmed": {}' not in src:
    CFG_OLD = '''        # 【引用授权】off / record / crosscheck / evidence / gate。
        "as_evidence": "crosscheck",
        "tier_floor": 2,'''
    CFG_NEW = '''        # 【引用授权】off / record / crosscheck / evidence / gate。
        "as_evidence": "crosscheck",
        # 【tier 门】[v1.23.2 遗留3] W# 进引用表的有效 tier 上限。
        #   ★ 本键在 v1.23.1 及以前**从未被读过**（审计 J 类抓出来的装饰品）。
        #   ★ 默认 3 = 与 v1.23.1 行为一致：客户端初值 3 能进表；
        #     人把某域名在 `tier_confirmed` 里确认成 4（博客/论坛）就进不了。
        "tier_floor": 3,
        # 【人工确认表】[v1.23.2 遗留3] 域名 → tier。**默认空 = 零差异**。
        #   ★ 从「提案」（`tier_proposal`）到「生效」**没有自动路径**：
        #     只有人把域名写进这张表才生效（写 4 会把它挡在引用表外）。
        #   形如：{"natcm.gov.cn": 1, "zhihu.com": 4}
        "tier_confirmed": {},'''
    src = sub_once(src, CFG_OLD, CFG_NEW, "S6a 配置 tier_floor=3 + tier_confirmed")
else:
    print("  · S6a 已加，跳过")

# S6b _web_search：记 pool._web_cfg + 挂 tier_effective + 留痕
if "pool._web_cfg = _ws_cfg(self.config)" not in src:
    W1_OLD = '''        if pool is not None:
            # 引用授权门每次同步（配置在跑内不变，但显式摆在这里可读）。
            pool.web_as_evidence = _web_evidence_gate(self.config)'''
    W1_NEW = '''        if pool is not None:
            # 引用授权门每次同步（配置在跑内不变，但显式摆在这里可读）。
            pool.web_as_evidence = _web_evidence_gate(self.config)
            # [v1.23.2 遗留3] 把 web_search 段挂在池上，供 `_citation_table`
            #   的 tier 门读（纯函数读不到 self —— 与 X# 的 `_anchor_cfg` 同款）。
            pool._web_cfg = _ws_cfg(self.config)'''
    src = sub_once(src, W1_OLD, W1_NEW, "S6b-1 pool._web_cfg")

    W2_OLD = '''                        "pre_seq": int(pre_seq or 0)}
                if pool is not None:'''
    W2_NEW = '''                        "pre_seq": int(pre_seq or 0)}
                # [v1.23.2 遗留3] 人工确认的 tier 才生效。★ 只挂
                #   `tier_effective`，**不改** `tier` 本身（tier 永远是客户端
                #   初值；提案与确认都不动它）。没命中确认表 ⇒ **不挂键**（加性）。
                _cf = _web_tier_confirmed(self.config, item.get("url", ""))
                if _cf is not None:
                    item["tier_effective"] = int(_cf)
                if pool is not None:'''
    src = sub_once(src, W2_OLD, W2_NEW, "S6b-2 挂 tier_effective")

    W3_OLD = '''        if out and pool is not None:
            pool.meta.append(
                "[W-OK] " + stage + " 收 " + str(len(out)) + " 条（"
                + "、".join(str(x.get("id")) for x in out[:4])
                + ("…" if len(out) > 4 else "") + "）")'''
    W3_NEW = '''        if out and pool is not None:
            pool.meta.append(
                "[W-OK] " + stage + " 收 " + str(len(out)) + " 条（"
                + "、".join(str(x.get("id")) for x in out[:4])
                + ("…" if len(out) > 4 else "") + "）")
            # [v1.23.2 遗留3] 人工确认表生效也要留痕 —— 否则「这条为什么
            #   没有进引用表」在产物里查不到（沉默 = 不可读）。
            _cfi = [x for x in out if "tier_effective" in x]
            if _cfi:
                pool.meta.append(
                    "[W-TIER✓] 人工确认表生效 " + str(len(_cfi)) + " 条："
                    + "、".join(
                        str(_web_domain_of(x.get("url"))) + "→"
                        + str(x.get("tier_effective"))
                        for x in _cfi[:4]))'''
    src = sub_once(src, W3_OLD, W3_NEW, "S6b-3 [W-TIER✓] 留痕")
else:
    print("  · S6b 已加，跳过")

# S6c _citation_table：W# tier 门
if "if not _web_enters_citation(_w," not in src:
    C_OLD = '''        _wi = 0
        for _w in (getattr(pool, "web_results", None) or []):
            if not str((_w or {}).get("claim", "")).strip():
                continue
            _wi += 1'''
    C_NEW = '''        _wi = 0
        for _w in (getattr(pool, "web_results", None) or []):
            if not str((_w or {}).get("claim", "")).strip():
                continue
            # [v1.23.2 遗留3] tier 门（与 X# 同纪律）：只收**有效 tier**
            #   ≤ `web_search.tier_floor` 的条目。默认 floor=3 ⇒ 与 v1.23.1
            #   一致；人把某域名确认成 4（博客/论坛）后就进不了引用表。
            if not _web_enters_citation(_w, getattr(pool, "_web_cfg", None)):
                continue
            _wi += 1'''
    src = sub_once(src, C_OLD, C_NEW, "S6c W# tier 门")
else:
    print("  · S6c 已加，跳过")

# S6d _web_digest_block：显示有效 tier
if 'x.get("tier_effective"' not in src:
    D_OLD = '''        lines.append("- " + str(x.get("id", "W?")) + "（"
                     + str(x.get("stage", "")) + "，tier "
                     + str(x.get("tier", 3)) + "）："
                     + str(x.get("claim", ""))[:200])'''
    D_NEW = '''        lines.append("- " + str(x.get("id", "W?")) + "（"
                     + str(x.get("stage", "")) + "，tier "
                     # [v1.23.2 遗留3] 显示**生效**档（人工确认值优先）。
                     + str(x.get("tier_effective", x.get("tier", 3))) + "）："
                     + str(x.get("claim", ""))[:200])'''
    src = sub_once(src, D_OLD, D_NEW, "S6d 摘要显示有效 tier")
else:
    print("  · S6d 已改，跳过")

# S6e _web_tier_proposal 复用 _ws_cfg（去重复实现）
if "两种写法都常见" in src and "_cfg = _ws_cfg(cfg)" not in src:
    P_OLD = '''    _cfg = cfg if isinstance(cfg, dict) else {}
    if isinstance(_cfg.get("web_search"), dict):
        _cfg = _cfg["web_search"]
    _rules = _cfg.get("domain_tier_rules") or []'''
    P_NEW = '''    _cfg = _ws_cfg(cfg)
    _rules = _cfg.get("domain_tier_rules") or []'''
    src = sub_once(src, P_OLD, P_NEW, "S6e tier 提案复用 _ws_cfg")

# =============================================================== S7 空票重试
if "\"tri_vote_retry_empty\": 1," not in src:
    A_OLD = '''        # 【引用授权】off / record / crosscheck / evidence / gate。'''
    src = src  # 占位：配置加在 actions 段（下面单独锚）
    AC_OLD = '        "tri_multi_vote": True,'
    AC_NEW = '''        "tri_multi_vote": True,
        # [v1.23.2 遗留1] 三票里某票返回**合法 dict 但 judgments 为空**时
        #   重试次数。★ 空票是**失败**不是弃权（实测 10 跑里 4 跑因此只有
        #   2 票可用）。0 = 不重试（退回 v1.23.1 行为）。
        "tri_vote_retry_empty": 1,'''
    src = sub_once(src, AC_OLD, AC_NEW, "S7a actions.tri_vote_retry_empty")

    R_OLD = '''        _empty_votes = 0
        for _vi, sysp in enumerate(_sys_list):
            try:
                raw = self.llm.call(sysp, user, 0.0, 1200, json_mode=True,
                                    stage="adjudicate_sub_tristate_multi")
                data = self.llm.parse_json(raw)
            except Exception as e:
                logger.warning("三态多票：一票失败（跳过）: %s", e)
                continue
            if not isinstance(data, dict):
                continue'''
    R_NEW = '''        _empty_votes = 0
        # [v1.23.2 遗留1] 空票重试：空票是**失败**（这次没问到），不是弃权。
        _retry = 0
        try:
            _retry = int((self.config.get("actions") or {})
                         .get("tri_vote_retry_empty", 1) or 0)
        except (TypeError, ValueError):
            _retry = 1
        for _vi, sysp in enumerate(_sys_list):
            data = None
            for _try in range(1 + max(0, _retry)):
                try:
                    raw = self.llm.call(
                        sysp, user, 0.0, 1200, json_mode=True,
                        stage="adjudicate_sub_tristate_multi")
                    data = self.llm.parse_json(raw)
                except Exception as e:
                    logger.warning("三态多票：一票失败（跳过）: %s", e)
                    data = None
                    break
                if isinstance(data, dict) and (data.get("judgments") or []):
                    break
                if _try < max(0, _retry):
                    logger.warning(
                        "三态多票：第 %d 票返回 0 条判决（合法 dict 但空），"
                        "重试 %d/%d", _vi + 1, _try + 2, 1 + max(0, _retry))
            if not isinstance(data, dict):
                continue'''
    src = sub_once(src, R_OLD, R_NEW, "S7b 空票重试循环")
else:
    print("  · S7 已加，跳过")

# =============================================================== 写回
out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "出现 CRCRLF"
assert out.count(b"\r") == out.count(b"\r\n"), "出现裸 CR"
ast.parse(src)
NEW.write_bytes(out)
print("[done] %s  %d 行" % (NEW.name, out.count(b"\n") + 1))

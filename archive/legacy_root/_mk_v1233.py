#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3] 主文件补丁：版本 + 三票 id 归一化（修「整票错位一格且无声」）。

发现路径：`_ab_tri_votes_v1233.py` 的受控投票实验里，某一票返回的
`judgments[].id` 是 **0 起**（0..n-1），而引擎按 **1 起** 对齐
（`enumerate(subs, 1)`）⇒ 该票**整票错位一格**：
第 2 条子问题拿到本该给第 1 条的标签，第 1 条没人投。
既不抛错、也不留痕 —— 读者从产物上完全看不出来。
两处实现（多票 / 单票）都有这个问题。

修法（最小且可断言）：
  · 新增模块级纯函数 `_normalize_judgment_ids(judged, n)`：
      1..n     → 原样
      0..n-1   → 整体 +1（并留痕）
      其他     → 判 None（**弃票**，绝不猜）
  · 两条路径都过它；异常与归一分档计数写进 `pool.meta`（加性：全 0 时不写）。
"""
from pathlib import Path
import ast
import shutil

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.2.py"
DST = HERE / "元DGTF-V1.23.3.py"
if not DST.exists():
    shutil.copyfile(SRC, DST)

raw = DST.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "主文件不是纯 CRLF"
s = raw.replace("\r\n", "\n")


def sub_once(old, new, tag):
    global s
    assert s.count(old) == 1, "%s：锚点命中 %d 次" % (tag, s.count(old))
    s = s.replace(old, new)
    print("  · %s" % tag)


# ---------------------------------------------------------------- S1 版本号
sub_once("元 DGTF · v1.23.2", "元 DGTF · v1.23.3", "S1 标题版本")
sub_once('__version__ = "1.23.2"', '__version__ = "1.23.3"', "S1 __version__")

# ---------------------------------------------------------------- S2 changelog
CHANGELOG = """v1.23.3 相对 v1.23.2

【主题】把 `v1232_报告.md` §十「仍未做 / 如实记账」五条**逐条清空**：
  不是「多跑几次」，而是把每一条**换成可判定的口径 / 受控实验 / 真跑旁证**。

  【遗留1 正交度：观测口径 → 受控实验】
    原判据「组间 ≥ 组内」（组 = 题、组内 = 同题重复跑）**结构性不可判定**：
    子问题集合**每跑重新拆解**，于是组内变异里混进了**上游拆解**的变异。
    实测同题两跑 `agree13` = 0.0 vs 1.0（组内极差 1.0 > 组间差 0.083）——
    再跑一百次也一样，测得的是「拆解每次都不一样」。
    修法：`_ab_tri_votes_v1233.py` **受控实验** —— 固定 12 条子问题 + 固定
    外部材料，只让三票重投（W4 关/开 × 温度 0.0/0.7 四臂）。
    判据落两个口径：① 信度 ICC(1,1) + 自助区间（组 = 子问题、组内 = 重复）；
    ② 字面口径「组间 ≥ 组内」= |臂间配对差 Δ| ≥ 配对残差 σ。
    ★ 温度 0.7 那一对是**负对照**：注入随机性后 ICC 不降 = 这个 ICC 没有判别力。

  【遗留1 顺带抓到的真 bug：三票 id 整票错位一格，且无声】
    受控实验实测：某票返回的 `judgments[].id` 是 **0 起**，引擎按 1 起对齐
    ⇒ 该票**整票错位一格**（第 2 条拿到本该给第 1 条的标签），第 1 条没人投。
    两处实现（`_adjudicate_sub_tristate_multi` / `_adjudicate_sub_tristate`）
    都直接 `sid = int(it.get("id", 0))`，没有任何校验。
    修法：新增 `_normalize_judgment_ids(judged, n)` 纯函数（1 起原样 /
    0 起整体 +1 / 其他**弃票**），两条路径都过它，并把「空票 / 0 起归一 /
    越界弃票」三个计数写进池级留痕（全 0 时**不写**，保持加性）。
    ★ 只归一、不猜：越界一律弃票而不是硬塞。

  【遗留2 思考分档：注释里的断言 → 录播式 A/B】
    那 15 行在 yaml 里写着「关：思考无收益」，但那是**注释里的断言**，
    从没测过（v1.23.2 只是把值改到与实际行为一致）。
    修法：`_ab_thinking_v1233.py` 先包住 `llm.call` 抓一次真跑的
    **真实 (stage, system, user, 温度, max_tokens) 输入**，再逐 stage 用
    同一批输入跑 thinking 关/开，量 JSON 合法率、输出规模、延迟与**评分**，
    判据用等效检验（区间落在 margin 内 = 无收益），输出逐 stage 结论。

  【遗留3 tier 确认：空表 → 真跑旁证】
    `web_search.tier_confirmed` 机制通了但表是空的（生效路径只有离线判据）。
    修法：先用真跑采集真实域名，再按观察把域名写进确认表（低质域 → 4
    踢出引用表 / 权威域 → 1），重跑并验产物里 `[W-TIER✓]` / `tier_effective`
    与引用表的排斥效果；未确认域作**负对照**（不挂键 = 与默认逐字一致）。

  【遗留5 triage 频度：顺手捞到的读数 → 专项批 + Wilson 区间】
    原读数 1/10 是**顺手**得到的，不是专项测量。修法：`_run_v1233_triage.py`
    用定制题 + 定向锚点跑 N 跑，报 k/N + Wilson 95% 区间（区间不含 0 即
    「频度可判定」，无论高低）。

  【声明】本版对**离线验收集**（冒烟 / 7 份探针 / 验收档）与**出厂配置**
  一并同步：新增 `_normalize_judgment_ids` 进 AST 登记表；新增冒烟判据
  `check_v1233_vote_ids`（含端到端错位修正 + 变异体）；审计探针补一类
  「读模型返回的 id 必须过归一化」。

"""
sub_once("CHANGELOG（按版本分段，最新在最前；每段只写该版本相对上一版本的改动）\n",
         "CHANGELOG（按版本分段，最新在最前；每段只写该版本相对上一版本的改动）\n\n"
         + CHANGELOG, "S2 changelog")

# ---------------------------------------------------------------- S3 纯函数
ANCHOR_TH = '''def _thinking_stage(cfg, name):'''
NEWFN = '''def _normalize_judgment_ids(judged, n):
    """[v1.23.3] 把一票的 `{id: label}` 归一到 **1..n** 对齐；越界返回 None。

    【为什么需要 —— 受控实验抓到的真 bug】
      `_ab_tri_votes_v1233.py` 实测：某票返回的 `judgments[].id` 是 **0 起**
      （0..n-1），而引擎按 **1 起** 对齐（`for i, s in enumerate(subs, 1)`）。
      后果：该票**整票错位一格** —— 第 2 条子问题拿到本该给第 1 条的标签，
      第 1 条没人投。既不抛错也不留痕，**读者从产物上完全看不出来**，
      而三态判决、`stability`、`tri_consensus` 全部跟着偏。
      两处实现（多票 / 单票）都是 `sid = int(it.get("id", 0))` 直接用。

    【口径】只归一、不猜：
      · 键集 ⊆ {1..n}      → 原样（生产口径）
      · 键集 ⊆ {0..n-1}    → 整体 +1（这才是 0 起；**留痕**，不静默）
      · 其他（含越界 / 混合）→ 返回 None ⇒ 调用方**弃这一票**
        （绝不做「把第 k 条硬塞给第 k 条」这种猜测 —— 那正是要防的静默）。
    返回 `(归一后的 dict 或 None, 档位说明)`，说明进池级留痕。
    """
    if not isinstance(judged, dict) or not judged or int(n or 0) <= 0:
        return None, "空"
    _ks = set(judged)
    _hi = int(n)
    if _ks <= set(range(1, _hi + 1)):
        return dict(judged), "1起"
    if _ks <= set(range(0, _hi)):
        return {int(k) + 1: v for k, v in judged.items()}, "0起+1"
    return None, "越界"


def _thinking_stage(cfg, name):'''
sub_once(ANCHOR_TH, NEWFN, "S3 _normalize_judgment_ids")

# ---------------------------------------------------------------- S4 多票路径
OLD_M = '''            ok_votes += 1
            for it in (data.get("judgments") or []):
                if not isinstance(it, dict):
                    continue
                try:
                    sid = int(it.get("id", 0))
                except (ValueError, TypeError):
                    continue
                st = str(it.get("decidability", "")).lower().strip()
                if st not in _DECIDABILITY_STATES:
                    continue
                votes.setdefault(sid, []).append(st)'''
NEW_M = '''            ok_votes += 1
            _judged: Dict[int, str] = {}
            for it in (data.get("judgments") or []):
                if not isinstance(it, dict):
                    continue
                try:
                    sid = int(it.get("id", 0))
                except (ValueError, TypeError):
                    continue
                st = str(it.get("decidability", "")).lower().strip()
                if st not in _DECIDABILITY_STATES:
                    continue
                _judged[sid] = st
            # [v1.23.3 遗留1] ★ 归一化 id 基准。实测某票返回 **0 起** id ⇒
            #   整票错位一格且**无声**（第 2 条拿到本该给第 1 条的标签）。
            #   1 起原样 / 0 起整体 +1 / 越界**弃票**。三个计数进池级留痕。
            _jb, _jk = _normalize_judgment_ids(_judged, len(subs))
            if _jk == "0起+1":
                _id_shift += 1
            elif _jb is None:
                _id_bad += 1
                logger.warning("三态多票：第 %d 票 id 档位=%s → 弃票",
                               _vi + 1, _jk)
                continue
            for _sid2, _st2 in (_jb or {}).items():
                votes.setdefault(_sid2, []).append(_st2)'''
sub_once(OLD_M, NEW_M, "S4 多票路径归一化")

sub_once('''        _empty_votes = 0
        # [v1.23.2 遗留1] 空票重试''',
         '''        _empty_votes = 0
        # [v1.23.3 遗留1] 票的 id 基准异常计数（见 `_normalize_judgment_ids`）。
        _id_shift = 0
        _id_bad = 0
        # [v1.23.2 遗留1] 空票重试''', "S4 计数器初始化")

OLD_META = '''        if _empty_votes:
            _p1 = self.pools.get("1")
            if _p1 is not None:
                _p1.meta.append(
                    "[三态多票] " + str(len(_sys_list) - _empty_votes)
                    + "/" + str(len(_sys_list)) + " 票可用（空票 "
                    + str(_empty_votes) + " 张，等于弃权；一致性指标只在"
                    "**可用票**之间计算）")'''
NEW_META = '''        if _empty_votes or _id_shift or _id_bad:
            _p1 = self.pools.get("1")
            if _p1 is not None:
                # ★ 全 0 时不写（加性）：这条留痕只在**真的发生异常**时出现。
                #   可用票数要把**弃票**也扣掉 —— 否则会印出「3/3 票可用」
                #   却只剩两张在算（非读数被当成测量值）。
                _extra = ""
                if _id_shift:
                    _extra += "；id 0 起→+1 归一 " + str(_id_shift) + " 张"
                if _id_bad:
                    _extra += "；id 越界弃票 " + str(_id_bad) + " 张"
                _p1.meta.append(
                    "[三态多票] "
                    + str(len(_sys_list) - _empty_votes - _id_bad)
                    + "/" + str(len(_sys_list)) + " 票可用（空票 "
                    + str(_empty_votes) + " 张，等于弃权；一致性指标只在"
                    "**可用票**之间计算" + _extra + "）")'''
sub_once(OLD_META, NEW_META, "S4 池级留痕")

sub_once('''        if ok_votes == 0:
            logger.warning("三态多票：三票全失败 → 保留拆解原标签")''',
         '''        if ok_votes == 0 or not votes:
            # [v1.23.3] `not votes` 也要走这一支：三票都返回了合法 dict、
            #   但**全部越界弃票**时，`ok_votes` 不为 0 而一条票都没落 ——
            #   原条件会漏过去，最后印出「三票 0/0」。与「三票全失败」同语义。
            logger.warning("三态多票：无有效票（全失败或全部弃票）"
                           " → 保留拆解原标签")''', "S4 全失败守卫")

# ---------------------------------------------------------------- S5 单票路径
OLD_S = '''        judged: Dict[int, str] = {}
        for it in (data.get("judgments") or []):
            if not isinstance(it, dict):
                continue
            try:
                sid = int(it.get("id", 0))
            except (ValueError, TypeError):
                continue
            st = str(it.get("decidability", "")).lower().strip()
            if st not in _DECIDABILITY_STATES:
                continue
            judged[sid] = st
        if not judged:'''
NEW_S = '''        judged: Dict[int, str] = {}
        for it in (data.get("judgments") or []):
            if not isinstance(it, dict):
                continue
            try:
                sid = int(it.get("id", 0))
            except (ValueError, TypeError):
                continue
            st = str(it.get("decidability", "")).lower().strip()
            if st not in _DECIDABILITY_STATES:
                continue
            judged[sid] = st
        # [v1.23.3 遗留1] 同多票路径：id 基准归一化（0 起 → +1、越界 → 判空）。
        judged, _jk1 = _normalize_judgment_ids(judged, len(subs))
        if judged is None and _jk1 == "越界":
            logger.warning("三态独立判决：id 档位=%s → 弃（保留拆解原标签）",
                           _jk1)
        if not judged:'''
sub_once(OLD_S, NEW_S, "S5 单票路径归一化")

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
ast.parse(s)
DST.write_bytes(out)
print("  · 已写 %s（%d 行）" % (DST.name, s.count("\n") + 1))

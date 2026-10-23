# -*- coding: utf-8 -*-
"""
收敛矩阵采集器 —— 为「自动调度选路」提供经验表。

一句话目标：把「题型 × 模式 × 圈数」→「收敛条件 / 停止触发 / 实际圈数 /
成本」这条关系从**已有的真跑数据**里抽出来，变成可以读的表，而不是靠猜。

数据源两处，缺一不可：
  · v60_*.log  —— 规划输入（route/mode/rounds/成本档/预算）+ 成本输出
                  （llm_calls/tokens）+ 判据（分叉/无追溯）+ 产物路径
  · outputs/*.md —— 每层**实际**跑了几圈、因什么停、闭环清算干净与否、
                  质量线索。这是「收敛」真正的落点。

为什么非要两边合起来看：
  日志只有「规划给了几圈」，产物才有「实际跑了几圈」。这两者的差就是
  「给多不等于跑多」的证据；而停止理由只在产物里，日志里搜「体力耗尽」
  会连注释和推迟说明一起数进去（历史上就这么假报过 19 次 vs 1 次）。

用法：
  python -u _convergence_matrix.py                # 扫全部 v60_*.log
  python -u _convergence_matrix.py "v60_x61*.log" # 只扫一批
  python -u _convergence_matrix.py --layers       # 附带逐层明细

口径说明（改动前先读）：
  · 停止理由分类见 classify_stop()。分类是**字面量映射**，不是语义判断 ——
    代码里新增一种停止理由而这里没加，会落到 OTHER 并被汇总表点名，
    不会悄悄混进「自然停止」。
  · 圈数取产物里「实际走了 N 圈」，不是规划给的 rounds。
  · 题型由 QUESTION_TYPES 关键词映射，匹配不上归 UNKNOWN 并在汇总里报出来。
"""
import re
import sys
import glob
from pathlib import Path
from collections import Counter, defaultdict

HERE = Path(__file__).resolve().parent

LAYER_NAMES = {
    "0": "修行",
    "1": "研究",
    "both": "对撞",
    "all": "元",
}

# 题型 → 关键词（打在产物文件名/问题文本上）
#   F 事实/可查证：有外部事实答案，研究层应能收敛
#   O 操作/方法论：要给出可执行的口径或步骤，partial 居多
#   P 哲学/结构开放：无外部答案，靠结构揭示与悬置收敛
QUESTION_TYPES = [
    # ⚠️ F 只放**强实体词**（有外部可核对答案的专名）。别放"指标""运营效率"
    #    "地铁""包含"这类泛词 —— 实测踩过：O 类题「怎么衡量一条城市地铁线路
    #    的运营效率？用什么指标，各自怎么取舍」被这几个词抢先判成 F，
    #    结果 27 个"F 类"样本里 21 个其实是同一道 O 类题的重复跑，
    #    按题型分层的所有结论跟着一起错。
    ("F", ["欧盟", "法案", "GDP", "多少",
           "哪一年", "是否属于", "定义是", "哪几",
           # 技术细节题：有外部可核对的确定答案
           "SNI", "sysconfig", "GIL", "记录位", "密钥", "推断", "TLS"]),
    ("O", ["如何", "怎么", "怎样", "用什么", "能力", "流程", "能否独立",
           "该不该", "要不要", "做法", "方案", "衡量",
           "IC", "能做什么", "到底"]),
    ("P", ["自由意志", "人生的意义", "灵魂", "存在", "剩下", "意义",
           "意识", "宇宙", "文明", "为什么",
           # 结构/自指类：没有外部答案，只能揭示结构
           "先于", "回溯", "停点", "整体/部分", "何时获得",
           "整体大于部分", "命题本身", "证明自己", "自指", "可判定吗"]),
    # T：机制自测题，不是真问题。单独一类，别让它污染选路表。
    ("T", ["自检", "PNP", "PPN", "wrapper", "只用来验证"]),
]

# 停止理由 → 类别。★ 顺序敏感：越具体的越靠前。
#   「双通道均收敛」比「有新增但无推进」更硬 —— 后者说的是量在涨质没动，
#   前者说的是两条通道都判完了，所以双通道那条即使同时带"无推进"也归安住。
STOP_RULES = [
    ("预算", ["预算用尽"]),                       # 动态提前停：诚实的被迫停
    ("走满", ["体力耗尽"]),                       # 走满上限：圈给少了
    ("安住", ["自然安住", "方向走完了", "无线头新增",
              "双通道均收敛", "无新 &", "沉淀完了",
              "无新维度"]),                       # 自然收敛（含结构饱和）
    ("空转", ["层内空转", "点名同一批", "复述",
              "有新增但无推进"]),                 # 有量无质
    ("清算", ["闭环完成", "清算完成", "交代完"]),  # 因清算完成而停
]


def classify_stop(reason: str) -> str:
    """把停止理由原文归到一类。认不出的返回 OTHER，绝不冒充自然停止。"""
    for cat, keys in STOP_RULES:
        for k in keys:
            if k in reason:
                return cat
    return "OTHER"


# ⚠️ 处世/价值类题**必须优先于** O 判。它们句式为「如何…」「需要具备什么」，
#   天然命中 O 的关键词，但本质是 P（没有外部答案，只能揭示结构）。
#   实测污染：O 类里混进「在AI飞速发展的当下我们如何与之相处」
#   「AI时代我们最需要具备的能力是什么」后，mode 对比直接反了 ——
#   serial 那 6 个 O 类样本里 5 个是这类题（覆盖率 40%），而 H/B 跑的
#   是「怎么衡量地铁运营效率」（96%）。看着像"serial 质量差"，
#   其实是两边跑的根本不是一类题。
P_PRIOR_KEYS = ["相处", "需要具备", "该具备", "如何面对", "怎样生活",
                "如何自处", "如何共处", "具备什么"]


def guess_type(name: str) -> str:
    for k in P_PRIOR_KEYS:
        if k in name:
            return "P"
    for t, keys in QUESTION_TYPES:
        for k in keys:
            if k in name:
                return t
    return "?"


# ---------------- 日志侧 ----------------

def gen_of(layers: dict) -> str:
    """区分配置代次。老版本 hard_max 默认 3，现在钳到 [4,6] —— 拿 3 圈的
    老数据去推「现在该给几圈」，结论会系统性偏低。默认只统计 cur。"""
    caps = [lr.get("cap") for lr in layers.values() if lr.get("cap")]
    return "cur" if any(c >= 4 for c in caps) else "old3"


def guess_output_by_mtime(log_path: Path):
    """日志里没有「产物=」时的回退：outputs/ 里紧跟其后的那篇。"""
    out_dir = HERE / "outputs"
    if not out_dir.is_dir():
        return None
    t0 = log_path.stat().st_mtime
    best, best_dt = None, None
    for p in out_dir.glob("*.md"):
        dt = p.stat().st_mtime - t0
        if dt < -60 or dt > 1800:      # 产物早于日志 >1min，或晚于 30min：不是
            continue
        if best_dt is None or dt < best_dt:
            best, best_dt = p, dt
    return best


def scan_log(path: Path) -> dict:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"file": path.name, "error": str(e)}

    d = {"file": path.name, "error": "", "log": path}

    # 文件名 v60_<tag>_<r_tag>_<mode>.log
    m = re.match(r"v60_(.+)\.log$", path.name)
    parts = m.group(1).split("_") if m else []
    d["mode"] = parts[-1] if parts else "?"
    d["r_tag"] = parts[-2] if len(parts) >= 3 else "?"
    d["tag"] = "_".join(parts[:-2]) if len(parts) >= 3 else "_".join(parts)

    # 规划行（只有 auto / rauto 的日志有）
    mp = re.search(r"自动规划：route=(\[[^\]]*\]) mode=(\S+) "
                   r"rounds=(\{[^}]*\}) 成本档=(\S+) 预算=(\S+)", txt)
    if mp:
        d["route"] = mp.group(1)
        d["p_mode"] = mp.group(2)
        d["rounds"] = mp.group(3)
        d["profile"] = mp.group(4)
        d["budget"] = mp.group(5)
    else:
        for k in ("route", "p_mode", "rounds", "profile", "budget"):
            d[k] = "-"

    mc = re.search(r"llm_calls=(\d+)(?:\s+tokens=(\d+))?", txt)
    d["calls"] = int(mc.group(1)) if mc else None
    d["tokens"] = int(mc.group(2)) if (mc and mc.group(2)) else None

    md = re.search(r"decidability=(\w+)", txt)
    d["decidability"] = md.group(1) if md else "-"
    mf = re.search(r"分叉=(\w+)", txt)
    d["divergent"] = mf.group(1) if mf else "-"

    # 产物定位。老一批日志是 _run_v60.py 还没写「产物=」时跑的，
    # 落盘路径只存在于当次 stdout。这里的回退是：取 outputs/ 里 mtime
    # 落在这份日志之后、且最接近的那一篇 —— 跑批是先跑完再落盘，所以
    # 产物必然比日志新，且中间不会夹别的跑（串行批次）。
    # 命中不了就当没有，宁可少一格也不猜一个错的。
    # ⚠️ 曾经写成 `产物=(\S+)` —— 文件名**带空格**时被截断在第一个空格：
    #   「..._225446_AI 能否独立完成数字 IC 设计流程？.md」只拿到
    #   「..._225446_AI」→ 判为产物缺失 → 这批行只能走孤儿路径，用 mtime
    #   去**借别人的日志**，calls/成本于是全是错的（实测 11 份产物带全角
    #   问号、另有若干带空格，整批受影响）。这条才是受害者最容易想到的
    #   「为什么我的样本数一会儿多一会儿少」的根。
    mo = re.search(r"^产物=(.+?)\s*$", txt, re.M)
    if mo:
        d["out"] = Path(mo.group(1))
        d["out_src"] = "log"
    else:
        d["out"] = guess_output_by_mtime(path)
        d["out_src"] = "mtime" if d["out"] else "-"

    # run 级机制计数（只在日志里数得清的）
    d["推迟"] = txt.count("未深入方向")
    d["预算用尽次数"] = txt.count("预算用尽")
    return d


# ---------------- 产物侧 ----------------

# 层头有两种历史写法，都得认：
#   新：`### 修行层 `0``    老：`## 0`
# 不兼容老写法的话，82 篇产物里只能吃到 26 篇 —— 剩下 56 篇是**免费样本**，
# 丢掉等于白跑。
LAYER_HEAD = re.compile(
    r"^#{2,3}\s*(?:(?:修行层|研究层|对撞层|元层)\s*)?"
    r"`?(0|1|both|all)`?\s*$", re.M)
DETAIL_START = re.compile(r"^## 附：逐层明细\s*$", re.M)
DETAIL_END = re.compile(r"^## (?:池|这一次我是谁|悬置总览)\s*$", re.M)

RE_ROUNDS = re.compile(r"\*\*实际走了\s*(\d+)\s*圈\*\*(?:（上限\s*(\d+)\s*圈）)?")
RE_STOP = re.compile(r"\*\*螺旋停止\*\*：(.+)")
RE_CLOSURE = re.compile(
    r"\*\*闭环清算\*\*：clean=(\w+)，对撞张力\s*(\d+)\s*类，"
    r"未交代\s*(\d+)\s*类")
RE_DIST = re.compile(r"\*\*综合距离\*\*：([\d.]+)")
RE_QFLAG = re.compile(r"\*\*质量线索\*\*：(.+)")
RE_QVERD = re.compile(r"\*\*质量评价\*\*：(.+)")
RE_DEBT = re.compile(r"最终状态：未回访，挂账 active")
# ★ 全局可判定性：这是**唯一跨层可比的输出质量口径**。
#   砍层数到底伤不伤质量，最终就看它 —— 层内指标（自然停/未交代）都是
#   过程量，可判定性才是结果量。decidable = 答出来了。
RE_DECID = re.compile(r"^\*\*可判定性\*\*:\s*(\w+)", re.M)
# ★ 头部「**调度**：修行(4圈) → 研究(4圈) → ...」里的**给定上限**。
#   为什么必须抽它：同题 mode 对照时，w61e(地铁×F) 是 12 圈 185 calls、
#   w61f(IC×H) 也是 12 圈 181 calls，而对照组只有 4 圈。差值几乎全是
#   圈数造成的，却被记成了 mode 的差 —— 这个混杂因子漏一次就白跑一轮。
RE_DISPATCH_CAP = re.compile(r"(\d+)圈")
# ★ 覆盖率的分母（`1 池` 那段「子问题 N 条：可判定 X / 不可判定 Y」）。
#   为什么必须连分母一起看：同一格六份产物的可判定子问题数是
#   **2 / 3 / 5 / 1 / 0 / 0**，覆盖率却分别是 0 / 100 / 84 / 72 / 100 / 100%。
#   每个格子的**分母只有 0~5**，于是"波动"里很大一块是**测量粒度**：
#   分母 2 的时候分辨率就是 50pt，答对 2/2 和 0/2 之间不存在中间值。
#   要连分母一起看，否则只能对着假波动瞎猜。
RE_SUBN = re.compile(r"子问题\s*(\d+)\s*条[：:]\s*可判定\s*(\d+)\s*/\s*不可判定\s*(\d+)")
# ★ 产物第七节自带的「**代码实算：已答子问题 X/Y**」—— 这才是带分子分母的
#   原始值。头条那个百分比是模型自评 depth 加权的折算版，分子分母都不可见：
#   「100%」既可能是 2/2 也可能是 200/200，两者根本不是一回事。
RE_ANSXY = re.compile(r"代码实算：已答子问题\s*(\d+)\s*/\s*(\d+)")
# ★ 可判定覆盖率 = 已答子问题 / 子问题总数。
#   这是**唯一不受 8 条截断影响**的答案量口径 —— 方面清单在
#   `_merge_decidability` 里被 `dec_aspects[:8]` / `und_aspects[:8]` 截断，
#   实测所有产物都落在 7~8 条，已经饱和，拿它比较「谁答得多」会得出
#   「大家都一样」的假结论（我第一版就栽在这）。覆盖率没有上限，能用。
RE_COVER = re.compile(r"可判定覆盖率\s*([\d.]+)%")
# [v1.21.61] 清算行改成「可判定覆盖率 X/Y（nn%）」—— 百分比单独存在，
#   同一个 100% 可能是 1/1 也可能是 20/20（实测 var_a/b/c：1/1、5/5、1/1）。
#   优先读新格式；老产物没有 X/Y，退回上面的旧格式（只拿得到百分比）。
RE_COVER_XY = re.compile(r"可判定覆盖率\s*(\d+)/(\d+)（([\d.]+)%）")
# [v1.21.61] 老的 374 份产物头条印的是**研究层收尾快照**，之后是**终局值**。
#   两者不可直接混着比；新产物在下一行留了快照值，抽出来才能跟老数据对齐。
RE_SNAP = re.compile(r"研究层收尾时是\s*([\d.]+)%")
# [v1.21.62] 三态判决一致率。这条是**质量指标的质量指标** ——
#   判决书本身不稳的话，上面所有百分比都不必当真。实测改动前同一份配置的
#   ANSWERABLE 在 1~5 之间跳（var_a~c / set_a~b 五份：1、5、1、3、3），
#   而那时产物里没有任何一行能提示读者"这个分母不可信"。
#   老产物没有这一行，抽不到就留 None，不要拿 0 冒充。
RE_TRI = re.compile(
    r"\*\*三态判决一致率\*\*：(\d+)\s*/\s*(\d+)（([\d.]+)%）")
# 停止判据被「未深入方向」推迟：N 次 + 被推迟的那条判据原文。
# ★ 这条是**判据可达性**的直接证据 —— 判据其实成立了，只是被"还有方向
#   没碰"挡下来。历史上 19 次「体力耗尽」里 9 次属于这种谎报。
RE_DEFER = re.compile(
    r"(\d+)\s*次停止判据被「未深入方向」推迟(?:（([^）]*)）)?")


def scan_output(path: Path) -> dict:
    """从产物里按层抽出：实际圈数 / 停止理由 / 清算 / 质量。"""
    res = {"layers": {}, "error": "", "pmode": "-", "dispatch": "-",
           "cap_vec": (), "cap_max": None}
    if not path or not path.exists():
        res["error"] = "产物缺失"
        return res
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        res["error"] = str(e)
        return res

    # 产物头部自带调度与模式。★ 这是**产物自己写的**，比从日志文件名猜可靠
    # —— 文件名里的模式是调用方给的，产物里的是实际生效的。
    m = re.search(r"\*\*并行模式\*\*：(\S+)", txt)
    if m:
        res["pmode"] = "serial" if m.group(1) == "严格串行" else m.group(1)
    m = re.search(r"\*\*调度\*\*：(.+)", txt)
    if m:
        res["dispatch"] = m.group(1).strip()
        _caps = tuple(int(x) for x in RE_DISPATCH_CAP.findall(m.group(1)))
        res["cap_vec"] = _caps
        res["cap_max"] = max(_caps) if _caps else None
    m = RE_DECID.search(txt)
    res["decidability"] = m.group(1) if m else "-"
    # ★ 三个**不经过模型自评**的替代观测量。
    #   为什么需要它们：覆盖率 0% 与 100% 的两份同题产物放在一起比，
    #   可判定方面都是 9 条、字数 47.7k vs 52.2k —— 内容量几乎一样。
    #   也就是说「0~100%」这个极差里，有一部分是指标崩了，不是质量差了。
    #   覆盖率分子用模型自评的 depth 加权、分母看子问题是否被标成
    #   answered/deferred，两处都能因一次标注差异整体归零。
    #   ⚠️⚠️ `aspects`（可判定方面条数）**本身是饱和的**：97 份产物里
    #   60 份恰好等于 9（上限）。拿它区分好坏等于拿一把封顶的尺 ——
    #   这是本项目第二次栽在饱和口径上（上一次是 `_merge_decidability`
    #   的 `dec_aspects[:8]`，第七章为此推翻过一次结论）。它只能用来
    #   判「有没有输出」，不能用来判「输出多少」。
    #   真正不饱和的两个：字数（7k~64k）、债/未回访条目数（0~数十）。
    res["aspects"] = len(re.findall(r"^- 📗 可判定", txt, re.M))
    res["chars"] = len(txt)
    res["debts"] = txt.count("债务") + txt.count("未回访") + txt.count("挂账")
    _m = RE_SUBN.search(txt)
    res["qa_dec"] = int(_m.group(2)) if _m else None   # 分母：可判定子问题数
    _xy = RE_ANSXY.search(txt)
    res["ans_x"] = int(_xy.group(1)) if _xy else None
    res["ans_y"] = int(_xy.group(2)) if _xy else None  # 代码实算的分母

    _mx = RE_COVER_XY.search(txt)
    if _mx:
        res["coverage"] = float(_mx.group(3))
        # 新的清算行自带权威的分子分母，比第七节那行更准
        if res["ans_x"] is None:
            res["ans_x"] = int(_mx.group(1))
            res["ans_y"] = int(_mx.group(2))
    else:
        m = RE_COVER.search(txt)          # 老产物：只有百分比
        res["coverage"] = float(m.group(1)) if m else None
    _ms = RE_SNAP.search(txt)
    # ★ 老 374 份头条印的是**研究层收尾快照**，本版起改成终局值 —— 两者
    #   不能直接混。新产物在下一行留了快照值，抽出来就有了跟历史对齐的桥
    #   （老产物没有这一行，`snapshot_cov` 就取它自己的头条值）。
    if _ms:
        res["snapshot_cov"] = float(_ms.group(1))
    else:
        _mo = RE_COVER.search(txt)
        res["snapshot_cov"] = float(_mo.group(1)) if _mo else None

    _mt = RE_TRI.search(txt)
    if _mt:
        res["tri_agree"] = int(_mt.group(1))
        res["tri_total"] = int(_mt.group(2))
        res["tri_rate"] = float(_mt.group(3))
    # ★ 三个键一起补 —— 下游只用 `r.get(...)` 取值，缺一个键不会报错，
    #   但会让「有条数、没比率」这种半截数据在统计里被当成有效样本。
    else:
        res["tri_agree"] = None
        res["tri_total"] = None
        res["tri_rate"] = None

    # 只在「逐层明细」区间内切层 —— 后面的复述段也有同类字段，会重复计数
    s = DETAIL_START.search(txt)
    seg = txt[s.end():] if s else txt
    e = DETAIL_END.search(seg)
    if e:
        seg = seg[:e.start()]

    heads = [(m.start(), m.group(1), m.end()) for m in LAYER_HEAD.finditer(seg)]
    for i, (start, lid, hend) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(seg)
        body = seg[hend:end]
        lr = {"id": lid, "name": LAYER_NAMES.get(lid, lid)}

        m = RE_ROUNDS.search(body)
        lr["rounds"] = int(m.group(1)) if m else None
        lr["cap"] = int(m.group(2)) if (m and m.group(2)) else None

        m = RE_STOP.search(body)
        lr["stop_raw"] = m.group(1).strip() if m else ""
        lr["stop"] = classify_stop(lr["stop_raw"]) if lr["stop_raw"] else "-"
        md = RE_DEFER.search(lr["stop_raw"])
        lr["defer_n"] = int(md.group(1)) if md else 0
        lr["defer_what"] = (md.group(2) or "")[:40] if md else ""

        m = RE_CLOSURE.search(body)
        if m:
            lr["clean"] = m.group(1)
            # 未交代的**比例**比 clean 布尔有区分力：clean 要求每条对撞
            # 张力都被元层以相似度 ≥0.6 覆盖一次，实测 89 次里只 clean 了
            # 7 次（8%）—— 一个几乎恒为假的口径分不出好坏。
            lr["duel_total"] = int(m.group(2))
            lr["unsettled"] = int(m.group(3))
        m = RE_DIST.search(body)
        lr["dist"] = float(m.group(1)) if m else None
        m = RE_QFLAG.search(body)
        lr["qflag"] = m.group(1).strip() if m else ""
        lr["debt_active"] = len(RE_DEBT.findall(body))
        res["layers"][lid] = lr

    # ★ 给定圈数优先取**层自己写的上限**（层体「上限 N 圈」），只有当
    #   层数据缺失时才退回头部的 `**调度**：...` 行。
    #   为什么不信头部：老产物的头部写的是**请求**圈数，元层 +1 的
    #   all_extra_rounds 没算进去（同一份产物里头部 4 圈、层里 5 圈）。
    #   头部已在 v1.21.61 修好，但历史那批产物改不了 —— 只能统一按层体读。
    _caps = [res["layers"][e]["cap"] for e in ("0", "1", "both", "all")
             if e in res["layers"] and res["layers"][e].get("cap")]
    if len(_caps) == len(res["layers"]) and _caps:
        res["cap_vec"] = tuple(_caps)
        res["cap_max"] = max(_caps)
    return res


# ---------------- 汇总 ----------------

def collect(pattern: str):
    """两条路合并，样本最大化 —— 这是**不花钱**就把统计变可信的办法。

      ① 日志 → 产物：有 mode/calls/decidability，信息最全（近期跑批）
      ② 产物 → 日志：老产物没有「产物=」行可循，用 mtime 反查最近的日志。
         配不上就把 mode/calls 记为 '-'，层数据照样算 —— 圈数和停止理由
         是收敛的核心观测量，有没有 mode 不影响它们成立。
    """
    # ★ 先扫一遍把「哪些产物已经有主」登记下来，再处理猜测。
    #   顺序敏感：按文件名排，`probe_stability.log` 比它的主人
    #   `v60_p61F_rauto_B.log` 排得早 —— 边扫边判时主人还没登场，
    #   避让就失效了（实测 5 份产物被二次认领）。DTO-self-own 优先。
    _claimed = set()
    for lp in sorted(HERE.glob(pattern)):
        _d = scan_log(lp)
        if _d.get("out") and _d.get("out_src") == "log":
            _claimed.add(_d["out"].resolve())

    rows = []
    used_out = set()
    used_logs = set()
    for lp in sorted(HERE.glob(pattern)):
        r = scan_log(lp)
        used_logs.add(lp.resolve())
        if r.get("error"):
            rows.append(r)
            continue
        out = r.get("out")
        # ★ mtime 是**猜**的，猜到别人已经有主的产物要认赔。
        #   实测：`v61_crit.log` / `v61_fhg.log` 本身没写「产物=」（那批跑
        #   的落盘路径没进日志），mtime 于是配到了 `v60_c61G_r4_G.log`
        #   和 `v60_v61G_r4_G.log` 的产物上 —— 同一跑在逐层统计里被数了
        #   两遍。DTO自己和自己的日志才是主。
        if out and r.get("out_src") == "mtime" and out.resolve() in _claimed:
            r["out"] = None
            out = None
            r["out_src"] = "mtime-collision"
        o = scan_output(out)
        r["oerr"] = o["error"]
        r["layers"] = o["layers"]
        # 产物写了实际模式就用产物的（日志文件名里的是调用方意图）
        if o.get("pmode", "-") != "-":
            r["mode"] = o["pmode"]
        r["dispatch"] = o.get("dispatch", "-")
        r["cap_max"] = o.get("cap_max")
        r["cap_vec"] = o.get("cap_vec", ())
        r["decidability"] = o.get("decidability", "-")
        r["coverage"] = o.get("coverage")
        for _pk in ("aspects", "chars", "debts", "qa_dec",
                    "ans_x", "ans_y", "snapshot_cov",
                    "tri_agree", "tri_total", "tri_rate"):
            r[_pk] = o.get(_pk)
        if out and not o["error"]:
            used_out.add(out.resolve())
        r["gen"] = gen_of(o["layers"])
        r["qtype"] = guess_type((out.name if out else "") + " " + r["file"])
        r["qname"] = (out.name.split("_", 2)[2][:20]
                      if out and out.name.count("_") >= 2 else "?")
        rows.append(r)

    # ② 补充：没被日志引用过的产物
    # ★ 只在扫全量时才补 —— 传了具体 glob 说明只想看那几个 run，
    #   这时把全部产物塞进来会把筛选意图冲掉。
    logs = sorted(HERE.glob(pattern))
    orphans = ((HERE / "outputs").glob("*.md")
               if pattern in ("*.log", "v60_*.log") else [])
    for op in sorted(orphans):
        if op.resolve() in used_out:
            continue
        o = scan_output(op)
        if o["error"] or not o["layers"]:
            continue
        r = {"file": "-" , "log": None, "error": "", "oerr": "",
             "mode": "-", "r_tag": "-", "tag": "-", "calls": None,
             "tokens": None, "decidability": "-", "divergent": "-",
             "route": "-", "p_mode": "-", "rounds": "-", "profile": "-",
             "budget": "-", "推迟": 0, "预算用尽次数": 0,
             "out": op, "out_src": "orphan"}
        lg = guess_log_by_mtime(op, logs)
        # ★ 一个 run 只有一份产物。若 mtime 把两份不同的产物配到同一份
        #   日志上，说明其中一次配对是错的（实测：复杂问题 E @4/4/4/4 出了
        #   3 行，其中两行 calls 同为 161 却一个 100% 一个 41%，多出来的
        #   那份产物借了别人的日志）。重复计数会把中位数带偏，直接丢。
        if lg and lg.resolve() in used_logs:
            continue
        if lg:
            d = scan_log(lg)
            used_logs.add(lg.resolve())
            for k in ("mode", "r_tag", "tag", "calls", "tokens",
                      "decidability", "divergent", "route", "p_mode",
                      "rounds", "profile", "budget", "推迟"):
                r[k] = d.get(k, "-")
            r["file"] = lg.name
        r["layers"] = o["layers"]
        r["gen"] = gen_of(o["layers"])
        r["mode"] = o.get("pmode", "-")
        r["dispatch"] = o.get("dispatch", "-")
        r["cap_max"] = o.get("cap_max")
        r["cap_vec"] = o.get("cap_vec", ())
        r["decidability"] = o.get("decidability", "-")
        r["coverage"] = o.get("coverage")
        for _pk in ("aspects", "chars", "debts", "qa_dec",
                    "ans_x", "ans_y", "snapshot_cov",
                    "tri_agree", "tri_total", "tri_rate"):
            r[_pk] = o.get(_pk)
        r["qtype"] = guess_type(op.name)
        r["qname"] = op.name.split("_", 2)[2][:20] \
            if op.name.count("_") >= 2 else op.name[:20]
        rows.append(r)
    return rows


def guess_log_by_mtime(md_path: Path, logs):
    """产物 → 日志：找它之前最近的那份日志（同一次跑批）。"""
    t0 = md_path.stat().st_mtime
    best, best_dt = None, None
    for lp in logs:
        dt = t0 - lp.stat().st_mtime
        if dt < -60 or dt > 1800:     # 日志比产物还新，或早于 30min：不是
            continue
        if best_dt is None or dt < best_dt:
            best, best_dt = lp, dt
    return best


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_layers = "--layers" in sys.argv
    # 默认扫全部日志（v60_* 是一批，v61_*/cost_*/ab_* 是另一批，都算真跑）
    pattern = args[0] if args else "*.log"

    rows = collect(pattern)
    have = [r for r in rows if not r.get("error") and r["layers"]]
    if "--old" in sys.argv:
        ok = have
        note = "（含老配置 3 圈数据）"
    else:
        ok = [r for r in have if r.get("gen") == "cur"]
        note = f"（另有 {len(have)-len(ok)} 份老配置 3 圈数据已排除，"
        note += "加 --old 看）"
    # --q=F 只看某类题。用来检查「层×上限」的结论在不同题型下稳不稳 ——
    # 汇总表可能是 Simpson 悖论（混合题型造出来的假规律）。
    _q = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--q=")]
    if _q:
        ok = [r for r in ok if r["qtype"] in _q]
        note += f" 题型过滤={','.join(_q)}"
    if not ok:
        print(f"没有可用的 run（匹配 {pattern} 共 {len(rows)} 份）")
        return

    print(f"=== 收敛矩阵：{len(ok)}/{len(rows)} 个 run 抽到了层数据 {note} ===\n")

    # ---- 1. 逐 run ----
    hdr = (f"{'题型':<4}{'模式':<7}{'圈(给)':<7}{'实际圈 0/1/both/all':<22}"
           f"{'calls':<7}{'停止类别':<26}{'dec':<11}")
    print(hdr)
    print("-" * len(hdr))
    for r in ok:
        ls = r["layers"]
        actual = "/".join(str(ls[k]["rounds"]) if k in ls else "-"
                          for k in ("0", "1", "both", "all"))
        stops = ",".join(f"{ls[k]['stop']}" for k in ("0", "1", "both", "all")
                         if k in ls)
        print(f"{r['qtype']:<4}{r['mode']:<7}{r['r_tag']:<7}{actual:<22}"
              f"{str(r['calls']):<7}{stops:<26}{r['decidability']:<11}")

    # ---- 2. 收敛条件 → 圈数（这张表是选路的核心依据）----
    print("\n=== 收敛条件 → 实际圈数 ===")
    by_cat = defaultdict(list)
    for r in ok:
        for lid, lr in r["layers"].items():
            if lr["rounds"] is not None:
                by_cat[lr["stop"]].append((lr["rounds"], lid, r["file"]))
    print(f"  {'类别':<8}{'次数':<7}{'圈数 中位/最小-最大':<22}{'出现在哪些层'}")
    for cat in ("安住", "空转", "清算", "走满", "预算", "OTHER"):
        if cat not in by_cat:
            continue
        rs = sorted(x[0] for x in by_cat[cat])
        mid = rs[len(rs) // 2]
        layers = Counter(x[1] for x in by_cat[cat])
        ls = " ".join(f"{LAYER_NAMES.get(k, k)}{v}" for k, v in layers.items())
        flag = ""
        if cat == "OTHER":
            flag = "  ← ★ 有认不出的停止理由，去 classify_stop() 补"
        elif cat in ("走满", "预算"):
            flag = "  ← 被迫停，非收敛"
        print(f"  {cat:<8}{len(rs):<7}{f'{mid} / {rs[0]}-{rs[-1]}':<22}{ls}{flag}")

    # ---- 2b. 被迫停的细分：走满里有多少其实是「判据已成立但被推迟」----
    forced = [(lr, r["file"]) for r in ok for lr in r["layers"].values()
              if lr["stop"] in ("走满", "预算")]
    if forced:
        lie = [x for x in forced if x[0].get("defer_n", 0) > 0]
        print(f"\n  被迫停 {len(forced)} 次，其中 {len(lie)} 次"
              f"「停止判据曾被『未深入方向』推迟」——判据其实成立过，"
              f"只是被挡下来")
        if lie:
            what = Counter(x[0]["defer_what"][:16] for x in lie)
            print("    被推迟的判据："
                  + "；".join(f"{k}×{v}" for k, v in what.most_common(4)))

    # ---- 3. 题型 × 模式 ----
    print("\n=== 题型 × 模式：成本与收敛 ===")
    cell = defaultdict(list)
    for r in ok:
        cell[(r["qtype"], r["mode"])].append(r)
    print(f"  {'题型·模式':<14}{'n':<4}{'calls 中位':<12}"
          f"{'自然停占比':<12}{'被迫停占比':<12}{'未交代(元)'}")
    NATURAL = ("安住", "空转", "清算")
    for k in sorted(cell):
        rs = cell[k]
        calls = sorted(x["calls"] for x in rs if x["calls"] is not None)
        cmid = calls[len(calls) // 2] if calls else "-"
        allstops = [lr["stop"] for x in rs for lr in x["layers"].values()]
        nat = sum(1 for s in allstops if s in NATURAL) / max(len(allstops), 1)
        forced = sum(1 for s in allstops if s in ("走满", "预算")) \
            / max(len(allstops), 1)
        uns = [x["layers"]["all"]["unsettled"] for x in rs
               if "all" in x["layers"] and "unsettled" in x["layers"]["all"]]
        uavg = f"{sum(uns)/len(uns):.1f}" if uns else "-"
        print(f"  {k[0]+'·'+k[1]:<14}{len(rs):<4}{str(cmid):<12}"
              f"{nat*100:.0f}%{'':<8}{forced*100:.0f}%{'':<8}{uavg}")

    # ---- 3b. ★ 选路核心表：层 × 给定上限 → 实际圈数 / 自然停率 ----
    #  「给 N 圈到底够不够」只能这样答：看给 N 圈时有多少层是自然停的。
    #   自然停率高 = 这个上限够用；走满多 = 还在爬坡，给少了。
    print("\n=== 层 × 给定上限 → 够不够用 ===")
    print(f"  {'层':<7}{'上限':<6}{'n':<5}{'实际圈 中位':<12}"
          f"{'自然停':<9}{'走满':<8}{'判据被推迟'}")
    grid = defaultdict(list)
    for r in ok:
        for lid, lr in r["layers"].items():
            if lr.get("cap") and lr.get("rounds") is not None:
                grid[(lid, lr["cap"])].append(lr)
    for (lid, cap) in sorted(grid, key=lambda k: (list(LAYER_NAMES).index(k[0])
                                                  if k[0] in LAYER_NAMES else 9,
                                                  k[1])):
        g = grid[(lid, cap)]
        rs = sorted(x["rounds"] for x in g)
        nat = sum(1 for x in g if x["stop"] in NATURAL) / len(g)
        ful = sum(1 for x in g if x["stop"] in ("走满", "预算")) / len(g)
        dfr = sum(1 for x in g if x.get("defer_n", 0) > 0)
        print(f"  {LAYER_NAMES.get(lid, lid):<7}{cap:<6}{len(g):<5}"
              f"{rs[len(rs)//2]:<12}{nat*100:.0f}%{'':<5}"
              f"{ful*100:.0f}%{'':<4}{dfr}")

    # ---- 3c. route 层数 → 成本（层数是最粗的成本旋钮）----
    print("\n=== route 层数 → 成本 ===")
    bylen = defaultdict(list)
    for r in ok:
        n = len(r["layers"])
        if r["calls"]:
            bylen[n].append(r["calls"])
    for n in sorted(bylen):
        g = sorted(bylen[n])
        print(f"  {n} 层（n={len(g)}）：calls {min(g)}~{max(g)}，"
              f"中位 {g[len(g)//2]}")

    # ---- 3d. ★ 层数 → 输出质量（砍层到底伤不伤质量，只看这一张）----
    #   过程指标（自然停/未交代）都说不清"结果好不好"，可判定性才是结果量：
    #   decidable = 答出来了。砍层若换来 partial/undecidable，那就是假省钱。
    print("\n=== route 层数 → 输出质量（可判定性）===")
    dec = defaultdict(lambda: Counter())
    for r in ok:
        d = r.get("decidability", "-")
        if d == "-":
            continue
        dec[len(r["layers"])][d] += 1
    _order = ("decidable", "partial", "undecidable")
    for n in sorted(dec):
        c = dec[n]
        tot = sum(c.values())
        _s = "  ".join(f"{k} {c.get(k,0)}" for k in _order)
        print(f"  {n} 层（n={tot}）：{_s}"
              f"   答出来 {c.get('decidable',0)/tot*100:.0f}%")
    print("  ⚠️ 层数是**自选**的（auto 按题给），不是随机分组 ——")
    print("     简单题天然被给少层。要看真因果得按题型分层（--q=F 等）。")

    # ---- 3e. ★ 题型 × 层数：控制住难度这个混杂因子 ----
    print("\n=== 题型 × 层数 → 成本 / 答出来率 ===")
    xd = defaultdict(lambda: [0, 0, []])
    for r in ok:
        d = r.get("decidability", "-")
        if d == "-":
            continue
        a = xd[(r.get("qtype"), len(r["layers"]))]
        a[0] += 1
        if d == "decidable":
            a[1] += 1
        if r["calls"]:
            a[2].append(r["calls"])
    for k in sorted(xd, key=lambda x: (str(x[0]), x[1])):
        n, hit, cs = xd[k]
        _med = sorted(cs)[len(cs)//2] if cs else 0
        print(f"  题型{k[0]}  {k[1]}层：n={n}  中位 {_med} calls  "
              f"答出来 {hit}/{n} = {hit/n*100:.0f}%")

    # ---- 3f. ★ 三态到底差在哪：是「答得少」还是「多说了说不清」----
    #   这条解释力最强，也最容易被误读：partial 看着像"没答全"，实测它的
    #   可判定方面数和 decidable **一样多**。差的是多出来的不可判定方面
    #   —— 归一化规则「有任何 und 方面就把 decidable 降 partial」在起作用。
    print("\n=== 三态的方面清单条数（⚠️ 饱和口径，别拿它比答案量）===")
    asp = defaultdict(lambda: [0, 0, 0])
    for op in sorted((HERE / "outputs").glob("*.md")):
        try:
            head = op.read_text(encoding="utf-8", errors="replace")[:3000]
        except Exception:
            continue
        mm = re.search(r"^\*\*可判定性\*\*:\s*(\w+)", head, re.M)
        if not mm:
            continue
        a = asp[mm.group(1)]
        a[0] += len(re.findall(r"^- 📗 可判定", head, re.M))
        a[1] += len(re.findall(r"^- 📘 不可判定", head, re.M))
        a[2] += 1
    for k in ("decidable", "partial", "undecidable"):
        a = asp.get(k)
        if not a or not a[2]:
            continue
        print(f"  {k:<12} 可判定方面 {a[0]/a[2]:.1f}  "
              f"不可判定方面 {a[1]/a[2]:.1f}   n={a[2]}")
    print("  ⚠️ 两方面各被 `[:8]` 截断（`_merge_decidability`），值都落在")
    print("     7~8 说明已饱和 —— **不能**据此说「答案量一样」。")
    print("     要比答案量用下面的覆盖率（没有上限）。")

    # ---- 3g. ★ 真正能比答案量的口径：可判定覆盖率 ----
    print("\n=== 层数 → 可判定覆盖率（不受 8 条截断）===")
    cov = defaultdict(list)
    for r in ok:
        c = r.get("coverage")
        if c is not None:
            cov[len(r["layers"])].append(c)
    for n in sorted(cov):
        g = sorted(cov[n])
        print(f"  {n} 层（n={len(g)}）：中位 {g[len(g)//2]:.0f}%  "
              f"均值 {sum(g)/len(g):.0f}%  范围 {g[0]:.0f}~{g[-1]:.0f}%")
    print("  ⚠️ 层数自选（简单题天然给少层），这张表不能定因果；")
    print("     要定论得做同题 2 层 vs 4 层对照（V60_ROUTE=light/full）。")

    # ---- 3h. ★ 同题 × mode 对照：mode 是五维里唯一没被系统分析过的 ----
    #   ⚠️ 必须**同题**比。跨题比会直接反：O 类里 serial 看着只有 40% 覆盖
    #   率、并行模式 96%，其实 serial 跑的 5 个样本是「如何与之相处」这类
    #   哲学题，H/B 跑的是「怎么衡量地铁运营效率」—— 题不一样，不是 mode
    #   的差。（连着三轮栽在混杂上，这张表只收同题样本。）
    #   ⚠️⚠️ 第二道混杂：**给定圈数**。圈数从 4 到 12，calls 差一倍以上，
    #   一旦某格是 12 圈、另一格是 4 圈，比出来的全是圈数不是 mode。
    #   所以这里既按题分组、又按 cap_vec 分组，两组完全同题同圈才进表。
    _CAP_LIMIT = 6        # 超过这个值的样本属于「12 圈污染」，直接排除
    print(f"\n=== 同题 × mode（同给定圈数，上限 ≤{_CAP_LIMIT}）===")
    tm = defaultdict(lambda: defaultdict(list))
    excluded = defaultdict(list)
    for r in ok:
        if len(r["layers"]) != 4 or r.get("coverage") is None:
            continue
        if not r["calls"] or not r.get("out"):
            continue
        _n = r["out"].name
        _key = ("地铁" if "地铁" in _n else
                "IC" if "IC" in _n else
                "复杂问题" if "复杂问题" in _n else None)
        if not _key:
            continue
        _cm = r.get("cap_max")
        if _cm and _cm > _CAP_LIMIT:
            excluded[_key].append((r.get("mode") or "?", _cm, r["calls"],
                                   r["coverage"]))
            continue
        tm[(_key, r.get("cap_vec"))][r.get("mode") or "?"].append(
            (r["coverage"], r["calls"]))
    for _k in ("地铁", "IC", "复杂问题"):
        for (_kk, _cv), _ms in sorted(tm.items(), key=lambda x: str(x[0])):
            if _kk != _k:
                continue
            _CAP = f"给定 {'/'.join(str(x) for x in _cv)}"
            _keep = {m: v for m, v in _ms.items()}
            print(f"  【{_k}】{_CAP}  ← 圈数相同才可横比")
            # 先看有没有两种以上模式跑过同样圈数
            _solid = {m: v for m, v in _keep.items() if len(v) >= 2}
            for _m in sorted(_keep, key=lambda x: (-len(_keep[x]), str(x))):
                v = sorted(_keep[_m])
                cov = [x[0] for x in v]
                cal = sorted(x[1] for x in v)
                _tag = "" if len(v) >= 2 else "   ← n=1 仅供参考"
                print(f"    {_m:<7} n={len(v):<3} 覆盖率 {cov[len(cov)//2]:>5.0f}%"
                      f"   calls {cal[len(cal)//2]:>4}"
                      f"   ({cal[0]}~{cal[-1]}){_tag}")
            if len(_solid) < 2:
                print("      ⚠️ 只有一种模式有 ≥2 个样本，尚无对照结论，"
                      "需再跑同圈数的另一种模式")
        if excluded.get(_k):
            _s = "、".join(f"{m}@{c}圈/{ca}calls" for m, c, ca, _ in excluded[_k])
            print(f"    ⚠️ 已排除 {len(excluded[_k])} 个高圈数样本（{_s}）"
                  f" —— 圈数不同不可比")

    # ---- 3i. ★★ 重复性：成本μ-main-质量间的相对可预测性 ----
    #   为什么单列一节：这才是本轮最值钱的发现。同题 + 同模式 + 同层上限
    #   重复跑，**calls 几乎不动，覆盖率能差 100pt**。于是「省钱」和
    #   「保质量」是两类完全不同的手段：前者靠结构（层数/圈数），后者靠
    #   冗余（多次取好）。没有这一节，上面所有单次观测的表都会被误读。
    print("\n=== 重复性：同一格里成本和质量各自稳不稳 ===")
    _cells = defaultdict(list)
    for r in ok:
        if len(r["layers"]) != 4 or r.get("coverage") is None:
            continue
        if not r["calls"] or not r.get("out"):
            continue
        _cv = r.get("cap_vec") or ()
        if any(c > _CAP_LIMIT for c in _cv):
            continue
        _q = r["out"].name.split("_", 2)[-1][:14]
        _cells[(_q, _cv, r.get("mode") or "?")].append((
            r["coverage"], r["calls"],
            r.get("aspects"), r.get("chars"), r.get("debts"),
            r.get("qa_dec"), r.get("ans_x"), r.get("ans_y")))
    _rep = {k: v for k, v in _cells.items() if len(v) >= 2}
    print(f"  有重复观测的格子 {len(_rep)}/{len(_cells)}"
          f"（其余全是单次观测，那些格子的『好坏』不存在可比性）")
    print(f"  {'格子':<34}{'n':<4}{'覆盖率观测值':<24}"
          f"{'calls 波动':<14}{'单次':<6}{'2取好':<7}{'3取好'}")
    for _k in sorted(_rep, key=lambda x: -len(_rep[x])):
        v = _rep[_k]
        covs = sorted(x[0] for x in v)
        cals = sorted(x[1] for x in v)
        n = len(covs)
        mean1 = sum(covs) / n
        # 有放回抽 k 次取最大值的期望（用本格经验分布近似）
        e2 = sum(max(a, b) for a in covs for b in covs) / (n * n)
        e3 = (sum(max(a, b, c) for a in covs for b in covs for c in covs)
              / (n ** 3))
        _nm = f"{_k[0]} {_k[1]} {_k[2]}"
        print(f"  【{_nm}】n={n}  覆盖率 {[round(c) for c in covs]}"
              f"   calls {cals[0]}~{cals[-1]}")
        # ★ 若覆盖率摆得厉害、而这三个**不自评**的量几乎不动，那就是
        #   打分崩了（覆盖率对 answered/deferred 的标注过敏），不是质量
        #   真的飘 —— 这两种情况要走的动作完全不同。
        _asp = [x[2] for x in v if x[2] is not None]
        _ch = [x[3] for x in v if x[3] is not None]
        _db = [x[4] for x in v if x[4] is not None]
        # ★ 判「打分崩了」要看**不饱和**的量。若字数和欠债条目数几乎
        #   不动、覆盖率却差了几十个百分点，崩的是打分那一侧
        #   （对 answered/deferred 的标注过敏），不是质量真的在飘。
        #   这两种情况后续动作完全不同：前者该修指标，后者才该做冗余。
        _qm = [x[5] for x in v]                        # 池标题的可判定子问题数
        _xyv = [(x[6], x[7]) for x in v if x[7] is not None]   # 代码实算 x/y
        print(f"      代码实算「已答/总数」{[f'{a}/{b}' for a, b in _xyv]}"
              f"   池标题可判定数 {_qm}"
              + ("   ← ⚠️ 分母 ≤3：这个格的『波动』至少有一半是测量粒度"
                 if _qm and all(q is not None and q <= 3 for q in _qm) else ""))
        _flag = ""
        if (_ch and covs[-1] - covs[0] >= 40
                and max(_ch) / max(min(_ch), 1) <= 1.25):
            _flag = ("  ← ⚠️ 字数几乎不动（±%.0f%%）、覆盖率却差 "
                     "%dpt：先看上面的分母，多半是测量粒度问题"
                     % ((max(_ch) / max(min(_ch), 1) - 1) * 100,
                        covs[-1] - covs[0]))
        print(f"      替代量（不饱和）：字数k {[round(c/1000) for c in _ch]}"
              f"   债/未回访 {_db}"
              f"   ｜方面条数 {_asp}（⚠️ 62% 的样本顶在上限，别用）"
              f"{_flag}")
        print(f"      单次 {mean1:.0f}% → 2取好 {e2:.0f}% → 3取好 {e3:.0f}%"
              f"（calls 单次中位 {cals[len(cals)//2]}）")
    if _rep:
        _sp_c = [max(x[0] for x in v) - min(x[0] for x in v)
                 for v in _rep.values()]
        _sp_d = [(max(x[1] for x in v) / max(min(x[1] for x in v), 1) - 1)
                 for v in _rep.values()]
        print(f"  ★ 格内覆盖率极差 中位 {sorted(_sp_c)[len(_sp_c)//2]:.0f}pt，"
              f"格内 calls 波动 中位 {sorted(_sp_d)[len(_sp_d)//2]*100:.0f}%"
              f" —— 成本可预测，质量不可预测")
        print("  ⚠️ 「k 取好」的期望是**上界**：需要事先知道哪份好，而现在的"
              "判优标准是覆盖率，其分子来自模型自评 depth —— 会被自己抬高。")

    # ---- 4. 成本模型：calls ~ 层实际圈数之和 ----
    print("\n=== 成本模型 ===")
    pairs = []
    for r in ok:
        tot = sum(lr["rounds"] for lr in r["layers"].values()
                  if lr["rounds"] is not None)
        if r["calls"] and tot:
            pairs.append((tot, r["calls"], r["qtype"]))
    if pairs:
        for lo, hi in ((0, 8), (9, 12), (13, 16), (17, 99)):
            g = [c for t, c, _ in pairs if lo <= t <= hi]
            if g:
                print(f"  总圈数 {lo}-{hi}（n={len(g)}）：calls "
                      f"{min(g)}~{max(g)}，中位 {sorted(g)[len(g)//2]}")
        calls_per = [c / t for t, c, _ in pairs]
        print(f"  平均每圈 {sum(calls_per)/len(calls_per):.1f} calls"
              f"（{len(pairs)} 个 run）")

    # ---- 4a. 「给多不等于跑多」到底省多少 ----
    # 这句话容易被当成"随便给，反正不跑"。量化一下：只省 6%，
    # 所以圈数**仍然是成本主驱动**，不能靠它当免死金牌。
    print("\n=== 给的圈 vs 跑的圈（只统计上限 ≤6 的当前配置）===")
    agg = defaultdict(lambda: [0, 0, 0])
    for r in ok:
        for lid, lr in r["layers"].items():
            cap, rd = lr.get("cap"), lr.get("rounds")
            if cap and rd is not None and cap <= 6:
                a = agg[lid]
                a[0] += cap
                a[1] += rd
                a[2] += 1
    tg = tr = 0
    for lid in ("0", "1", "both", "all"):
        if lid not in agg:
            continue
        c, rd, n = agg[lid]
        tg += c
        tr += rd
        print(f"  {LAYER_NAMES[lid]:<5}给{c:>5} 跑{rd:>5} 省{c-rd:>4}"
              f"（{(c-rd)/c*100:>2.0f}%）  n={n}")
    if tg:
        print(f"  合计 给{tg} 跑{tr} 省{tg-tr}"
              f" → 只省 {(tg-tr)/tg*100:.0f}%，圈数仍是成本主驱动")

    # ---- 4b. 质量线索：输出质量的把关口径 ----
    # 线索目前是**标记**为主（只有 candidates_backfilled 会联动自省），
    # 不自动纠正 —— 所以它们正是人该盯的地方。
    print("\n=== 质量线索（按层）===")
    qc = Counter()
    qc_layer = defaultdict(Counter)
    for r in ok:
        for lid, lr in r["layers"].items():
            for f in (lr.get("qflag") or "").split(","):
                f = f.strip().split("(")[0]
                if f and f != "无":
                    qc[f] += 1
                    qc_layer[f][lid] += 1
    if not qc:
        print("  （无）")
    for f, n in qc.most_common(8):
        where = " ".join(f"{LAYER_NAMES.get(k, k)}{v}"
                         for k, v in qc_layer[f].most_common())
        print(f"  {f:<30}{n:>4} 次   {where}")

    # ---- 5. 判据健康 ----
    print("\n=== 判据 ===")
    dc = Counter(r["decidability"] for r in ok)
    print("  decidability：" + "  ".join(f"{k}={v}" for k, v in dc.items()))
    dv = sum(1 for r in ok if str(r["divergent"]).startswith("True"))
    print(f"  池判/外判分叉：{dv}/{len(ok)}")
    unclean = sum(1 for r in ok
                  if r["layers"].get("all", {}).get("clean") == "False")
    has_all = sum(1 for r in ok if "all" in r["layers"])
    print(f"  元层闭环未清算：{unclean}/{has_all}")

    # ---- 6. 数据缺口（决定下一批补跑什么）----
    print("\n=== 缺口 ===")
    no_out = [r["file"] for r in rows if not r.get("error") and r.get("oerr")]
    if no_out:
        print(f"  产物抽不到（{len(no_out)}）：{', '.join(no_out[:6])}")
    unk = [r["file"] for r in ok if r["qtype"] == "?"]
    if unk:
        print(f"  题型没认出（{len(unk)}）：{', '.join(unk[:6])}"
              "  ← 去 QUESTION_TYPES 补关键词")
    seen = Counter((r["qtype"], r["mode"]) for r in ok)
    thin = [k for k, v in seen.items() if v < 2]
    if thin:
        print("  样本 <2 的格子：" + "、".join(f"{a}·{b}" for a, b in thin))

    if show_layers:
        print("\n=== 逐层明细 ===")
        for r in ok:
            print(f"\n[{r['file']}] {r['qname']}  题型={r['qtype']} "
                  f"模式={r['mode']}  calls={r['calls']}")
            for lid in ("0", "1", "both", "all"):
                lr = r["layers"].get(lid)
                if not lr:
                    continue
                print(f"   {lr['name']}层 {lid:<5} "
                      f"实际{lr['rounds']}圈(上限{lr['cap']})  "
                      f"停={lr['stop']:<6} "
                      f"clean={lr.get('clean','-')} "
                      f"未交代={lr.get('unsettled','-')} "
                      f"距离={lr.get('dist','-')} "
                      f"债={lr['debt_active']}")
                if lr["stop_raw"]:
                    _df = (f"  ⚠推迟{ lr['defer_n']}次：{lr['defer_what']}"
                           if lr.get("defer_n") else "")
                    print(f"        └ {lr['stop_raw'][:78]}{_df}")
                if lr["qflag"]:
                    print(f"        ⚑ {lr['qflag'][:78]}")


if __name__ == "__main__":
    main()

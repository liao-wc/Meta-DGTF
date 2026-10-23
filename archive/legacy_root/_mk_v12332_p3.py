#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.32 补丁第 3 段（吸收清单第二批，7 项，全部为读数/结构，不改行为）。

⑦ 截断两向记账（AgentExit）：省了多少圈 / 丢了几个 core 问项
⑨ 预设检查（语用学）：预设失败是「答非所问」的真实来源
⑩ 言语行为标注（Austin/Searle）：承诺/断言/请求 —— 全是「请求」= 公文体
⑪ FMEA 可检测性（安全工程）：不可检测的失败最危险
⑫ 多样性预算（Ashby 必要多样性定律）：固定层×通道的多样性有上限
⑬ nogoods 矛盾档案（ftl-beliefs）：矛盾 append-only，不覆盖
⑭ 输入自检加不可见字符 / 指令注入（llm-guard 的规则类）
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.32.py"


def _load(p=SRC):
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF"
    assert b.count(b"\r\r\n") == 0, "含 CRCRLF"
    return b.decode("utf-8").replace("\r\n", "\n")


def _save(s, p=SRC):
    assert "\r\r\n" not in s
    p.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))


def rep(s, old, new, what, expect=1):
    n = s.count(old)
    assert n == expect, "%s：命中 %d 次（要求 %d）" % (what, n, expect)
    return s.replace(old, new)


BLOCK = '''# ============================================================
# 学科吸收 · 第二批（读数与结构，不改行为）
# ============================================================

#: 不可见 / 同形类字符（llm-guard 的 InvisibleText 思路，只取规则类、不拉模型）。
_INVISIBLE_CHARS = ("\\u200b", "\\u200c", "\\u200d", "\\u2060", "\\ufeff",
                    "\\u00ad", "\\u2028", "\\u2029")
#: 指令注入的**规则类**特征（不判语义，只报形态）。
_INJECT_PATTERNS = ("忽略以上", "忽略前面", "无视上述", "ignore previous",
                    "ignore above", "disregard the above", "system:",
                    "assistant:", "你现在是", "从此以后你")
#: 预设触发式（语用学：预设失败 ⇒ 问的问题本身预设了未成立的东西）。
_PRESUP_PATTERNS = (
    ("为什么", "「为什么X」预设 X 成立"),
    ("为何", "「为何X」预设 X 成立"),
    ("什么时候停止", "预设存在停止时点"),
    ("如何避免", "「如何避免X」预设 X 必然发生"),
    ("怎样才能不", "预设当前状态是该被消除的"),
    ("既然", "「既然」预设前件为真"),
)


def input_red_flags(q: str) -> list:
    """[输入自检 · 规则类] 不可见字符 + 指令注入 + 预设式（**只报不改**）。

    ★ 依据：llm-guard 的 InvisibleText 与 PromptInjection 扫描器。
      本实现**只取规则类**（正则/字符表）—— 其 ML 扫描器会拉 transformers，
      与本项目「单文件零依赖」冲突。
    """
    _q = str(q or "")
    out = []
    for _c in _INVISIBLE_CHARS:
        if _c in _q:
            out.append({"kind": "invisible", "term": repr(_c),
                        "why": "不可见字符（零宽/软连字符），可能被用来隐藏内容"})
            break
    _low = _q.lower()
    for _p in _INJECT_PATTERNS:
        if _p.lower() in _low:
            out.append({"kind": "injection", "term": _p[:20],
                        "why": "指令注入式形态（要求覆盖既有指示）"})
            break
    for _p, _why in _PRESUP_PATTERNS:
        if _p in _q:
            out.append({"kind": "presupposition", "term": _p,
                        "why": _why})
            break
    return out


#: 言语行为的**动词特征**（Austin/Searle 的 illocutionary 分类，规则判定）。
_ILLOC_PATTERNS = (
    ("承诺", ("指派", "建立", "试点", "委托", "备案", "制定", "开展",
              "实施", "落地", "推动", "建设", "部署")),
    ("断言", ("是", "为", "等于", "达到", "存在", "表明", "说明", "显示",
              "意味着", "定义")),
    ("请求", ("应当", "应该", "建议", "需要", "要", "请", "期望", "呼吁",
              "不得", "必须")),
)


def illocution_of(text: str) -> str:
    """判一条行动的**言语行为类型**：承诺 / 断言 / 请求（判不出 ⇒ "其他"）。

    ★ 依据：言语行为论（Austin/Searle）—— `illocution`（在做什么）与
      `locution`（说了什么）必须分开。若一份「行动清单」**全是请求**、
      没有任何**承诺**（自己承担的动作），那就是祈使句堆砌，不是方案。
    """
    _t = str(text or "")
    for _k, _ws in _ILLOC_PATTERNS:
        if any(w in _t for w in _ws):
            return _k
    return "其他"


def illocution_dist(actions) -> dict:
    """行动清单的言语行为分布 + 判词（全是请求 ⇒ 公文体告警）。"""
    _d = {"承诺": 0, "断言": 0, "请求": 0, "其他": 0}
    _n = 0
    for a in (actions or []):
        _txt = ""
        if isinstance(a, dict):
            _txt = "%s%s" % (a.get("verb", ""), a.get("object", "")) \
                or str(a.get("text", ""))
        else:
            _txt = str(a)
        _d[illocution_of(_txt)] += 1
        _n += 1
    _verdict = ""
    if _n and _d["承诺"] == 0 and _d["请求"] >= max(1, _n // 2):
        _verdict = "公文体风险：全部/多数为「请求」，无「承诺」型动作（没人认领）"
    return {"dist": _d, "n": _n, "verdict": _verdict}


def cut_two_way(cut: bool, rounds_cap, rounds_run, duty: dict) -> dict:
    """**截断的两向记账**（AgentExit 的 Redundancy Steps vs Progress Degradation）。

    ★ 依据：截断省下了多少圈（正向），同时丢了多少 core 问项（**负向**）。
      只报一面的读数必然误导 —— 与「只升不降的指标是自欺」同源。
    ★ 本函数**只出读数**：截断仍按原判据停（不改停止行为）。
    """
    _d = duty or {}
    _miss = list(_d.get("missing_core") or [])
    _core = int(_d.get("core_total", 0) or 0)
    return {
        "cut": bool(cut),
        "rounds_cap": int(rounds_cap or 0),
        "rounds_run": int(rounds_run or 0),
        "saved_rounds": max(0, int(rounds_cap or 0) - int(rounds_run or 0))
        if not cut else 0,
        "lost_core": len(_miss),
        "core_total": _core,
        "note": ("截断：省（未跑满的余量不产生成本）与丢（core 未覆盖）"
                 "两面分开报，不合成一个判词"),
    }


def fmea_detectability(name: str, known_markers) -> str:
    """[FMEA] 一条失败模式的**可检测性**：能被已有判据/线索发现吗。

    ★ 依据：FMEA 的 RPN = 严重度 × 频度 × **可检测性** ——
      **不可检测的失败最危险**（它不会出现在任何读数里，只能等后果）。
      本函数只做**规则匹配**：失败模式名是否出现在已知标记集合里。
    """
    _n = str(name or "")
    _ms = [str(x) for x in (known_markers or []) if str(x).strip()]
    for _m in _ms:
        if _m and (_m in _n or _n in _m):
            return "可检测（有对应标记：%s）" % _m[:20]
    return "⚠️ **不可检测**（没有对应标记 —— 它不会出现在任何读数里）"


def diversity_budget(views, channels, mode) -> dict:
    """[Ashby 必要多样性定律] 本跑实际动用的**组合数**（层 × 通道 × 模式）。

    ★ 依据：控制器可用的状态多样性 ≥ 被控系统的扰动多样性，否则无法维持目标。
      固定四层 × 固定通道的多样性**有上限** —— 踩到上限时「跑得不好」
      不是工程缺陷，而是**控制论上不可能**。
      ⇒ 这是一个**读数**（提示谨慎读结论），**不是**分数。
    """
    _vs = views or {}
    _layers = [k for k in ("0", "1", "both", "all") if k in _vs]
    _ch = [str(x) for x in (channels or [])]
    _m = str(mode or "serial")
    _combos = max(0, len(_layers)) * max(0, len(_ch))
    return {"layers": len(_layers), "channels": len(_ch), "mode": _m,
            "combos": _combos,
            "note": "组合数 = 层数 × 通道数（模式另计）；"
                    "低于「层×通道满配」时，结论的可迁移性受限"}


'''


def main():
    s = _load()

    # 1) 纯函数块（插在学科吸收第一块之前）
    _anch = "# ============================================================\n" \
            "# 学科吸收：评分者一致性 / 测量尺度 / 停因级联 / 早期预警"
    s = rep(s, _anch, BLOCK + _anch, "第二批纯函数块")

    # 2) ⑦ 截断两向：View 字段 + 收尾计算
    s = rep(s, "    #: [CSD 早期预警] 逐圈序列的方差/AC1 读数（**只作读数**）。",
            "    #: [截断两向记账] 省了多少圈 / 丢了几个 core 问项（**两面分开报**）。\n"
            "    cut_two_way: dict = field(default_factory=dict)\n"
            "    #: [CSD 早期预警] 逐圈序列的方差/AC1 读数（**只作读数**）。",
            "View cut_two_way 字段")

    s = rep(s, '''        if _duty_fin and _duty_fin.get("short"):''',
            '''        # ★ [截断两向记账] 只报「省了什么」或只报「丢了什么」都会误导 ——
        #   两面必须一起出（AgentExit 的 Redundant Steps vs Progress Degradation）。
        try:
            _is_cut = any(k in str(view.stop_reason or "")
                          for k in ("体力耗尽", "预算用尽", "截断"))
            view.cut_two_way = cut_two_way(
                _is_cut, int(getattr(view, "rounds_cap", 0) or 0),
                int(getattr(view, "rounds_run", 0) or 0), _duty_fin or {})
        except Exception:
            view.cut_two_way = {}

        if _duty_fin and _duty_fin.get("short"):''',
            "截断两向计算")

    # 3) ⑨⑭ 输入自检：规则类 flags（不改 LLM 调用次数）
    s = rep(s, '''        return {
            "issues": issues,
            "note": str(data.get("note", ""))[:80],
            "checked": True,
        }''',
            '''        # ★ [规则类自检] 不可见字符 / 指令注入 / 预设式 —— **不计入 LLM 调用**，
        #   在既有检查之外补一层确定性判据（llm-guard 的规则类思路）。
        try:
            _rf = input_red_flags(question)
        except Exception:
            _rf = []
        return {
            "issues": issues,
            "note": str(data.get("note", ""))[:80],
            "checked": True,
            "rule_flags": _rf,
        }''',
            "输入自检规则类 flags")

    # 4) ⑩ 言语行为：行动清单后加分布行
    s = rep(s, '''        out.append(f"  - 回退：{a.get('fallback', '（未指定）')}\\n")''',
            '''        out.append(f"  - 回退：{a.get('fallback', '（未指定）')}\\n")
    # ★ [言语行为标注] 承诺 / 断言 / 请求 —— 全是「请求」= 公文体
    #   （言语行为论：一份清单若没有任何「承诺」，就没人真的认领）。
    try:
        _il = illocution_dist(actions)
        if _il.get("n"):
            _dd_ = _il["dist"]
            out.append("\\n> **言语行为分布**（承诺/断言/请求/其他）："
                       f"{_dd_.get('承诺', 0)}/{_dd_.get('断言', 0)}/"
                       f"{_dd_.get('请求', 0)}/{_dd_.get('其他', 0)}"
                       f"（n={_il['n']}）")
            if _il.get("verdict"):
                out.append("> ⚠️ " + _il["verdict"])
            out.append("\\n")
    except Exception:
        pass''',
            "言语行为分布渲染")

    # 5) ⑪ FMEA 可检测性：失败模式节里逐条标注
    s = rep(s, '''    else:
        out.append("- 所有行动都带回退路径。\\n")

    out.append("\\n### 五、不做什么\\n")''',
            '''    else:
        out.append("- 所有行动都带回退路径。\\n")
    # ★ [FMEA 可检测性] 不可检测的失败最危险 —— 它不会出现在任何读数里。
    #   本节原有「有没有回退」，缺「这个失败**能不能被发现**」。
    try:
        _marks = []
        for _v in (v1 or {}).values() if isinstance(v1, dict) else []:
            _marks += [str(x) for x in ((_v or {}).get("quality_flags") or [])]
            _marks += [str(x) for x in ((_v or {}).get("errors") or [])][:6]
        _marks += [str(x) for x in (flags or [])]
        _names = ["失败模式" + str(i + 1) for i in range(min(3, len(_nf)))]
        if _names:
            out.append("\\n> **FMEA 可检测性**（严重度×频度×**可检测性**）：\\n")
            for _nm in _names:
                out.append(f"> - {_nm}：{fmea_detectability(_nm, _marks)}\\n")
    except Exception:
        pass

    out.append("\\n### 五、不做什么\\n")''',
            "FMEA 可检测性渲染")

    _save(s)
    print("OK 第 3 段（第二批 7 项中的 ⑥ 项：截断两向/输入自检/言语行为/FMEA）")
    s2 = SRC.read_bytes().decode("utf-8")
    for _m in ("def input_red_flags(", "def illocution_of(",
               "def illocution_dist(", "def cut_two_way(",
               "def fmea_detectability(", "def diversity_budget("):
        assert _m in s2, _m
    print("复读校验通过")


if __name__ == "__main__":
    main()

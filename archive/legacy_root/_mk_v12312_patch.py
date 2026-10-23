# -*- coding: utf-8 -*-
"""v1.23.12 补丁：把「外部锚点」拆成**文本锚点 / 联网检索**两条通道分别写明。

五处改动（全部落在渲染层，不碰 prompt / LLM / 判定语义）：
  1. 新增两个纯函数 `_web_lane_stats` / `_anchor_lane_lines`（单一实现）。
  2. `render_manifestation` 的「这份产物没有显化的」段：改为调 `_anchor_lane_lines`。
  3. `_render_landing_decision` 加「七、外部锚点（两条通道分开记账）」。
  4. `_render_landing_boundary` 加同一节。
  5. `save_result`：头部插两条通道行；`if dec:` 里恢复锚点**明细**
     （对照 / 分级 / triage 降级 / 冲突 / 入池）+ 联网关时的留痕指路。

★ 写文件铁律：read_bytes → 断言锚点命中 == 1 → 转 LF → 替换 → 转回 CRLF
  → **write_bytes**（write_text 会产出 CRCRLF 且不报错）。写完自检 CRCRLF == 0。
★ 顺序：**先做替换、最后插入新函数**，且插入前**重新扫描**锚点 —— 前面的替换
  会让行号漂移（v1.23.12 首版就因此把新函数塞进了 `_render_landing_decision`
  的函数体，函数只剩 docstring 返回 None，而 `ast.parse` 照样通过）。
"""
import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE / "元DGTF-V1.23.12.py"

raw = MAIN.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n"), "主文件不是纯 CRLF"
assert raw.count(b"\r\r\n") == 0
src = raw.decode("utf-8")
lines = src.replace("\r\n", "\n").split("\n")
N0 = len(lines) - 1


def find_row(pred, what):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    assert len(hits) == 1, "%s：命中 %d 次 %r" % (what, len(hits), hits)
    return hits[0]


# ══════════════════════════════════════════════════════════
# 0 · 先定位「两个新函数」的插入点（插入放到最后做）
# ══════════════════════════════════════════════════════════
i_dl0 = find_row(lambda l: l == "def _render_landing_decision(res: dict) -> str:",
                 "decision 模板定义")
assert lines[i_dl0 - 1] == "" and lines[i_dl0 - 2] == "", \
    "decision 模板前不是两个空行：%r %r" % (lines[i_dl0 - 2], lines[i_dl0 - 1])
assert lines[i_dl0 - 3].startswith('            f"{_tail}{_flag}'), \
    "decision 模板前不是停因汇总的末行：%r" % (lines[i_dl0 - 3],)

NEW_FUNCS = '''def _web_lane_stats(res: dict) -> dict:
    """联网检索侧的可读读数（纯函数、零 LLM）—— 「外部锚点」两条通道之一。

    ★ 与 `external_anchor` 的分工：`external_anchor` 读的是运行前挂进来的
      **锚点文件**；本函数读的是 `web_search` 落进池里的**联网检索**结果
      （`web_results` / `web_errors`）。两者互相独立 —— 一个开、另一个
      可以是关的。真跑实测出现过「联网收了 6 条（W1–W6）、锚点文件一条
      没有」，而旧产物只写「**外部锚点**：无」，读者据此会以为本次没有
      任何外部校验。
    ★ `enabled` 三态：True 开 / False 关 / None 未记录（产物没写 `_runtime`）。
    """
    _rt = res.get("_runtime")
    _enabled = (_rt or {}).get("web_enabled") if isinstance(_rt, dict) else None
    _ok: List[dict] = []
    _errs: List[tuple] = []
    for _p in (res.get("pools") or {}).values():
        if not isinstance(_p, dict):
            continue
        for _it in (_p.get("web_results") or []):
            if isinstance(_it, dict):
                _ok.append(_it)
        for _e in (_p.get("web_errors") or []):
            if isinstance(_e, dict):
                _errs.append((str(_e.get("kind") or "?"),
                              str(_e.get("stage") or "?")))
    _tiers: Dict[str, int] = {}
    for _it in _ok:
        _t = _it.get("tier_effective", _it.get("tier"))
        _k = "?" if _t is None else str(_t)
        _tiers[_k] = _tiers.get(_k, 0) + 1
    return {
        "enabled": _enabled,
        "ok": len(_ok),
        "ids": [str(_it.get("id")) for _it in _ok if _it.get("id")],
        "stages": sorted({str(_it.get("stage")) for _it in _ok
                          if _it.get("stage")}),
        "tiers": _tiers,
        "errs": _errs,
    }


def _anchor_lane_lines(res: dict) -> List[str]:
    """把「外部锚点」拆成**两条通道**分别写明：文本锚点（文件）/ 联网检索。

    ★ 为什么必须分开写：真跑产物里联网明明收了 6 条（`pool.meta` 里的
      `[W-OK] …收 3 条`），产物却只写「**外部锚点**：无」—— 读者会据此
      认为本次没有任何外部校验。两套机制各自「没有」时也要各自写清。
    ★ **单一实现**：产物头部 / 显化说明 / 两套落地层模板共 4 处调用本函数。
      「同一条逻辑两条通道各写一份」是本项目复发率最高的问题，不再加例。
    ★ 通道行只写「这一路接没接上」；锚点的**明细**（对照 / 分级 /
      triage 降级 / 冲突 / 入池）仍由产物头部那几行承担 —— 两条通道是
      **多一条出口**，不是换掉那些读数。
    """
    out: List[str] = []
    _ea = res.get("external_anchor")
    if isinstance(_ea, dict):
        _l = ("**外部锚点 · 文本**（锚点文件 `external_anchor`）：已接入 "
              + str(_ea.get("anchors", 0)) + " 条")
        if _ea.get("source_file"):
            _l += ("（" + str(_ea.get("source_file"))
                   + "，检索于 " + str(_ea.get("retrieved_at", "?")) + "）")
        if _ea.get("error"):
            _l += "；⚠️ 接入失败（明细见下方「锚点异常」）"
        out.append(_l)
    else:
        out.append("**外部锚点 · 文本**（锚点文件 `external_anchor`）："
                   "无 —— 本次未挂外部事实文件；结论可信度只取决于池内"
                   "材料的一致性（设计边界，不是缺陷）")
    _w = _web_lane_stats(res)
    if _w["enabled"] is None:
        _l2 = ("**外部锚点 · 联网**（`web_search`）：未记录 —— "
               "本次产物没有写入联网生效状态（要接入：`--web on`）")
    elif not _w["enabled"]:
        _l2 = ("**外部锚点 · 联网**（`web_search`）：**关** —— "
               "本次未接入联网检索；事实类结论没有外部证据支撑"
               "（要接入：`--web on`）")
    else:
        _l2 = ("**外部锚点 · 联网**（`web_search`）：**开** —— 收 "
               + str(_w["ok"]) + " 条")
        if _w["ok"]:
            _ids = "、".join(_w["ids"][:6]) + ("…" if len(_w["ids"]) > 6 else "")
            _l2 += ("（" + (_ids + "；" if _ids else "")
                    + str(len(_w["stages"])) + " 个环节"
                    + ("；tier " + "/".join(
                        _k + "×" + str(_v) for _k, _v in _w["tiers"].items())
                       if _w["tiers"] else "")
                    + "）")
        _l2 += ("；失败 " + str(len(_w["errs"])) + " 条"
                + ("（" + "、".join("[W-" + _k.upper() + "] " + _s
                                   for _k, _s in _w["errs"][:3]) + "）"
                   if _w["errs"] else ""))
    out.append(_l2)
    return out
'''.split("\n")

# ══════════════════════════════════════════════════════════
# 1 · render_manifestation：旧的单通道块 → 两条通道
# ══════════════════════════════════════════════════════════
i_m = find_row(lambda l: l == '    _ea = res.get("external_anchor")',
               "manifestation 锚点块首行")
assert lines[i_m + 1] == "    if _ea:", \
    "manifestation 锚点块第 2 行不符：%r" % (lines[i_m + 1],)
assert lines[i_m + 2] == '        _n = _ea.get("summary") or {}', \
    "manifestation 锚点块第 3 行不符：%r" % (lines[i_m + 2],)
i_m_end = find_row(lambda l: l == "    for g in _gaps:", "manifestation 渲染 _gaps")
assert i_m > 0 and i_m_end - i_m < 25, "manifestation 锚点块跨度过大"
assert lines[i_m_end - 1] == \
    '                     "结论的可信度取决于池内材料的一致性）")', \
    "manifestation 锚点块末行不符：%r" % (lines[i_m_end - 1],)

NEW_MANIF = [
    "    # ★ 两条通道分别记账（文本锚点 / 联网检索）—— 单一实现见",
    "    #   `_anchor_lane_lines`。旧实现只写「外部锚点：无」，联网真跑了",
    "    #   读者也看不到。",
    "    for _al in _anchor_lane_lines(res):",
    "        _gaps.append(_al)",
]
lines[i_m:i_m_end] = NEW_MANIF

# ══════════════════════════════════════════════════════════
# 2 · decision 模板：加「七、外部锚点（两条通道分开记账）」
# ══════════════════════════════════════════════════════════
NEW_SEC = [
    "",
    '    out.append("\\n### 七、外部锚点（两条通道分开记账）\\n")',
    '    out.append("（`external_anchor` 是运行前挂进来的**锚点文件**；"',
    '               "`web_search` 是**联网检索**。两者互相独立 —— "',
    '               "一条没有时也各自写明，避免把「没接入」读成「没这一项」。）\\n")',
    "    for _al in _anchor_lane_lines(res):",
    '        out.append(f"- {_al}\\n")',
]
i_d = find_row(lambda l: l == '        out.append("（本节无内容：没有抽出任何行动）\\n")',
               "decision 模板末节")
assert lines[i_d + 1] == '    return "".join(out)', \
    "decision 模板结尾不符：%r" % (lines[i_d + 1],)
lines[i_d + 1:i_d + 1] = NEW_SEC

# ══════════════════════════════════════════════════════════
# 3 · boundary 模板：加同一节
# ══════════════════════════════════════════════════════════
i_b = find_row(
    lambda l: l == '                       f"未交代 {clo.get(\'unsettled\', 0)} 类\\n")',
    "boundary 模板末节")
assert lines[i_b + 1] == "", "boundary 模板末节后不是空行：%r" % (lines[i_b + 1],)
assert lines[i_b + 2] == '    return "".join(out)', \
    "boundary 模板结尾不符：%r" % (lines[i_b + 2],)
lines[i_b + 1:i_b + 1] = NEW_SEC

# ══════════════════════════════════════════════════════════
# 4 · save_result 头部：插两条通道行
# ══════════════════════════════════════════════════════════
i_h = find_row(lambda l: l == '            _tri = result.get("tri_state") or [0, 0]',
               "save_result 三态行")
NEW_HEAD = [
    "",
    "            # ★ 外部锚点两条通道（文本 / 联网）分别写明 —— 单一实现。",
    "            for _al in _anchor_lane_lines(result):",
    "                f.write(_al + \"\\n\\n\")",
]
lines[i_h:i_h] = NEW_HEAD

# ══════════════════════════════════════════════════════════
# 5 · save_result `if dec:`：锚点明细保留 + 联网关时的留痕指路
# ══════════════════════════════════════════════════════════
i_e = find_row(lambda l: l == '            _ea = result.get("external_anchor")',
               "save_result 锚点块首行")
assert lines[i_e - 1] == "        if dec:", \
    "save_result 锚点块前一行不是 if dec：%r" % (lines[i_e - 1],)
i_e_end = find_row(
    lambda l: l == '            f.write(f"**可判定性**: {dec.get(\'decidability\', \'?\')}\\n\\n")',
    "save_result 可判定性行")
assert i_e_end - i_e < 50, "save_result 锚点块跨度过大"

NEW_SAVE = '''            # ★ 锚点文件的**明细**（对照 / 分级 / triage 降级 / 冲突 / 入池）
            #   原样保留：两条通道是**多一条出口**，不是换掉这些读数。
            #   `[4.7]` 判据读「锚点分级 / triage 降级」两个字面串，
            #   `_p2_triage_from_md` 读 `**triage 降级**：N 条` 这个格式。
            _ea = result.get("external_anchor")
            if isinstance(_ea, dict) and _ea.get("error"):
                f.write(f"**锚点异常**：{_ea['error']}\\n\\n")
            elif isinstance(_ea, dict):
                _sm = _ea.get("summary") or {}
                f.write(f"**锚点对照**：结论 {_sm.get('claims', 0)} 条 —— "
                        f"印证 {_sm.get('supported', 0)} / "
                        f"冲突 {_sm.get('conflicted', 0)} / "
                        f"无对应 {_sm.get('unmatched', 0)}"
                        f"（用到锚点 {_sm.get('anchor_used', 0)}/"
                        f"{_ea.get('anchors', 0)}）\\n\\n")
                f.write(f"**锚点分级**：{_ea.get('as_evidence', 'off')}"
                        f"（tier_floor {_ea.get('tier_floor', '?')}）\\n\\n")
                f.write(f"**triage 降级**："
                        f"{_ea.get('triage_downgrades', 0)} 条\\n\\n")
                f.write(f"**冲突**：{_sm.get('conflicted', 0)} 条"
                        f"（gate 阻断 {len(_ea.get('blocked_conclusions') or [])} 条）\\n\\n")
                f.write(f"**锚点入池**：{_ea.get('pooled', 0)} 条"
                        f"（{'已获证据资格' if _ea.get('as_evidence')
                            else '仅记录，不作证据'}）\\n\\n")
            # ★ 两条通道已在头部写明；此处只在「联网关」时补一句留痕，
            #   并把「怎么接」指清楚（事实题才提示 —— 决策题不提示）。
            if not _web_lane_stats(result)["enabled"]:
                if not _has_decision_context(
                        str(result.get("question") or "")):
                    f.write(
                        "★ **本题是事实型询问，但本次未接入外部校验**"
                        "（两条通道都关：锚点文件无、联网检索关）"
                        " —— 这是一次**显式选择**，不是默认特权：\\n"
                        "  - 要接入：`--web on`（或配置 `web_search.*` 五档）；\\n"
                        "  - 接入后头部「**外部锚点 · 联网**」会写出收了几条"
                        "（W#）、跨几个环节、失败几条；\\n"
                        "  - 未接入时，史实类结论**没有外部证据支撑**，请自行核对。\\n\\n")'''.split("\n")
lines[i_e:i_e_end] = NEW_SAVE

# ══════════════════════════════════════════════════════════
# 6 · 最后插入两个新纯函数（★ 插入前重新扫描：索引会漂）
# ══════════════════════════════════════════════════════════
i_dl = find_row(lambda l: l == "def _render_landing_decision(res: dict) -> str:",
                "decision 模板定义（插入前重扫）")
assert lines[i_dl - 1] == "" and lines[i_dl - 2] == "", \
    "decision 模板前不是两个空行：%r %r" % (lines[i_dl - 2], lines[i_dl - 1])
assert lines[i_dl - 3].startswith('            f"{_tail}{_flag}'), \
    "decision 模板前不是停因汇总的末行：%r" % (lines[i_dl - 3],)
lines[i_dl - 2:i_dl - 2] = NEW_FUNCS

# ══════════════════════════════════════════════════════════
out = "\n".join(lines)
ast.parse(out)                      # 语法自检
data = out.replace("\n", "\r\n").encode("utf-8")
assert data.count(b"\r\r\n") == 0, "★ 产出 CRCRLF"
assert data.count(b"\r\n") == data.count(b"\n"), "★ 换行不纯"
MAIN.write_bytes(data)

txt = data.decode("utf-8")
N1 = txt.count("\n")
print("行数：%d → %d（%+d）" % (N0, N1, N1 - N0))
print("CRLF %d | CRCRLF %d" % (data.count(b"\r\n"), data.count(b"\r\r\n")))
for _k in ("def _web_lane_stats(res: dict) -> dict:",
           "def _anchor_lane_lines(res: dict) -> List[str]:",
           "### 七、外部锚点（两条通道分开记账）",
           "for _al in _anchor_lane_lines(",
           "**锚点分级**", "**triage 降级**"):
    print("  %-52s ×%d" % (_k, txt.count(_k)))
print("旧单通道块残留（应为 0）：",
      txt.count('f.write("**外部锚点**：无（本产物不含外部事实校验；'))

# ── 结构性自检：两个模板必须仍返回 str（防「函数体被并进上一个函数」）──
import importlib.util as _ilu
import sys as _sys
_spec = _ilu.spec_from_file_location("m_v12312_patchchk", MAIN)
_m = _ilu.module_from_spec(_spec)
_sys.modules["m_v12312_patchchk"] = _m
_spec.loader.exec_module(_m)
for _o in ("boundary", "decision", "auto"):
    _r = _m.render_landing({"orientation": _o,
                            "_config": {"actions": {"landing_decision": True}},
                            "views": {}, "decidability": {},
                            "question": "这份方案怎么落地"})
    assert isinstance(_r, str), "★ render_landing(%s) 返回 %r" % (_o, type(_r))
    assert "### 七、外部锚点（两条通道分开记账）" in _r, \
        "★ render_landing(%s) 缺第七节" % _o
print("结构自检：render_landing 三档都返回 str 且带第七节 ✓")

# -*- coding: utf-8 -*-
"""v1.23.8 补丁：渲染层守卫（空节 / 停止汇总 / suspensions 去重）+ 版本号。

三处改动全在**渲染层**，不碰 prompt、不碰 LLM 调用、不碰判定语义。
主文件必须保持纯 CRLF：read_bytes → 断言 CRLF==LF → 转 LF → 改 →
转回 CRLF → write_bytes。每个锚点断言命中恰好 1 处。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.8.py"

raw = SRC.read_bytes()
txt = raw.decode("utf-8")
assert txt.count("\r\n") == txt.count("\n"), "不是纯 CRLF"
assert txt.count("\r") == txt.count("\r\n"), "有游离 CR（\\r 不在 CRLF 里）"
text = txt.replace("\r\n", "\n")
assert "\r" not in text

lines = text.split("\n")
N0 = len(lines)


def find_row(pred, tag):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    assert len(hits) == 1, f"[{tag}] 整行锚点命中 {len(hits)} 行（要求 1）"
    return hits[0]


# ── 0) 版本号（两处）──────────────────────────────────────────
i = find_row(lambda l: l == "元 DGTF · v1.23.7", "docstring 标题")
lines[i] = "元 DGTF · v1.23.8"

i = find_row(lambda l: l == '__version__ = "1.23.7"', "__version__")
lines[i] = '__version__ = "1.23.8"'

# ── 1) 新增三个渲染层纯函数（插在 _render_landing_decision 之前）──
NEW_FUNCS = '''def _susp_key(target) -> str:
    """取一枚悬置条目的归并键：target 的首个分句（按「；」切）。

    ★ 真跑实测：同一类张力被登记成「X」与「X；元层决定不消解。」—— 全长
      不等 ⇒ 按全长去重完全无效；取首分句后两者相等。首分句短于 6 字时
      退回全长，避免短串误合并。
    """
    _t = str(target or "").strip()
    _head = _t.split("；")[0].split(";")[0].strip()
    return _head if len(_head) >= 6 else _t


def _dedup_suspensions_for_render(items) -> tuple:
    """渲染层归一：同 target 的悬置只渲染一条，返回 (保留列表, 合并条数)。

    ★ 池内已有重复检测，但「决定不消解」这一类没接同一个去重器。这里只做
      渲染层归一，并把合掉的条数打印出来 —— 去冗余、但留痕，不假装池里
      没有重复。
    """
    _seen = set()
    _kept = []
    _dup = 0
    for _it in (items or []):
        _k = _susp_key(_it.get("target") if isinstance(_it, dict) else _it)
        if _k and _k in _seen:
            _dup += 1
            continue
        if _k:
            _seen.add(_k)
        _kept.append(_it)
    return _kept, _dup


_STOP_CUT_MARKS = ("体力耗尽", "被截断")


def _stop_kind_summary(views) -> str:
    """把各层 stop_reason 归纳成一行「自然停 n 层 / 被截断 m 层」。

    ★ 为什么单列到头部：真跑实测四层全部「体力耗尽（被截断不是自然停止）」
      时，读者从头部完全看不出来 —— 「一次停止判据都没触发」与「四层都
      自然收敛」在头部长得一样。没有任何一层留下停因时返回空串（不渲染）。
    """
    if not isinstance(views, dict) or not views:
        return ""
    _nat = _cut = _none = 0
    for _v in views.values():
        if isinstance(_v, dict):
            _sr = str(_v.get("stop_reason") or "")
        else:
            _sr = str(getattr(_v, "stop_reason", "") or "")
        if not _sr:
            _none += 1
        elif any(_m in _sr for _m in _STOP_CUT_MARKS):
            _cut += 1
        else:
            _nat += 1
    if _nat + _cut <= 0:
        return ""
    _tail = f"，无停因记录 {_none} 层" if _none else ""
    _flag = " ⚠️ 无一层自然收敛" if (_cut and not _nat) else ""
    return (f"**停止**：自然 {_nat} 层 / 被截断（体力耗尽）{_cut} 层"
            f"{_tail}{_flag}\\n\\n")


'''

i = find_row(lambda l: l == "def _render_landing_decision(res: dict) -> str:",
             "新函数插入点")
lines[i:i] = NEW_FUNCS.split("\n")[:-1]

# ── 2) 「三、所需数据清单」：空节守卫 ─────────────────────────
i = find_row(
    lambda l: l == '    out.append("\\n### 三、所需数据清单\\n")',
    "三节标题行")
assert lines[i + 4].strip() == 'out.append("（以下行动缺时限，通常是因为缺一次现场量测）\\n")', \
    f"三节块第 5 行不符：{lines[i + 4]!r}"
assert lines[i + 6].strip() == 'out.append(f"- {s[:80]}\\n")', \
    f"三节块第 7 行不符：{lines[i + 6]!r}"
NEW3 = [
    '    _dd = [a.get("object", "") for a in actions',
    '           if a.get("deadline_hint") == "（未指定）"]',
    '    out.append("\\n### 三、所需数据清单\\n")',
    "    if _dd:",
    '        out.append("（以下行动缺时限，通常是因为缺一次现场量测）\\n")',
    "        for s in _dd[:3]:",
    '            out.append(f"- {s[:80]}\\n")',
    "    else:",
    "        # 空节守卫：有标题、没内容，读者会读成「渲染失败」。",
    "        out.append(\"（本节无内容：没有「缺时限」的行动，\"",
    "                   \"因此没有待补的现场量测项）\\n\")",
]
lines[i:i + 7] = NEW3

# ── 3) 「六、如果只能做一件事」：空节守卫 ─────────────────────
i = find_row(
    lambda l: l == '    out.append("\\n### 六、如果只能做一件事\\n")',
    "六节标题行")
assert lines[i + 1].strip() == "if actions:", f"六节块第 2 行不符：{lines[i + 1]!r}"
assert lines[i + 3].strip() == \
    "out.append(f\"- {a1.get('verb', '')} {a1.get('object', '')}\\n\")", \
    f"六节块第 4 行不符：{lines[i + 3]!r}"
NEW6 = [
    '    out.append("\\n### 六、如果只能做一件事\\n")',
    "    if actions:",
    "        a1 = actions[0]",
    "        out.append(f\"- {a1.get('verb', '')} {a1.get('object', '')}\\n\")",
    "    else:",
    "        out.append(\"（本节无内容：没有抽出任何行动）\\n\")",
]
lines[i:i + 4] = NEW6

# ── 4) save_result：头部「停止」汇总（接在 **调度** 之后）──────
i = find_row(
    lambda l: l == "            f.write(f\"**调度**：{seq or '（空）'}\\n\\n\")",
    "调度行")
lines[i + 1:i + 1] = [
    "            _stop_line = _stop_kind_summary(_views0)",
    "            if _stop_line:",
    "                f.write(_stop_line)",
]

# ── 5) save_result：suspensions 渲染去重 ──────────────────────
i = find_row(lambda l: l == '                for s in v["suspensions"]:',
             "suspensions 遍历行")
assert 'f.write(f"- {s.get(\'target\',\'\')}：")' in lines[i + 1] or \
    'target' in lines[i + 1], f"suspensions 渲染行不符：{lines[i + 1]!r}"
assert lines[i + 3].strip().startswith('f"（{s.get('), \
    f"suspensions 渲染第 4 行不符：{lines[i + 3]!r}"
NEW_S = [
    "                _susp_kept, _susp_dup = _dedup_suspensions_for_render(",
    '                    v["suspensions"])',
    "                for s in _susp_kept:",
    '                    f.write(f"- {s.get(\'target\',\'\')}："',
    "                            f\"{s.get('reason') or '直觉，无理由'}\"",
    "                            f\"（{s.get('reason_type','')}）\\n\")",
    "                if _susp_dup:",
    "                    f.write(f\"  （另有 {_susp_dup} 条同 target 重复\"",
    "                            f\"已合并；原始 {len(v['suspensions'])} 条）\\n\")",
]
lines[i:i + 4] = NEW_S

out = "\n".join(lines)
# 收尾：CRLF 往返 + 字节写出
out_b = out.replace("\n", "\r\n").encode("utf-8")
assert out_b.count(b"\r\n") == out_b.count(b"\n"), "写出前 CRLF 校验失败"
assert out_b.count(b"\r\r\n") == 0, "出现 CRCRLF"
SRC.write_bytes(out_b)

# 自检：回读
chk = SRC.read_bytes()
assert chk.count(b"\r\r\n") == 0
assert chk.count(b"\r\n") == chk.count(b"\n")
import ast
ast.parse(chk.decode("utf-8"))
print(f"OK 行数 {N0} → {chk.decode('utf-8').count(chr(10)) + 1}")
print("新符号：",
      [n for n in ("_susp_key", "_dedup_suspensions_for_render",
                   "_stop_kind_summary")
       if f"def {n}(" in chk.decode("utf-8")])

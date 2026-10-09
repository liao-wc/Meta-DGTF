# -*- coding: utf-8 -*-
"""v1.23.9 补丁：取向分流守卫（auto + 无决策语境 → boundary 模板）+ 版本号。

改动全在**渲染层分流壳** `render_landing`：不碰 prompt、不碰 LLM 调用、
不碰判定语义。主文件必须保持纯 CRLF。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.9.py"

raw = SRC.read_bytes()
txt = raw.decode("utf-8")
assert txt.count("\r\n") == txt.count("\n"), "不是纯 CRLF"
assert txt.count("\r") == txt.count("\r\n"), "有游离 CR"
text = txt.replace("\r\n", "\n")
lines = text.split("\n")
N0 = len(lines)


def find_row(pred, tag):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    assert len(hits) == 1, f"[{tag}] 整行锚点命中 {len(hits)} 行（要求 1）"
    return hits[0]


# ── 0) 版本号（两处）───────────────────────────────────────────
i = find_row(lambda l: l == "元 DGTF · v1.23.8", "docstring 标题")
lines[i] = "元 DGTF · v1.23.9"
i = find_row(lambda l: l == '__version__ = "1.23.8"', "__version__")
lines[i] = '__version__ = "1.23.9"'

# ── 1) 新增决策语境词表 + 纯函数（插在 render_landing 之前）─────
NEW = '''# ★ v1.23.9：decision 模板的适用前提是「题面里有决策语境」。
#   词表只增不减 —— 加词只会让更多题走 decision 模板（即回到 v1.23.8 及
#   以前的行为），不会静默把本来走 decision 的题踢出去。
_DECISION_CUES = (
    "该不该", "要不要", "是否", "怎么办", "怎么选", "怎么建", "怎么改",
    "如何", "方案", "建议", "选哪个", "取舍", "优先", "值不值", "利弊",
    "可行", "落地", "规划", "部署", "决策", "权衡", "风险", "预算",
    "排期", "步骤", "流程", "设计",
)


def _has_decision_context(question: str) -> bool:
    """题面是否带决策语境（决定 decision 模板适不适用）。

    ★ 判据落在**行为**上：命中任一决策语汇 → True（走 decision 模板）。
      只判「有 / 没有」，不判程度。
    ★ 负对照：单点事实询问（「…是什么时候」「…是哪一年」「…有多少」）
      不该命中 —— 它们套 decision 模板会替提问者编出一整套不存在的
      执行流程（行动清单 / 负责人 / 时限 / 验收）。
    ★ 题面取不到（空 / 缺 question 键）时返回 False：宁可走边界模板，
      也不在不知道题面时套决策模板。
    """
    _q = str(question or "")
    if not _q.strip():
        return False
    return any(_c in _q for _c in _DECISION_CUES)


'''
i = find_row(lambda l: l == "def render_landing(res: dict) -> str:", "render_landing")
lines[i:i] = NEW.split("\n")[:-1]

# ── 2) 分流壳：auto 也要看题面 ─────────────────────────────────
i = find_row(lambda l: l == "def render_landing(res: dict) -> str:", "分流壳")
assert 'decision → 行动闭环模板。壳里不写任何渲染逻辑。"""' in lines[i + 2], \
    f"分流壳 docstring 尾行不符：{lines[i + 2]!r}"
assert lines[i + 3].strip() == 'cfg = res.get("_config") or {}', \
    f"分流壳第 4 行不符：{lines[i + 3]!r}"
assert lines[i + 7].strip() == "return _render_landing_decision(res)", \
    f"分流壳末行不符：{lines[i + 7]!r}"
NEW6 = [
    'def render_landing(res: dict) -> str:',
    '    """ 落地层分流壳：boundary / 关掉开关 / **无决策语境** → 老五块模板；',
    "    decision → 行动闭环模板。壳里不写任何渲染逻辑。",
    "",
    "    ★ v1.23.9 起 `auto` 还要看题面：无决策语境的单点事实询问",
    "      （「…是什么时候」「…是哪一年」）套 decision 模板，会替提问者",
    "      编出一整套不存在的执行流程（行动清单 / 负责人 / 时限 / 验收）。",
    "      这类题面走 boundary 模板。",
    "      **显式传 `--orientation decision` 仍走 decision**（不覆盖用户的",
    "      显式选择）；`boundary` 与「关掉开关」两种短路都保持原样。",
    '    """',
    '    cfg = res.get("_config") or {}',
    '    orientation = str(res.get("orientation") or "auto").strip().lower()',
    '    if orientation == "boundary" or not _action_on(cfg, "landing_decision"):',
    "        return _render_landing_boundary(res)",
    '    if orientation == "auto" and not _has_decision_context(',
    '            str(res.get("question") or "")):',
    "        return _render_landing_boundary(res)",
    "    return _render_landing_decision(res)",
]
lines[i:i + 8] = NEW6

out = "\n".join(lines)
out_b = out.replace("\n", "\r\n").encode("utf-8")
assert out_b.count(b"\r\n") == out_b.count(b"\n"), "写出前 CRLF 校验失败"
assert out_b.count(b"\r\r\n") == 0, "出现 CRCRLF"
SRC.write_bytes(out_b)

chk = SRC.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\r\n") == chk.count(b"\n")
import ast  # noqa: E402
ast.parse(chk.decode("utf-8"))
print(f"OK 行数 {N0} → {chk.decode('utf-8').count(chr(10)) + 1}")
print("新符号存在：", "def _has_decision_context(" in chk.decode("utf-8"),
      "| 词表：", "_DECISION_CUES = (" in chk.decode("utf-8"))

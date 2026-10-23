#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v122 阶段1] 打补丁：Phase.objective 分层 / coverage 只对研究层 /
_classify_unsaid / 头部四行分层目标 / 版本号。

铁律：read_bytes → 断言 CRLF → 转 LF → 逐条断言出现次数 → 替换
      → 转回 CRLF → write_bytes。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "元DGTF-V1.22.0-rc1.py"

NEWFUNCS = '''
# ============================================================
# [v122 阶段1] 目标函数分层 · 未生分类
# ============================================================


def _classify_unsaid(block) -> str:
    """[v122 阶段1 G1.5] 「此处未生」的分类：`real`（真未生）/ `lazy`（偷懒）。

    红线上写着「悬置不打分、未生合法」，但**合法 ≠ 一律可信**：一条探针
    在没看过「本层未触及项」清单的情况下说「此处未生」，与它认真核过清单
    之后说未生，是两件事。判据取最便宜的那一个 —— 它有没有用 `covers`
    声明碰过清单里的东西：

      · 有非空 covers → `real`（认真看过才说未生）；
      · 无 covers / 空 covers / 非 mapping → `lazy`（没声称碰过任何东西）。

    ★ 负对照（写进冒烟）：`{"covers": []}` 必须判 `lazy`，不是 `real` ——
      否则「空数组」会被 fuzz 成通过，这个判据就永远亮了。
    """
    if not isinstance(block, dict):
        return "lazy"
    cov = block.get("covers")
    if isinstance(cov, str):
        return "real" if cov.strip() else "lazy"
    if isinstance(cov, (list, tuple, set)):
        return "real" if len(cov) > 0 else "lazy"
    return "lazy"


_LAYER_CN = {"0": "修行层", "1": "研究层", "both": "对撞层", "all": "元层"}

_OBJECTIVE_CN = {
    "manifest": "把处境显形 —— 不求答案，因此不计覆盖率",
    "truth": "求可判定的真 —— 覆盖率只对这一层算",
    "collision": "求不可通约处 —— 对撞不改判定，只暴露张力",
    "closure": "求整体闭环 —— 不评价修行层，只交代留没留账",
}


def _layer_objective_lines() -> List[str]:
    """[v122 阶段1 G1.6] 四层目标函数分层，一行一层，进产物头部。

    为什么要写进产物：以前「覆盖率」只有一个数，读者看不出**它属于哪一层**。
    修行层本来就不求答案 —— 拿它的覆盖率去衡量它，等于用错的尺。四行写清
    「这一层在求什么」，覆盖率的适用面就自明了。
    """
    out: List[str] = []
    for e in ("0", "1", "both", "all"):
        o = getattr(PHASES.get(e), "objective", "?")
        out.append(f"- **{_LAYER_CN[e]}**：objective=`{o}` —— "
                   f"{_OBJECTIVE_CN.get(o, '')}")
    return out

'''

REPS = [
    # P1-a dataclass 加字段
    ('    view_focus: str\n    target_hardness: str = "soft"\n',
     '    view_focus: str\n    target_hardness: str = "soft"\n'
     '    # [v122 阶段1 G1.3] 目标函数分层：本层求的是"显形 / 真 / 张力 / 闭环"\n'
     '    objective: str = "truth"\n', 1),
    # P1-b 修行层
    ('        "四、与问题相处的姿态（一段话）"\n    ),\n)',
     '        "四、与问题相处的姿态（一段话）"\n    ),\n'
     '    objective="manifest",\n)', 1),
    # P1-c 研究层
    ('    target_hardness="hard",\n)',
     '    target_hardness="hard",\n    objective="truth",\n)', 1),
    # P1-d 对撞层
    ('    target_hardness="mixed",\n)',
     '    target_hardness="mixed",\n    objective="collision",\n)', 1),
    # P1-e 元层
    ('        "从整体·局部对撞里长出的新东西 / 一个新的姿态（与「完整」相处的方式）。"'
     '\n    ),\n)',
     '        "从整体·局部对撞里长出的新东西 / 一个新的姿态（与「完整」相处的方式）。"'
     '\n    ),\n    objective="closure",\n)', 1),
    # P1-f coverage_parts 签名
    ('def coverage_parts(pool, cfg: Optional[dict] = None):',
     'def coverage_parts(pool, cfg: Optional[dict] = None,\n'
     '                   entry: Optional[str] = None):', 1),
    # P1-g coverage_parts 守卫
    ('    调用点传真配置，两件事都做到。\n    """\n    _all = list(pool.sub_questions)',
     '    调用点传真配置，两件事都做到。\n    """\n'
     '    # [v122 阶段1 G1.4] 覆盖率只对**研究层**有意义：修行层求显形不求答案、\n'
     '    #   对撞层只暴露张力不改判定、元层求闭环。非研究层一律返回 None，\n'
     '    #   不再拿"没东西可答"当成"覆盖率低"。\n'
     '    if entry is not None and entry != "1":\n'
     '        return 0, 0, None\n'
     '    _all = list(pool.sub_questions)', 1),
    # P1-h coverage_of 签名
    ('def coverage_of(pool, cfg: dict) -> Optional[float]:',
     'def coverage_of(pool, cfg: Optional[dict] = None,\n'
     '                entry: Optional[str] = None) -> Optional[float]:', 1),
    # P1-i coverage_of 体内传 entry
    ('    _, _, cov = coverage_parts(pool, cfg)\n    return cov',
     '    _, _, cov = coverage_parts(pool, cfg, entry)\n    return cov', 1),
    # P1-j 新函数插在「保存结果」banner 之前
    ('# ============================================================\n'
     '# 保存结果\n'
     '# ============================================================\n',
     NEWFUNCS + '\n# ============================================================\n'
     '# 保存结果\n'
     '# ============================================================\n', 1),
    # P1-k save_result 头部插入四行分层目标
    ('        f.write(f"**时间**: {datetime.now().isoformat()}\\n\\n")\n',
     '        f.write(f"**时间**: {datetime.now().isoformat()}\\n\\n")\n'
     '        # [v122 阶段1 G1.6] 分层目标：四层各一行，进头部\n'
     '        f.write("**分层目标**：\\n")\n'
     '        for _ol in _layer_objective_lines():\n'
     '            f.write(f"{_ol}\\n")\n'
     '        f.write("\\n")\n', 1),
]

COV_CALL = re.compile(
    r'(?m)^( +)(cov(?:_before)? = coverage_of\(self\.pools\[entry\], sp)\)\s*$')


def main():
    b = TARGET.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "原文不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    S = {"s": s}

    for old, new, cnt in REPS:
        n = S["s"].count(old)
        if n != cnt:
            print(f"✗ 断言失败：出现 {n} 次（期望 {cnt}）：{old[:70]!r}")
            return 1
        S["s"] = S["s"].replace(old, new)

    # P1-l coverage 调用点补 entry=entry（4 处，全在 entry=="1" 分支内）
    n_call = len(COV_CALL.findall(S["s"]))
    if n_call != 4:
        print(f"✗ coverage 调用点数 = {n_call}（期望 4）")
        return 1
    S["s"] = COV_CALL.sub(r'\1\2, entry=entry)', S["s"])

    # P1-m 版本号（两处）
    for old, new in (
        ("元 DGTF · v1.21.77", "元 DGTF · v1.22.0-rc1"),
        ('__version__ = "1.21.77"', '__version__ = "1.22.0-rc1"'),
    ):
        if S["s"].count(old) != 1:
            print(f"✗ 版本锚点 {old!r} 出现 {S['s'].count(old)} 次")
            return 1
        S["s"] = S["s"].replace(old, new)

    out = S["s"].replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n")
    assert out.count("\r") == out.count("\r\n")
    TARGET.write_bytes(out.encode("utf-8"))
    print("✓ 阶段1 补丁完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())

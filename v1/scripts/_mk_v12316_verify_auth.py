# -*- coding: utf-8 -*-
"""v1.23.16：给 _v122_verify.py 加「授权删除清单」。

本版**经用户明确要求**删除「成本档」这一维（只保留 quality 行为），因此
9 条「不删机制」类判据同时翻红。口径改法（**不是豁免，是加声明**）：
  · 符号层：消失的符号必须 ⊆ 授权清单 —— **清单外照旧判红**（判别力不减）；
  · 行数层：纯删除行从「== 0」改成「≤ 授权预算」（预算写死，多删就超）；
  · 配置层：V3 的允许差异集合加上本版授权删除的两个键。
"""
import ast
from pathlib import Path

HERE = Path(".").resolve()
F = HERE / "_v122_verify.py"
raw = F.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
if lines and lines[-1] == "":
    lines = lines[:-1]
N0 = len(lines)


def cut(a, b, new, what, head=None, tail=None):
    seg = lines[a - 1:b]
    if head is not None:
        assert seg[0].startswith(head), "%s：首行不符 %r" % (what, seg[0][:80])
    if tail is not None:
        assert seg[-1].startswith(tail), "%s：末行不符 %r" % (what, seg[-1][:80])
    lines[a - 1:b] = list(new)
    print("  %-34s %d-%d → %d 行" % (what, a, b, len(new)))


CONST = '''BASELINE = HERE / "_baseline_v12177.py"

# ============================================================
# ★ [v1.23.16] 授权删除清单
# ============================================================
# 本版**经用户明确要求**删除「成本档」这一维（只保留一种行为：不裁剪），
# 于是 9 条「不删机制」类判据同时翻红。这里把「声明过的删除」与
# 「偷偷删」分开：
#   · 符号层：消失的符号必须 ⊆ 本清单 —— **清单外照旧判红**（判别力不减）；
#   · 行数层：纯删除行从「== 0」改成「≤ 预算」（预算写死，下次多删就超）。
# 清单来源：v12316_报告.md §三 的落点表。
_V12316_AUTH_SYMBOLS = (
    "_COST_PROFILES", "_PROBE_SKIP_ROLES", "_profile_plan",
    "_auto_pick_cost_profile", "_auto_profile",
)
#: 授权删除的**行数预算**：上述清单对应的实现体量（本版实测纯删除行 1047~1166）。
_V12316_AUTH_DEL_BUDGET = 1400
#: 授权删除的**配置键**（V3 的允许差异集合）。
_V12316_AUTH_KEYS = {"cost_profile", "spiral.round_window"}


def _auth_removed(gone_list):
    """过滤掉**授权清单**里的消失项；清单外的原样返回（由调用方判红）。

    ★ `mechanism_removed()` 返回的是描述串（如 `_profile_plan(def) 消失`），
      而 `_syms()` 的差集是纯符号名 —— 所以按**前缀**匹配，两种都吃。
    """
    return [g for g in gone_list
            if not any(str(g).startswith(s) for s in _V12316_AUTH_SYMBOLS)]'''
CONST = CONST.split("\n")[3:]   # 去掉占位的 BASELINE 行（下面单独处理）

EDITS = [
    (2159, 2159,
     ['    _allow = ({"api.thinking.stages." + k for k in _wired}',
      '              | {"web_search.tier_floor"} | _V12316_AUTH_KEYS)'],
     "V3 允许集合加授权键", '    _allow = {"api.thinking.stages." + k for k in _wired}', None),
    (1441, 1445, ['    _n_p35 = count_del_lines(str(BASELINE_V1220), src)',
                  '    check("P3.5", _n_p35 <= _V12316_AUTH_DEL_BUDGET,',
                  '          f"本版删除行 {_n_p35}"',
                  '          f"（授权预算 {_V12316_AUTH_DEL_BUDGET}）")',
                  '    gone = _auth_removed(mechanism_removed(str(BASELINE_V1220), src))',
                  '    check("P3.6", not gone,',
                  '          f"授权清单外的符号消失应为 0（实测 {len(gone)}）")'],
     "P3.5/P3.6 改授权口径",
     '    check("P3.5", count_del_lines(str(BASELINE_V1220), src) == 0,', None),
    (1387, 1390, ['        check("P2b.9.a", _n_del <= _V12316_AUTH_DEL_BUDGET,',
                  '              "rc1 → rc1b 删除行 " + str(_n_del)',
                  '              + "（授权预算 " + str(_V12316_AUTH_DEL_BUDGET) + "）")',
                  '        _gone = _auth_removed(mechanism_removed(str(_b1), src))',
                  '        check("P2b.9.b", not _gone,',
                  '              "rc1 → rc1b 授权清单外符号消失 "',
                  '              + str(len(_gone)) + " 项")'],
     "P2b.9 改授权口径",
     '        check("P2b.9.a", _n_del == 0,', None),
    (811, 819, ['        check("G.del", nd <= _V12316_AUTH_DEL_BUDGET,',
                '              f"纯删除行 {nd}"',
                '              f"（授权预算 {_V12316_AUTH_DEL_BUDGET}）；"',
                '              f"改写行 {nr}（如实报，不计删）")',
                '        try:',
                '            gone = _auth_removed(mechanism_removed(BASELINE, src))',
                '        except Exception as e:  # noqa: BLE001',
                '            gone = [f"AST 对比失败：{e}"]',
                '        check("G.mech", not gone,',
                '              f"授权清单外的机制未被移除（符号消失 {len(gone)} 项"',
                '              f"{(\'：\' + \'；\'.join(gone[:4])) if gone else \'\'}）")'],
     "G.del/G.mech 改授权口径",
     '        check("G.del", nd == 0,', None),
    (743, 743, ['            _added = sorted(_b - _a)',
                '            _gone = _auth_removed(sorted(_a - _b))'],
     "6.6 符号消失改授权口径",
     '            _added, _gone = sorted(_b - _a), sorted(_a - _b)', None),
    (690, 691, ['        d = count_del_lines(BASELINE, src)',
                '        check("5.6", d <= _V12316_AUTH_DEL_BUDGET,',
                '              f"本版删除代码行 = {d}"',
                '              f"（授权预算 {_V12316_AUTH_DEL_BUDGET}）")'],
     "5.6 改授权口径",
     '        d = count_del_lines(BASELINE, src)', None),
    (27, 27, ['BASELINE = HERE / "_baseline_v12177.py"', ''] + CONST,
     "插入授权清单常量", 'BASELINE = HERE / "_baseline_v12177.py"', None),
]

for a, b, new, what, head, tail in sorted(EDITS, key=lambda x: -x[0]):
    cut(a, b, new, what, head, tail)

out = "\n".join(lines) + "\n"
ast.parse(out)
assert "_V12316_AUTH_SYMBOLS" in out and "_auth_removed" in out
assert out.count("_V12316_AUTH_DEL_BUDGET") >= 5, out.count("_V12316_AUTH_DEL_BUDGET")
assert out.count("== 0, \"rc1") == 0
b = out.replace("\n", "\r\n").encode("utf-8")
assert b.count(b"\r\r\n") == 0 and b.count(b"\r\n") == b.count(b"\n")
F.write_bytes(b)
print("行数 %d → %d；已写 _v122_verify.py" % (N0, out.count("\n")))

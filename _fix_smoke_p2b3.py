# -*- coding: utf-8 -*-
"""[v1.23.2] 修生成器里 STALE_P2B 的**定义**（上一版用字符串拼元组，拼出嵌套元组）。

正解：用 `NL.join([...])` 拼两个整块字符串，`STALE_P2B` 就是「一对 (旧, 新)」，
运行循环写成 `for _o, _n in STALE_P2B:`。
"""
import ast
from pathlib import Path

P = Path("_mk_v1230_smoke_checks.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")
NL = chr(10)

OLD_LINES = [
    '        # 7 crosscheck：两条路都在 + tier 门仍在 + 旧单路径已撤',
    '        _k0 = src.find("def _anchor_crosscheck")',
    '        _k1 = src.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1',
    '        _xc = src[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else src[_k0:]',
    '        assert "_hit_by_answers(str(" in _xc, "crosscheck 未接 answers 路径"',
    '        assert "_hit_by_claim(str(" in _xc, "crosscheck 未接 claim 路径"',
    '        assert \'x.get("answers")\' in _xc, "crosscheck 未读 answers 字段"',
    '        assert \'if int(x.get("tier", 3) or 3) <= _floor_c\' in _xc, "tier 门丢了"',
]
NEW_LINES = [
    '        # 7 [v1.23.2] crosscheck 路径：两条路都在 + tier 门仍在 + 旧单路径已撤',
    '        #   ★ 组装逻辑已抽成纯函数 `_triage_suggestions` ⇒ 区域 = 两处之和，',
    '        #     并**钉住调用关系**（否则「搬走了」与「删掉了」看起来一样）。',
    '        _k0 = src.find("def _anchor_crosscheck")',
    '        _k1 = src.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1',
    '        _xc0 = src[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else src[_k0:]',
    '        _t0 = src.find("def _triage_suggestions")',
    '        _t1 = src.find(NL + "def ", _t0 + 10) if _t0 >= 0 else -1',
    '        _ts = src[_t0:_t1] if _t0 >= 0 and _t1 > _t0 else ""',
    '        _xc = _xc0 + NL + _ts',
    '        assert "_triage_suggestions(" in _xc0, \\',
    '            "crosscheck 未调 _triage_suggestions（组装逻辑搬走后没接上）"',
    '        assert "_hit_by_answers(str(" in _xc, "crosscheck 未接 answers 路径"',
    '        assert "_hit_by_claim(str(" in _xc, "crosscheck 未接 claim 路径"',
    '        assert \'x.get("answers")\' in _xc, "crosscheck 未读 answers 字段"',
    '        assert \'int(x.get("tier", 3) or 3) <= _floor\' in _xc, "tier 门丢了"',
]

BLOCK = (
    "# ---- [v1.23.2] 过期区域判据同步：`check_v1221_p2b` 第 7 步（triage 组装逻辑"
    + NL + "#      已抽成 `_triage_suggestions` ⇒ 区域要扩成两处之和 + 钉调用关系）。"
    + NL + "#      ★ 这段文本在 **smoke 正文**里，必须像 STALE_HOOK 那样对 `src`"
    + NL + "#        做**运行时**替换（对生成器文件本身替换 = 命中 0，已踩过）。"
    + NL + "_P2B_OLD = " + repr(NL.join(OLD_LINES))
    + NL + "_P2B_NEW = " + repr(NL.join(NEW_LINES))
    + NL + "STALE_P2B = ((_P2B_OLD, _P2B_NEW),)"
    + NL + NL
)

i0 = s.index("STALE_P2B = (")
i1 = s.index("\nGUARD_RE = re.compile(", i0) + 1
s = s[:i0] + BLOCK + s[i1:]

# 运行循环改成 STALE_P2B 已经是一对
O = ("# --- 过期区域判据同步（check_v1221_p2b 第 7 步）---"
     + NL + "for _o, _n in (STALE_P2B,):")
N = ("# --- 过期区域判据同步（check_v1221_p2b 第 7 步）---"
     + NL + "for _o, _n in STALE_P2B:")
assert s.count(O) == 1, "循环锚点命中 %d 次" % s.count(O)
s = s.replace(O, N)

ast.parse(s)
P.write_bytes(s.encode("utf-8"))
print("STALE_P2B 定义与运行循环已修好")

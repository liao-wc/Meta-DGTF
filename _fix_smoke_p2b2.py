# -*- coding: utf-8 -*-
"""[v1.23.2] 生成器加 STALE_P2B：**运行时**替换 smoke 正文里 `check_v1221_p2b`
的第 7 步区域判据（triage 组装逻辑已抽成 `_triage_suggestions`）。

★ 上一版我把替换写成了「对生成器文件本身做 replace」—— 可那段文本在
  **smoke 正文**（`_bak_smoke_test.pre_v123`）里，生成器里根本没有 ⇒ 命中 0。
  正解与 `STALE_HOOK` 同款：在生成流程里对 `src` 做替换。
"""
import ast
from pathlib import Path

P = Path("_mk_v1230_smoke_checks.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

if "STALE_P2B" in s:
    print("已有 STALE_P2B，跳过")
    raise SystemExit(0)

NL = chr(10)
OLD = (
    '        # 7 crosscheck：两条路都在 + tier 门仍在 + 旧单路径已撤',
    '        _k0 = src.find("def _anchor_crosscheck")',
    '        _k1 = src.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1',
    '        _xc = src[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else src[_k0:]',
    '        assert "_hit_by_answers(str(" in _xc, "crosscheck 未接 answers 路径"',
    '        assert "_hit_by_claim(str(" in _xc, "crosscheck 未接 claim 路径"',
    '        assert \'x.get("answers")\' in _xc, "crosscheck 未读 answers 字段"',
    '        assert \'if int(x.get("tier", 3) or 3) <= _floor_c\' in _xc, "tier 门丢了"',
)
NEW = (
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
)

BLOCK = (
    "# ---- [v1.23.2] 过期区域判据同步：`check_v1221_p2b` 第 7 步（triage 组装逻辑"
    + NL + "#      已抽成 `_triage_suggestions` ⇒ 区域要扩成两处之和 + 钉调用关系）。"
    + NL + "#      ★ 这段文本在 **smoke 正文**里，所以必须像 STALE_HOOK 那样"
    + NL + "#        对 `src` 做**运行时**替换（上一版对生成器文件本身替换 ⇒ 命中 0）。"
    + NL + "STALE_P2B = ("
    + NL + "    " + ("(" + NL + "     ".join(
        [""] + ["".join(repr(x) + "," + NL + "     ") for x in OLD])).rstrip() + "),"
    + NL + "    " + ("(" + NL + "     ".join(
        [""] + ["".join(repr(x) + "," + NL + "     ") for x in NEW])).rstrip() + "),"
    + NL + ")" + NL
)

ANCH = "GUARD_RE = re.compile("
assert s.count(ANCH) == 1, "插入锚点命中 %d 次" % s.count(ANCH)
s = s.replace(ANCH, BLOCK + NL + ANCH)

RUN = (
    "# --- 过期区域判据同步（check_v1221_p2b 第 7 步）---"
    + NL + "for _o, _n in (STALE_P2B,):"
    + NL + "    if _o in src:"
    + NL + '        assert src.count(_o) == 1, "过期区域判据出现 %d 次" % src.count(_o)'
    + NL + "        src = src.replace(_o, _n)"
    + NL + '        print("  已同步过期区域判据（check_v1221_p2b 第 7 步）")'
    + NL + NL
)
ANCH2 = "# --- 过期配置登记同步 ---"
assert s.count(ANCH2) == 1, "运行锚点命中 %d 次" % s.count(ANCH2)
s = s.replace(ANCH2, RUN + ANCH2)

ast.parse(s)
P.write_bytes(s.encode("utf-8"))
print("生成器已加 STALE_P2B（运行时替换）")

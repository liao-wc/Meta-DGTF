# -*- coding: utf-8 -*-
"""[v1.23.2] 在冒烟生成器里加 STALE_P2B：把 `check_v1221_p2b` 的第 7 步区域判据
同步到新语义（triage 组装逻辑已抽成 `_triage_suggestions`）。

★ 这条判据在 **smoke_test.py 的正文**里（不属于注入器的 CHECKS），所以要像
  STALE_HOOK / STALE_CONFIG 那样，在生成时对 `src` 做定点替换。
"""
import ast
from pathlib import Path

P = Path("_mk_v1230_smoke_checks.py")
s = P.read_bytes().decode("utf-8").replace("\r\n", "\n")

if "STALE_P2B" in s:
    print("已有 STALE_P2B，跳过")
    raise SystemExit(0)

OLD = (
    '        # 7 crosscheck：两条路都在 + tier 门仍在 + 旧单路径已撤\n'
    '        _k0 = src.find("def _anchor_crosscheck")\n'
    '        _k1 = src.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1\n'
    '        _xc = src[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else src[_k0:]\n'
    '        assert "_hit_by_answers(str(" in _xc, "crosscheck 未接 answers 路径"\n'
)
NEW = (
    '        # 7 [v1.23.2] crosscheck 路径：两条路都在 + tier 门仍在 + 旧单路径已撤\n'
    '        #   ★ 组装逻辑已抽成纯函数 `_triage_suggestions` ⇒ 区域 = 两处之和，\n'
    '        #     并**钉住调用关系**（否则「搬走了」与「删掉了」看起来一样）。\n'
    '        _k0 = src.find("def _anchor_crosscheck")\n'
    '        _k1 = src.find(NL + "    def ", _k0 + 10) if _k0 >= 0 else -1\n'
    '        _xc0 = src[_k0:_k1] if _k0 >= 0 and _k1 > _k0 else src[_k0:]\n'
    '        _t0 = src.find("def _triage_suggestions")\n'
    '        _t1 = src.find(NL + "def ", _t0 + 10) if _t0 >= 0 else -1\n'
    '        _ts = src[_t0:_t1] if _t0 >= 0 and _t1 > _t0 else ""\n'
    '        _xc = _xc0 + NL + _ts\n'
    '        assert "_triage_suggestions(" in _xc0, \\\n'
    '            "crosscheck 未调 _triage_suggestions（组装逻辑搬走后没接上）"\n'
    '        assert "_hit_by_answers(str(" in _xc, "crosscheck 未接 answers 路径"\n'
)
assert s.count(OLD) == 1, "OLD 锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)

OLD2 = """        assert 'if int(x.get("tier", 3) or 3) <= _floor_c' in _xc, "tier 门丢了\""""
NEW2 = """        assert 'int(x.get("tier", 3) or 3) <= _floor' in _xc, "tier 门丢了\""""
assert s.count(OLD2) == 1, "OLD2 锚点命中 %d 次" % s.count(OLD2)
s = s.replace(OLD2, NEW2)

# 在生成流程里声明 STALE_P2B（供审计/自证看到）
ANCH = "# --- 过期配置登记同步 ---"
assert s.count(ANCH) == 1, "插入锚点命中 %d 次" % s.count(ANCH)
s = s.replace(ANCH, """# ---- [v1.23.2] 过期区域判据同步：`check_v1221_p2b` 的第 7 步（triage 组装
#      逻辑已抽成 `_triage_suggestions`，区域要扩成两处之和 + 钉调用关系）。
#      ★ 这条判据在 smoke 正文里（不在 CHECKS 字面量里），所以在上面已经
#        对 `src` 做过定点替换；这里只留一个可被 grep 到的标记。----
STALE_P2B = "已在生成时定点替换（见上方 OLD/NEW）"

""" + ANCH)

ast.parse(s)
P.write_bytes(s.encode("utf-8"))
print("生成器已加 STALE_P2B（区域判据同步）")

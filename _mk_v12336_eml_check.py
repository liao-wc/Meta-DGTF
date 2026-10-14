# -*- coding: utf-8 -*-
"""v1.23.36 判据：**EML 两向对账**（保证「学了一定有人用」）。

## 为什么必须有这条
本版实测逮到：`eml_candidates_from_result` 生成 **4 种** `action.key`，而
`_eml_apply` 只有 **2 个**分支 ⇒ `carve_first` / `tri_advisory_only` /
`note_cost_no_gain` **生成→过闸→存库→召回，但永不生效**，且**无判据可见**。

## 判据（两向 + 构造性）
  ① **正向**：`eml_candidates_from_result` 里出现的每个 `"key": "xxx"`
     ⇒ 必须**要么**在 `_eml_apply` 有 `_key == "xxx"` 分支、
     **要么**在 `_EML_RECORD_ONLY` 豁免表里；
  ② **反向**：豁免表里的每个 key **必须**真的被生成过
     （否则是**过期登记** —— 登记表不能只增不减）；
  ③ **构造性**：造一个 episode（截断层 + 职责不足）⇒ 真调
     `eml_candidates_from_result` ⇒ 抽 key ⇒ 对账（证**真能生成**，不是只写在源码里）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"

NEW_FN = '''def check_v12336_eml():
    """[v1.23.36] EML 两向对账：**每个 action.key 要么有应用分支、要么登记豁免**。

    ★ 为什么：不这么查，「学而不做」可以长期静默存在（召回日志只说「用了几条」，
      不说「其中几条真生效」）。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    if "_EML_RECORD_ONLY" not in src:
        bad.append("[EML] 缺 `_EML_RECORD_ONLY`（「只记录」没有显式登记）")
        print("  X", bad[-1])
        return False

    # ① 静态：生成侧 vs 应用侧 vs 豁免表
    _i_gen = src.find("def eml_candidates_from_result")
    _i_gen_end = src.find("\\ndef ", _i_gen + 10)
    _gen = src[_i_gen:_i_gen_end if _i_gen_end > 0 else _i_gen + 6000]
    import re as _re3
    _gen_keys = sorted(set(_re3.findall(r'"key":\\s*"([a-z_0-9]+)"', _gen)))
    _i_ap = src.find("def _eml_apply")
    _i_ap_end = src.find("\\n    def ", _i_ap + 10)
    _ap = src[_i_ap:_i_ap_end if _i_ap_end > 0 else _i_ap + 4000]
    _ap_keys = sorted(set(_re3.findall(r'_key == "([a-z_0-9]+)"', _ap)))
    _ex = getattr(mod, "_EML_RECORD_ONLY", None) or {}
    if not _gen_keys:
        bad.append("[EML] 从 `eml_candidates_from_result` 里**抽不到** action.key"
                   "（改写形态了？判据需要更新）")
    _missing = [k for k in _gen_keys if k not in _ap_keys and k not in _ex]
    if _missing:
        bad.append("[EML] 这些 key **生成了但既不应用也没登记豁免**：%r"
                   "（学而不做、且不可见）" % (_missing,))
    _stale = [k for k in _ex if k not in _gen_keys]
    if _stale:
        bad.append("[EML] 豁免表里有**过期登记**（不再生成）：%r" % (_stale,))

    # ③ 构造性：真造一个 episode，看能不能真生成（不是只写在源码里）
    try:
        _ep = {"stop": {"0": "体力耗尽（4 圈走满，是被截断）"},
               "duty": {"0": {"S": 0.0}},
               "quality": {},
               "tri_state": {}}
        _cands = mod.eml_candidates_from_result(_ep) or []
        _got = sorted({(c.get("action") or {}).get("key")
                       for c in _cands if isinstance(c, dict)})
        _got = [k for k in _got if k]
        if not _got:
            bad.append("[EML] 构造性：喂一个截断层 episode **一条候选都没生成**"
                       "（学习闸门过严？）")
        else:
            _m2 = [k for k in _got if k not in _ap_keys and k not in _ex]
            if _m2:
                bad.append("[EML] 构造性生成的 key 有对不上的：%r" % (_m2,))
    except Exception as _e:
        bad.append("[EML] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 EML 两向对账（生成侧 %r ↔ 应用侧 %r ↔ 豁免 %r · "
          "无学而不做 · 无过期登记）全过" % (_gen_keys, _ap_keys, sorted(_ex)))
    return True


def check_v12336_tick():'''

ANCHOR_CALL = '''    if not check_v12336_tick():
        return 1'''
NEW_CALL = '''    if not check_v12336_tick():
        return 1
    if not check_v12336_eml():
        return 1'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "smoke_test.py 应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    n = s.count("def check_v12336_tick():")
    assert n == 1, "插入锚点命中 %d 次" % n
    s = s.replace("def check_v12336_tick():", NEW_FN, 1)
    n2 = s.count(ANCHOR_CALL)
    assert n2 == 1, "调用锚点命中 %d 次" % n2
    s = s.replace(ANCHOR_CALL, NEW_CALL, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK EML 对账判据已加；smoke_test.py 行数 %d" % out.count(b"\n"))


main()

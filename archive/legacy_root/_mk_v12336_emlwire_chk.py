# -*- coding: utf-8 -*-
"""判据 + 变异体：EML 五分支「学了要做，与调度层融合」。

## 判据增量（加进 `check_v12336_eml`）
  · **五个应用分支都要在**（含新接的 `carve_first` / `tri_advisory_only` /
    `note_cost_no_gain`）—— 防"删分支"这种退化；
  · 三向对账（生成侧 ⊆ 应用侧 ∪ 豁免表）**已有**，现在豁免表为空 ⇒
    等价于「生成侧必须全部有应用分支」（**这就是「学了要做」的判据化**）。

## 变异体（M69~M71）
  · M69：删 `carve_first` 分支 ⇒ 它落回「无分支且无豁免」⇒ 判据判红；
  · M70：`tri_advisory_only` 分支改成不做实事（不写控制面）⇒ 判据的
    "分支存在"仍绿，但**构造性**那侧要能抓到 —— 见下；
  · M71：`note_cost_no_gain` 的减圈写成「加圈」（方向反了）⇒ 判据判红。

★ M70 的设计要点：**"分支存在" 与 "分支真的改了调度量" 是两件事** ——
  所以判据除了源码级「分支在」，还要有一条**功能性**断言：喂一条
  `tri_advisory_only` 候选给 `_eml_apply`，看 `_duty_floor` **是否真的变了**。
"""
import io
import re
from pathlib import Path

SM = Path(__file__).resolve().parent / "smoke_test.py"
MU = Path(__file__).resolve().parent / "_mut_v12332.py"

# ── A：判据增量（加在 check_v12336_eml 的静态对账之后）──
SM_OLD = '''    _missing = [k for k in _gen_keys if k not in _ap_keys and k not in _ex]
    if _missing:
        bad.append("[EML] 这些 key **生成了但既不应用也没登记豁免**：%r"
                   "（学而不做、且不可见）" % (_missing,))'''

SM_NEW = '''    _missing = [k for k in _gen_keys if k not in _ap_keys and k not in _ex]
    if _missing:
        bad.append("[EML] 这些 key **生成了但既不应用也没登记豁免**：%r"
                   "（学而不做、且不可见）" % (_missing,))
    # ★ [学了要做] 五个应用分支都要在（防"删分支"退化）。
    for _k in ("rounds_delta", "duty_floor", "carve_first",
               "tri_advisory_only", "note_cost_no_gain"):
        if '_key == "%s"' % _k not in _ap:
            bad.append("[EML] `_eml_apply` 缺分支 %r（学了要做，不许只剩记录）"
                       % _k)
    # ★ [学了要做 · 功能性] 「分支在」≠「分支真的改了调度量」——
    #   直接喂一条 `tri_advisory_only` 给 `_eml_apply`，看 `_duty_floor`
    #   是否**真的变了**（这是"与调度层融合"的可执行证据）。
    try:
        _cfg_t = build_cfg(False)
        _mt_t = mod.MetaDGTF(_cfg_t)
        _mt_t._eml_mode = "on"
        _fl0 = float(getattr(_mt_t, "_duty_floor", 0.0) or 0.0)
        _mt_t._eml_used = [{"id": "T-TRI", "action": {"key": "tri_advisory_only",
                                                      "rate": 0.1}}]
        _mt_t._eml_apply({})
        _fl1 = float(getattr(_mt_t, "_duty_floor", 0.0) or 0.0)
        if _fl1 == _fl0:
            bad.append("[EML] `tri_advisory_only` **没有真的改调度量**"
                       "（_duty_floor %s → %s）⇒ 只是记账不是融合" % (_fl0, _fl1))
        # 同一把尺子量第四个：`note_cost_no_gain` 应让圈数**变小**
        _mt_t2 = mod.MetaDGTF(build_cfg(False))
        _mt_t2._eml_mode = "on"
        _mt_t2._eml_used = [{"id": "T-COST",
                             "action": {"key": "note_cost_no_gain"}}]
        _rp = {"0": 4, "1": 3}
        _mt_t2._eml_apply(_rp)
        if not all(int(v) < 4 for v in _rp.values()):
            bad.append("[EML] `note_cost_no_gain` 没把圈数**降下来**：%r" % (_rp,))
    except Exception as _e3:
        bad.append("[EML] 功能性验证抛错：%r" % (_e3,))'''

# ── B：变异体 M69~M71 ──
MU_OLD = '''    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。'''
MU_NEW = '''    #   ★ M69 打在**「学了要做」**上（删 `carve_first` 分支 ⇒ 它落回
    #     "无分支且无豁免" ⇒ 判据的两向对账必判红）。
    ("M69 删 carve_first 分支（又变成学而不做）",
     "            elif _key == \\"carve_first\\":",
     "            elif _key == \\"carve_first_DISABLED\\":"),
    #   ★ M70 打在**「分支真的改调度量」**上（分支还在，但什么都不做 ⇒
    #     源码级判据仍绿，必须靠**功能性**断言抓 ⇒ 这就是那条断言存在的理由）。
    ("M70 tri_advisory_only 分支空转（分支在、不做事）",
     "                _new_fl = round(min(1.0, (_cur if _cur > 0 else 0.35) * 1.15), 4)",
     "                _new_fl = _cur"),
    #   ★ M71 打在**方向**上（`note_cost_no_gain` 该降圈却写成加圈 ⇒
    #     "花多赚少反而多跑" ⇒ 判据必判红）。
    ("M71 note_cost_no_gain 方向反了（该降圈却加圈）",
     "                    _new = max(1, _old - 1)\\n"
     "                    if _new == _old:\\n"
     "                        continue",
     "                    _new = max(1, _old + 1)"),

    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。'''


def main():
    s = SM.read_text(encoding="utf-8")
    assert s.count(SM_OLD) == 1, "判据锚点命中 %d 次" % s.count(SM_OLD)
    s = s.replace(SM_OLD, SM_NEW, 1)
    SM.write_text(s, encoding="utf-8")
    print("OK 判据已加（5 分支 + 功能性）")

    m = MU.read_text(encoding="utf-8")
    if "M69 删 carve_first 分支" in m:
        print("M69~M71 已存在（跳过）")
    else:
        assert m.count(MU_OLD) == 1, "变异体锚点命中 %d 次" % m.count(MU_OLD)
        m = m.replace(MU_OLD, MU_NEW, 1)
        MU.write_text(m, encoding="utf-8")
        _order = re.findall(r'"(M\d+) ', m)
        print("OK M69~M71 已加；MUTS 尾 6：%r" % (_order[-6:],))
        assert _order[-3:] == ["M69", "M70", "M71"], "顺序不对"


main()

# -*- coding: utf-8 -*-
"""修**真跑逮到的真缺陷**：`merge_expand` 开时 `yin_yang_divergence` 静默缺失。

## 缺陷（本版全开真跑实测）
真跑 `_fullrun_V1236FULL`（11 项全开，含 `actions.merge_expand=True`）的
`quant.json` 里**四层都只有 3 个读数**（缺 `yin_yang_divergence`）——
而上一次 `V1234FULL` 是**四层四个读数齐（16 条）**。

**根因**（读码确认）：
```
_expand_pair: 若 merge_expand 且恰好两臂 ⇒ _expand_pair_merged_once ⇒ **提前 return**
              ⇒ 下面那句 `self._quant_pending_yy = _yy`（L9896）**永不执行**
run:          `_yy = getattr(self, "_quant_pending_yy", None); if _yy: _quant_note(...)`
              ⇒ 取到 None ⇒ **不写读数**
```
⇒ 合并路径**既没算分歧、也没记「本路径不适用」** ⇒ 产物里
「**本层没有分歧读数**」与「**分歧读数为空**」**分不开**。

★ 这正是用户口径「**全开真跑不仅检验本次改动，还方便发现新问题**」的**实例**：
  缺陷由**上一轮的降本开关**引入，靠**真跑产物对比**才暴露（判据与冒烟都没抓到）。

## 修法（照**既有语义**，不另造一套）
`yin_yang_divergence()` 自己的 docstring 就写着：
「**任一侧为空 ⇒ `divergence=None` 且 `verdict=""`（不表态）**」。
⇒ 合并路径按同一口径**显式记一档**（`verdict=""` = 不表态），
并在 `why` 里写明「阴阳已合并成一次调用 ⇒ 分歧度不适用」。

## 判据增量
`check_v12336_readings` 加一条**条件断言**：
**当配置里 `actions.merge_expand` 为真时，四层的 `yin_yang_divergence` 必须存在**
（值可以是「不表态」档）—— 防它再静默消失。

## 变异体
`M72`：把合并路径那一档**去掉** ⇒ 判据必判红。
"""
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent
P = HERE / "元DGTF-V1.23.36.py"
SM = HERE / "smoke_test.py"
MU = HERE / "_mut_v12332.py"

OLD = '''        if len(jobs) == 2 and _action_on(self.config, "merge_expand", False):
            _mg = self._expand_pair_merged_once(jobs)
            if _mg is not None:
                return _mg'''

NEW = '''        if len(jobs) == 2 and _action_on(self.config, "merge_expand", False):
            _mg = self._expand_pair_merged_once(jobs)
            if _mg is not None:
                # ★ [读数完整性 · **真跑逮到**] 合并路径**不走**下面的阴阳分歧
                #   计算 ⇒ `_quant_pending_yy` 会保持 None（或上一次的值）⇒
                #   产物里「**本层没有分歧读数**」与「**分歧读数为空**」分不开。
                #   按本题**既有语义**（`yin_yang_divergence()` 的 docstring：
                #   「任一侧为空 ⇒ divergence=None 且 verdict=""（不表态）」）
                #   显式记一档 —— **不另造新语义**。
                try:
                    self._quant_pending_yy = {
                        "n_yin": None, "n_yang": None,
                        "max_sim": None, "divergence": None,
                        "verdict": "",
                        "merged": True,
                        "why": "阴阳已合并成一次调用（merge_expand）"
                               "⇒ 分歧度不适用（不表态）",
                    }
                except Exception:
                    pass
                return _mg'''

# ── 判据增量 ──
SM_OLD = '''    _rt = (_res or {}).get("readings_table") or ""'''
SM_NEW = '''    # ★ [读数完整性 · 真跑逮到] `merge_expand` 开时，合并路径**提前 return**
    #   ⇒ 阴阳分歧读数会**静默消失**（四层都缺）。合并路径修好后，
    #   它必须**有档**（值可为「不表态」= `verdict=""`）。
    if "self._quant_pending_yy = {" in src and '"merged": True' in src:
        pass          # 修复在位
    else:
        bad.append("[读数] 合并路径**没记「不表态」档** ⇒ "
                   "`merge_expand` 开时阴阳分歧读数会静默消失")

    _rt = (_res or {}).get("readings_table") or ""'''

# ── 变异体 ──
MU_OLD = '''    #   ★ M56 打在**新规范接线**上（判据 ①b 数使用处 ⇒ 少一处必判红）。'''
MU_NEW = '''    #   ★ M72 打在**真跑逮到的那处**上：合并路径去掉「已合并」标记
    #     ⇒ 判据（查 `self._quant_pending_yy = {` 与 `"merged": True` 同在）
    #     必判红。★ 用**最小改动**（只删一行）而不是整块替换 ——
    #     整块替换会因缩进对不上而产生**语法错**，那样子进程直接崩、
    #     变异体报的是"崩溃"而不是"判红"，**理由就不对了**。
    ("M72 合并路径不记「已合并」档（真跑逮到的缺陷复现）",
     '                        "merged": True,\\n',
     ''),
'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    assert s.count(OLD) == 1, "主文件锚点命中 %d 次" % s.count(OLD)
    s = s.replace(OLD, NEW, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 主文件已修（合并路径记「不表态」档）；行数 %d" % out.count(b"\n"))

    sm = SM.read_text(encoding="utf-8")
    assert sm.count(SM_OLD) == 1, "判据锚点命中 %d 次" % sm.count(SM_OLD)
    sm = sm.replace(SM_OLD, SM_NEW, 1)
    SM.write_text(sm, encoding="utf-8")
    print("OK 判据已加")

    m = MU.read_text(encoding="utf-8")
    if "M72 合并路径不记" in m:
        print("M72 已存在")
    else:
        assert m.count(MU_OLD) == 1, "变异体锚点命中 %d 次" % m.count(MU_OLD)
        m = m.replace(MU_OLD, MU_NEW, 1)
        MU.write_text(m, encoding="utf-8")
        import re
        _o = re.findall(r'"(M\\d+) ', m)
        print("OK M72 已加；MUTS 尾 4：%r" % (_o[-4:],))


main()

# -*- coding: utf-8 -*-
"""把「真缺陷：_quant_note 不可达」补写进 CHANGELOG 的第六期段。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"

ANCHOR = """【验收（第六期）】判据 **㉗~㉛**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +
  缺一侧不表态 / ㉙ 保真度方向 + 缺输入不表态 / ㉚ 语义密度方向 + 空输入不表态 +
  **「不调 LLM」的构造性证明**（spy `LLM.call` 计数须为 **0**）/ ㉛ 三处真实入口 + 出口；
  变异体 **M45**（合并开关默认打开）/ **M46**（分歧度方向反）/
  **M47**（保真度缺输入硬表态）/ **M48**（语义密度偷偷调 LLM）**均判红**（累计 **48**）。
"""

NEW = """【★★ 真跑逮到的真缺陷：`_quant_note` 结构性不可达（已修）】
  · **现象**：真跑 `_fullrun_QUANT`（四层齐 / 2 圈 / 136 calls / 133 万 tok / 59.3 min）
    落盘 `_fullrun_QUANT.quant.json` —— **四层 `quant_readings` 全空**，
    而四层目标读数 `_fullrun_QUANT.goals.json` **全部有值**
    （`0 excavate 0.0 / n_aspects 12`；`1 settle 1.0`；`both fuse 0.8519`；
    `all crystallize 1.0 / n_hits 4`）。
  · **打点探针**（`_probe_v12333_quant.py`，猴补丁包一层、**不改主文件**）四问定位：
    Q1 `_quant_note` 调用 **0 次**；Q2 三个纯函数**都跑了**
    （`restate_fidelity` → `verdict=drifted`／`coverage 0.1875`；
    `semantic_density` → **0.8004**；`yin_yang_divergence` → `divergence 0.3636`／`ok`）；
    Q4 `views` 的值是 `View` 对象（不是 dict）。
  · **根因**：`_quant_note(self, view, key, val)` **只定义在 `MetaDGTF`**，
    而三处调用点在 **`DGTF.run`**（L8776 / L8812 / L8874）——
    `MetaDGTF` **不继承** `DGTF`（每跑一层**新建 `DGTF` 实例**）
    ⇒ `DGTF` 实例解析不到该属性 ⇒ **AttributeError**；
    而三处调用都包在 `try: … except Exception: pass` 里 ⇒ **静默吞掉**。
  · ★ 这是本项目错型「**有接线 ≠ 这跑走得到**」+「**静默失败**」的合体。
    判据 ㉛ 第一版只查「`self._quant_note(view,` 出现 ≥2 次」（**存在性**）
    ⇒ 接线看似在、实则不可达 ⇒ **判据假绿**。
  · **修法**（`_patch_v12333_quantnote_fix.py`）：把 `_quant_note` **降为模块级函数**
    （它本就是纯写入口、**不依赖 self**），三处调用改裸名，
    并删掉 `MetaDGTF` 的方法版（**避免两个真相源**）。
  · **判据升级**（㉛）：从「数出现次数」改为**可达性证明** ——
    ① 模块级 `_quant_note` 必须 `callable`；② **拿真 `View` 写一条，必须落进去**；
    ③ 不许再有 `self._quant_note(`；④ 真实调用点 == 3 处；⑤ 定义份数 == 1。
  · **变异体 M49**（`_quant_note` 退回「孤儿函数」名 ⇒ 调用点解析不到）**判红**。
  · ★★ **本轮最重要的一条通则**：
    **「有接线」≠「这跑走得到」，而「查字面存在」的判据查不出可达性。**
    凡新能力，必须配「**真实入口产出**」判据（跑一次真实入口、**断言产出**），
    不能只查调用点是否存在 —— 与 v1.23.27 的 D1/D2 同族，这是它的第二次显形。

【验收（第六期）】判据 **㉗~㉛**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +
  缺一侧不表态 / ㉙ 保真度方向 + 缺输入不表态 / ㉚ 语义密度方向 + 空输入不表态 +
  **「不调 LLM」的构造性证明**（spy `LLM.call` 计数须为 **0**）/
  **㉛ 可达性**（模块级 + 真写一次 + 无 `self._quant_note(` + 3 处调用 + 1 份定义）；
  变异体 **M45**（合并开关默认打开）/ **M46**（分歧度方向反）/
  **M47**（保真度缺输入硬表态）/ **M48**（语义密度偷偷调 LLM）/
  **M49**（`_quant_note` 结构性不可达）**均判红**（累计 **49**）。
"""


def main() -> int:
    b = CL.read_bytes()
    txt = b.decode("utf-8")
    assert b"\r\r\n" not in b
    flat = txt.replace("\r\n", "\n")
    n = flat.count(ANCHOR)
    assert n == 1, "锚点命中 %d 次（应 1）" % n
    out = flat.replace(ANCHOR, NEW, 1)
    assert out.count(NEW) == 1
    data = out.encode("utf-8")
    assert b"\r\r\n" not in data
    CL.write_bytes(data)
    print("OK CHANGELOG 已补真缺陷段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

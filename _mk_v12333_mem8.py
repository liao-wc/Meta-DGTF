# -*- coding: utf-8 -*-
"""追加当日记忆第八节：真缺陷（_quant_note 不可达）+ 键登记补漏。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
F = HERE / ".workbuddy" / "memory" / "2026-10-14.md"

A = """### 验收（第二期）
- 判据 **㉖**（方向 / 缺读数不表态 / 不混 role 语义 / **两通道都接线** /
  **两条 prompt 都注入** / 初始化）；变异体 **M43 / M44** 判红。
"""

NEW = """### 验收（第二期）
- 判据 **㉖**（方向 / 缺读数不表态 / 不混 role 语义 / **两通道都接线** /
  **两条 prompt 都注入** / 初始化）；变异体 **M43 / M44** 判红。

---

## 八、★★ 真跑逮到真缺陷：`_quant_note` 结构性不可达（已修）

### 现象
真跑 `_fullrun_QUANT`（四层齐 / 2 圈 / **136 calls / 133.1 万 tok / 59.3 min**）
落盘 `quant_readings` **四层全空**，而同跑 `goals.json` 四层读数**全部有值**
（`0 excavate 0.0/n_aspects 12`、`1 settle 1.0`、`both fuse 0.8519`、
`all crystallize 1.0/n_hits 4`）⇒ 是**这一条链断了**，不是没跑。

### 定位（`_probe_v12333_quant.py` 打点四问，猴补丁包一层、不改主文件）
- Q1 `_quant_note` 调用 **0 次**；
- Q2 三个纯函数**各跑了 1 次**且值有效（`restate_fidelity`→`drifted`；
  `semantic_density`→**0.8004**；`yin_yang_divergence`→`divergence 0.3636`/`ok`）；
- Q4 `views` 的值是 `View` 对象。
- ★ **探针第一版假阴性**：我补 `MetaDGTF._quant_note`，而接线点在 `DGTF.run`
  ⇒ **打点要打在接线点真正所属的那个类上**。

### 根因
`_quant_note(self, view, key, val)` **只定义在 `MetaDGTF`**，三处调用点在
**`DGTF.run`**（L8776/8812/8874）；`MetaDGTF` **不继承** `DGTF`
（每跑一层**新建 `DGTF` 实例**）⇒ `DGTF` 实例解析不到 ⇒ **AttributeError**
⇒ 三处都包在 `try: except Exception: pass` 里 ⇒ **静默吞掉**。
★ 两条经典错型合体：「**有接线 ≠ 这跑走得到**」+「**静默失败**」。

### 判据为什么没拦住
判据 ㉛ 第一版只写 `src.count("self._quant_note(view,") < 2` —— **只查字面出现次数**
（存在性）⇒ 代码在、判据绿、路径进不去。与 v1.23.27 的 D1/D2 **同族，第二次显形**。

### 修法（`_patch_v12333_quantnote_fix.py`）
① `_quant_note` **降为模块级函数**（本就不依赖 self，只用 view）；
② 删 `MetaDGTF` 方法版（**避免两个真相源**）；③ 三处调用改**裸名**。
自检：`self._quant_note` 0 次 / `def _quant_note(` 1 份 / 真实调用点 3 处。

### 判据升级（㉛：存在性 → **可达性**）
模块级必须 `callable` + **拿真 `View` 写一条、必须落进去** +
不许再有 `self._quant_note(` + 真实调用点 ==3 + 定义份数 ==1。
**变异体 M49**（改名成孤儿）**判红**。

### 修复验证（真跑）
短真跑 `_fullrun_QFIX`（route=0 / 1 圈）：层 0 落盘 **3 条** `quant_readings`
（`restate_fidelity coverage 0.9333/ok`、`yin_yang_divergence divergence 0.5625/ok`、
`ing_density value 0.8224/chars 1084/ok`）⇒ 修前 0 条 / 修后 3 条。

### ★★ 本轮最重要通则
> **「有接线」≠「这跑走得到」，而「查字面存在」的判据查不出可达性。**
> 凡新能力，必须配「**真实入口产出**」判据 —— 跑一次真实入口、**断言产出**。

---

## 九、收尾补漏：`merge_expand` 有读点、没登记

- `_action_on(config, "merge_expand", False)` 是**读取端**（有键用键、没键落默认）
  ⇒ 行为上默认关**是对的**；但它**没登记进 `DEFAULT_CONFIG["actions"]`**、yaml 也没有
  ⇒ ① 用户在 yaml 里**打不开**；② 正好是审计 **J 类**（「每个键都要有读点」）的
  **反面**：这次是「有读点、没键」⇒ **两个方向都要有判据**。
- 修：`DEFAULT_CONFIG["actions"]` + 出厂 yaml 各登记一行（默认 false ⇒ 零行为差）。
- 验收：配置键 **192 → 193**；冒烟「键已列全（193 项）/ 手调 29 项全部已登记」、
  两向对账 **0 差**。
- ★ 通则：**新增任何开关，必须同时登记「读取端默认值」与「配置声明」** ——
  只做前者，开关是隐形的；只做后者，是「写了没生效」。

### 最终验收（v1.23.33）
- 主文件 **24514 行 / 纯 CRLF**（CR-CR-LF 三元组 0）；
- 冒烟 **223 ✓ / 0 ✗ / EXIT=0**；AUDIT **68 PASS / 0 FAIL**；
- 变异体 **49 / 49 判红**（+ M49 `_quant_note` 结构性不可达）；
- 配置 **193 键 / 两向对账 0 差**；
- 真跑：`_fullrun_QUANT`（四层齐 2 圈）全链路；`_fullrun_QFIX` 验修复（3 条读数）。
"""


def main() -> int:
    b = F.read_bytes()
    txt = b.decode("utf-8")
    assert b"\r\r\n" not in b
    flat = txt.replace("\r\n", "\n")
    assert flat.count(A) == 1, "锚点命中 %d 次" % flat.count(A)
    assert "八、★★ 真跑逮到真缺陷" not in flat, "已补过"
    out = flat.replace(A, NEW, 1)
    data = out.encode("utf-8")
    assert b"\r\r\n" not in data
    F.write_bytes(data)
    print("OK 当日记忆已补第八、九节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""报告第十一节：真跑逮到的真缺陷（_quant_note 结构性不可达）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
RP = HERE / "v12333_报告.md"

ADD = """

---

## 十一、★★ 真跑逮到的真缺陷：`_quant_note` 结构性不可达

### 11.1 现象

  第六期落地后跑真跑 `_fullrun_QUANT`（route 四层齐 / serial / 2 圈，
  **136 calls / 133.1 万 tok / 59.3 min**），落盘
  `_fullrun_QUANT.quant.json` —— **四层 `quant_readings` 全空**。
  同一次跑的 `_fullrun_QUANT.goals.json`（四层目标读数）**全部有值**：

  ```
  0     {"excavate": 0.0, "converging": false, "n_aspects": 12}
  1     {"settle": 1.0, "pseudo_convergence": false, "converging": false}
  both  {"fuse": 0.8519, "sem_stagnation": 0.1481, "n_new": 6}
  all   {"crystallize": 1.0, "n_hits": 4}
  ```

  ⇒ 不是「没跑」、不是「引擎坏了」，是**这一条特定的读数链断了**。

### 11.2 打点探针四问（`_probe_v12333_quant.py`，猴补丁包一层，**不改主文件**）

  | 问 | 结果 | 含义 |
  |---|---|---|
  | Q1 `_quant_note` 被调几次？ | **0** | 接线不可达 |
  | Q2 三个纯函数跑了吗？ | **各 1 次** | 计算**发生了** |
  | Q2b 返回了什么？ | `restate_fidelity` → `drifted`（coverage 0.1875）／`semantic_density` → **0.8004**／`yin_yang_divergence` → `divergence 0.3636`／`ok` | 值**有效** |
  | Q4 `views` 的值是什么？ | `View` 对象 | 不是 dict |

  ★ 探针**第一版假阴性**：我补的是 `MetaDGTF._quant_note`，而接线点在
  `DGTF.run` ⇒ 补错类 ⇒ Q1 报 0。**通则：打点要打在「接线点真正所属的那个类」上。**

### 11.3 根因

  · `_quant_note(self, view, key, val)` **只定义在 `MetaDGTF`**（L16636 附近）；
  · 三处调用点在 **`DGTF.run`**（L8776 / L8812 / L8874）；
  · `MetaDGTF` **不继承** `DGTF`（AST 实测：`class MetaDGTF` 无基类；
    `MetaDGTF` 每跑一层**新建 `DGTF` 实例**）；
  · ⇒ `DGTF` 实例上解析不到 `_quant_note` ⇒ **`AttributeError`**；
  · ⇒ 三处调用都包在 `try: … except Exception: pass` 里 ⇒ **静默吞掉**。

  ★ 这是本项目两条经典错型的**合体**：
    ① 「**有接线 ≠ 这跑走得到**」（v1.23.3 §8）；
    ② 「**静默失败**」（`except: pass` 让缺陷不带任何症状）。

### 11.4 判据为什么没拦住

  判据 ㉛ 第一版这样写：

  ```python
  if src.count("self._quant_note(view,") < 2:
      bad.append("[量化] _quant_note 未在真实入口调用（读数不可达）")
  ```

  **只查「字面出现次数」（存在性）** ⇒ 代码里那三行**在**、判据**绿**、
  而路径**进不去**。这与 v1.23.27 的 D1/D2（`belief_transition` 纯函数全绿
  但三条结构性不可达）是**同一族**，这是它的**第二次显形**。

### 11.5 修法（`_patch_v12333_quantnote_fix.py`）

  1. **A1**：`_quant_note` 降为**模块级函数**（本就不依赖 `self`，只用 `view`）；
  2. **A2**：删掉 `MetaDGTF` 的方法版（**避免两个真相源**）；
  3. **A3~A5**：三处调用改**裸名** `_quant_note(view, …)`；
  4. 补丁脚本自检：`self._quant_note` 出现 **0** 次 / `def _quant_note(` **1** 份 /
     真实调用点 **3** 处。

### 11.6 判据升级（㉛，**从存在性改成可达性**）

  ```python
  _qn = getattr(mod, "_quant_note", None)
  if not callable(_qn):
      bad.append("模块级 `_quant_note` 不存在（调用点在 DGTF，定义却在 MetaDGTF…）")
  else:
      _vq = mod.View(entry="0"); _qn(_vq, "judge_probe", {"value": 1})
      if (_vq.quant_readings or {}).get("judge_probe", {}).get("value") != 1:
          bad.append("`_quant_note` 写不进真 View（写入口坏了）")
  ```

  外加：不许再有 `self._quant_note(` / 真实调用点 == 3 / 定义份数 == 1。

  ★ 与项目通则一致：**「不调 LLM」要构造性证明（spy 计数为 0）**，同理
    「写入口可用」要**真写一次**（不是「我看代码能写」）。

### 11.7 判别力证明

  变异体 **M49**（把 `_quant_note` 改名成孤儿 ⇒ 调用点解析不到）**判红**。
  修前判据（只数出现次数）对 M49 **假绿**，修后判据**判红** —— 判别力增量已量化。

### 11.8 ★★ 本轮最重要的一条通则

  > **「有接线」≠「这跑走得到」，而「查字面存在」的判据查不出可达性。**
  >
  > 凡新能力，必须配一条「**真实入口产出**」判据 ——
  > 跑一次真实入口、**断言产出**，而不是「调用点存在」或「纯函数正确」。

  本次的代价：一次 59.3 min / 136 calls 的真跑 + 一轮根因定位。
  若第六期落地时就配了这条判据，缺陷会在**第一秒**被拦下。
"""


def main() -> int:
    b = RP.read_bytes()
    txt = b.decode("utf-8")
    assert b"\r\r\n" not in b
    assert "## 十一、" not in txt, "第十一节已存在"
    crlf = (txt.count("\r\n") > 0 and txt.count("\r\n") == txt.count("\n"))
    flat = txt.replace("\r\n", "\n").rstrip("\n") + ADD
    out = flat.replace("\n", "\r\n") if crlf else flat
    data = out.encode("utf-8")
    assert b"\r\r\n" not in data
    RP.write_bytes(data)
    print("OK 报告已追加第十一节（CRLF=%s）" % crlf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

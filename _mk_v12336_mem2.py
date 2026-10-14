# -*- coding: utf-8 -*-
"""补充今日记忆：v1.23.36 的最终验收数字（建版与验收之后）。"""
import io, os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".workbuddy", "memory", "2026-10-14.md")
ADD = u"""
### v1.23.36 最终验收（建版 + 全套之后）

- **升版**：`元DGTF-V1.23.36.py`（**25288 行 / 纯 CRLF**，CR-CR-LF 0，AST OK）；
  四处版本同步（docstring 标题 / `__version__` / 出厂 yaml 头部 / smoke+mut 的 SRC）；
  yaml 加升级段；**AST 登记补 19 个新符号**（registry → **305**）。
- **冒烟**：**226 ✓ / 0 ✗ / EXIT=0**（含新增 `check_v12336_allweb` /
  `check_v12336_readings`）。
- **`--phase all`**：**EXIT=0，无 ❌**；各探针 PASS 全绿（42/0 · 34/0 · 30/0 ·
  **AUDIT 69/0** · 16/0 · 26/0）。
- **配置**：叶子键 **223**；`web_search.stages` **37 键**（全 false）。
- **变异体**：M60~M64 已单独验证判红；全量（64 个）运行中。
- **真跑**：`_fullrun_V1236FULL`（四层齐 / rounds 4-4-4-5 / **11 项全开**含
  `actions.merge_expand`）运行中。

### ★★ 收尾时踩的三个坑（都是老坑的新实例）
1. **bump 时的 AST 基线用错**：我拿「上一版」当基线算差集 ⇒ 差集为空 ⇒
   **19 个新符号一个没登记**（verify 的 6.6 两向对账逮到）。
   ★ 正解：**基线要用 `_baseline_v12177.py`**（审计用的就是它）。
2. **`_probe_v123_w34.py` 的默认 SRC 是老版本**（`元DGTF-V1.23.0.py`）——
   直接跑（不传参数）会**验错对象**（C4.b 数出 6 而非 8）。
   ★ 通则：**验收脚本的默认指向要显式传**；「默认值」是验收里最隐蔽的错源。
3. **锚点没归一化换行**：修 `_probe_v123_w34.py` 时锚点是 LF 写的，而文件是
   CRLF ⇒ `count == 0`（又一次「锚点明明在却命中 0」）。
   ★ 通则：**读进来先 `replace("\\r\\n", "\\n")`**，写回时转回并断言 `\\r\\r\\n` 为 0。

### ★ C4.b/C4.c 的修法是「登记」不是「放宽」
旧判据断言「`self._web_search(` 调用点 = **6** 且全在 5 个白名单方法里」——
本轮新增 2 个**真实**调用点（修行层术语校准 / 停止判据复核）⇒ 判据**正确判红**。
改法：白名单**加名**、数量 **6 → 8**（**仍是硬等式**）—— 这是「判据随实现更新」
的**登记式**改法（有牙），不是「放宽式」（`>= 6` 就没牙了）。
"""


def main():
    src = io.open(P, encoding="utf-8").read()
    if "### v1.23.36 最终验收" in src:
        print("已存在该小节"); return
    raw = io.open(P, "rb").read()
    assert raw.count(b"\r\n") == 0, "今日记忆应为 LF-only"
    s = raw.decode("utf-8").rstrip("\n") + "\n" + ADD
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK 最终验收小节已追加，行数 %d" % s.count("\n"))


main()

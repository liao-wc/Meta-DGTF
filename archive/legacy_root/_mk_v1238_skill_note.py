# -*- coding: utf-8 -*-
"""把 v1.23.8 的方法论追加进 dgtf-version-bump 技能（幂等 + 换行自检）。

★ 技能自己中过「多级转义吃反斜杠」的招（906 行里 889 处 CRCRLF），
  所以写完必须自检 `CRCRLF == 0` 且无游离 CR。
"""
import re
from pathlib import Path

p = Path.home() / ".workbuddy" / "skills" / "dgtf-version-bump" / "SKILL.md"
raw = p.read_bytes()
print("before: CRCRLF", raw.count(b"\r\r\n"), "CRLF", raw.count(b"\r\n"),
      "bare LF", raw.count(b"\n") - raw.count(b"\r\n"))
crlf = raw.count(b"\r\n") > (raw.count(b"\n") - raw.count(b"\r\n"))
s = raw.decode("utf-8").replace("\r\n", "\n")

ADD = """
## v1.23.8 追加：渲染层守卫的三条方法论（+ 一条工具坑）

适用形态：**产物 md 的写法问题**（空节 / 读数不可见 / 重复渲染）。
这类改动的验收成本最低（探针驱动生产入口 + 变异体，全部离线），**应优先做**。

### 1. ★★ 「杀掉了靶子」≠「满足了判据」

v1.23.8 首版补丁把「六、如果只能做一件事」的**节标题行一起替换掉了** ——
空节数确实从 2 变成 0（判据目标达成），但那是靠**删标题**达成的。
是探针里一条**额外的**负对照读数（`A1_节数` 6→5、`A1_六节标题在`）当场抓出来的。

**通则：判据只量「目标值」不够，必须同时量「靶子还在不在」** ——
改「某节不许为空」，要同时断言「该节标题仍在」。

### 2. ★ 探针的目标文件必须 `.py` 结尾

`importlib.util.spec_from_file_location(name, "xxx.py.pre_patch")` 后缀不认 →
**返回 None**（不抛异常）→ 探针在第一环就死。
更坏的是当时用 `&&` 串了一长条命令：**中间失败时整条 stdout 全空**，
看起来像「什么也没发生」。改 `;` 分段 + 每步 `echo "EXIT=$?"` 后立刻现形。
**通则：诊断链每一步都要有自己的退出码回声。**

### 3. ★★ 「判据过时」与「真回归」用「跑一次基线」来分

`--phase all` 出 5 条红时，光看红名单**无法判断**是不是自己弄坏的。做法：
**临时把 `smoke_test.py` 的 `SRC` 指回上一版**、跑同一档，两份红名单并排放：

- 本版 FAIL 5 ⊂ 基线（另 2 条在基线上红、本版绿）；
- 基线上 `G.smokeSRC`（smoke 指向本版）与 `--src` 版本错配各红一次，正好互为对照。

**「红了」本身不是信号，「比基线多红了什么」才是。**
（与 §7b「AST 等价 ⇒ 可以不跑真跑」并列：那条管「该不该跑」，这条管「红了怎么判」。）

### 4. 工具坑：`.gitignore` 的 `/*.log` 与「`_smoke_*.log` 是证据」并不冲突

本仓库 `.gitignore` 有 `/*.log`（顶层运行日志 306 个 60 MB）⇒
**`_smoke_vNNNN.log` 也被忽略、不进版本库**。但 `_git_save.py` 的第 2 项防呆是
**读文件系统**上的它（不是读 git），所以防呆照常生效。
★ 结论：**防呆读的是文件，公开口径管的是跟踪** —— 两件事不冲突。
若将来要让冒烟日志也进仓库，要显式加 `!_smoke_*.log` 反向规则。

### 5. 渲染层守卫的验收组合（可直接复用）

```python
# 探针：驱动生产入口（render_landing / save_result），离线、零 LLM
parts = re.split(r"(?m)^(#{3,4} .*)$", txt)      # 切成 (标题, 正文字数)
empty = [s for s, n in zip(parts[1::2], parts[2::2]) if not n.strip()]
```
- **空节**：`empty == []` **且** 标题仍在（负对照）；
- **新读数**：无输入 → 必须返回空串（不许印 0/0 冒充读数）；
- **去重**：真跑形态必须合并 **且** 异 target 一条都不许合（否则恒去重也能过）；
- **接线**：`inspect.getsource(m.save_result)` 里必须出现新函数名（防死代码）。
"""

SENT = "## v1.23.8 追加：渲染层守卫的三条方法论"
if SENT in s:
    print("[skip] 已追加过")
else:
    if not s.endswith("\n"):
        s += "\n"
    s = s + ADD
    print("已追加 v1.23.8 方法论")

out = s.replace("\n", "\r\n").encode("utf-8") if crlf else s.encode("utf-8")
p.write_bytes(out)

chk = p.read_bytes()
fixed = re.sub(b"\r+\n", b"\r\n", chk)
if fixed != chk:
    p.write_bytes(fixed)
    chk = fixed
    print("★ 检出并修复了 CRCRLF / 游离 CR")
print("after : CRCRLF", chk.count(b"\r\r\n"),
      "CRLF", chk.count(b"\r\n"),
      "stray CR", chk.count(b"\r") - chk.count(b"\r\n"))

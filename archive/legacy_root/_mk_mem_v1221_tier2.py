#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.22.1 第二档] 落工作记忆 + 更新长期记忆与技能（全部带幂等守卫）。"""
from __future__ import annotations

import sys
from pathlib import Path

CR = chr(13)
LF = chr(10)
NL = chr(10)


def append_crlf(path: str, text: str, key: str) -> None:
    p = Path(path)
    t = p.read_bytes().decode("utf-8").replace(CR + LF, LF).rstrip(NL)
    if key in t:
        print("  · 已含该段（跳过）：" + path)
        return
    p.write_bytes((t + NL + text).replace(NL, CR + LF).encode("utf-8"))
    c = p.read_bytes()
    print("  ✓ " + path.split("/")[-1]
          + "（crr " + str(c.count(bytes([13, 13, 10]))) + "）")


DAILY = NL.join([
 "",
 "## v1.22.1 第二档 P4/P5/P6 —— **三档全绿**（2026-10-05 上午）",
 "",
 "任务书：`_v1221_taskbook.md`（P2b 通过后第一档解冻，按任务书进第二档）。",
 "文件链：rc1b（P2b）→ **rc2**（P4，与 rc1b **逐字节相同**）→ **rc3**（P5+P6）。",
 "补丁：`_mk_v1221_p56.py`（12 处）· 验收：`_mk_v1221_verify_p456.py`（把三处",
 "`_phase_todo(\"pN\")` 占位**直接替换**成真实现，PHASES 不用动）·",
 "检查：`_mk_v1221_checks_p56.py`（追加 check_v1221_p5/p6）。",
 "",
 "```",
 "python _v122_verify.py --phase p4 --src 元DGTF-V1.22.1-rc3.py → PASS 14/0 EXIT=0",
 "python _v122_verify.py --phase p5 --src 元DGTF-V1.22.1-rc3.py → PASS 14/0 EXIT=0",
 "python _v122_verify.py --phase p6 --src 元DGTF-V1.22.1-rc3.py → PASS 14/0 EXIT=0",
 "冒烟（rc3）：439 行 / 164 ✓ / 0 ✗ / EXIT=0（守卫 79 条）",
 "```",
 "",
 "### P4（一致率 ON/OFF 对照）★ 最关键的一条方法学发现",
 "任务书指定的口径（产物 md 的「三态多票：high/medium/low」行）**在 OFF 臂不可用**：",
 "那一行读每条的 `stability`，而 **`stability` 只有多票路径才写** —— OFF 臂子问题里",
 "**连键都没有**，引擎照 `(0+0)/n` 印出「一致率 0%　⚠️ unstable（＜50%）」。",
 "**那是「没算」，不是「算出来是 0」。** 若照抄口径就会得出「多票更好 +100%」这个",
 "建立在不存在读数上的结论。",
 "→ 改用一个**两臂都可得**的口径 `tri_state = [agree,total]`：",
 "  ON 80/80/80（组内极差 0%）· OFF 50/80/60（组内极差 30%）· 组间差 +16.7%",
 "  按 P4.4 的两向规则（组内极差 ≥ 组间差 → 无结论）⇒ **无结论**。",
 "汇总脚本 `_v1221_p4_agg.py` 因此出**两份** summary（`summary` 任务书口径 + `fair`",
 "公平口径）并带 `md_metric.usable=false` 与 alerts；验收加了 P4.2.c 要求报告写明。",
 "（★ 那个假告警是 v1.22.0 就有的，不是本档引入；P4 只是让它显形。本档不改它。）",
 "",
 "### P5（auto 取向回填）任务书前提与实现不符",
 "任务书写「`auto_plan` 已经带 orientation，把它带出来即可」——**不成立**：",
 "带 orientation 的是**两次调用**那条路（无任何内部调用点，给外部 API 用）；",
 "`run()` 走的**单调用**那条只回 mode/rounds/reason/confidence。",
 "→ 在**同一次调用**的 prompt 里把取向一起要出来（schema 加 `orientation`），",
 "  三处 return 都带出；**成本不变**（冒烟用打桩断言 `len(calls)==1` 钉住）。",
 "真跑：`p5_auto` 判 boundary → 头部「取向判定」+「取向错配」双双命中；",
 "`p5_boundary`（显式指定）无错配告警（负对照）。",
 "★ 顺带发现：**取向判定本身有噪声** —— 同题两次 auto 跑判出一 boundary 一 decision。",
 "  P5 的价值就是让它**可见**；要下「稳不稳」的结论需同条件 ≥3 次。",
 "",
 "### P6（tier 缺省提示）任务书骨架有真 bug",
 "骨架写 `sum(1 for a in out if \"tier\" in a and a[\"tier\"] is not None)` ——",
 "但 `out` 里每条都已被补过 `tier`（缺省 3），两个条件**恒真** → 计数恒等于总数",
 "→ `== 0` 永不成立 → **警告永远不触发**。正解：在**补默认值之前的原始条目**上数",
 "（`_n_explicit_tier`）。真跑：全缺省快照 → 产物有警告；有一条 tier=1 → 无警告。",
 "",
 "### 本轮新踩的环境/工具坑",
 "1. ★ **同一段 heredoc 脚本偶发被重复执行**：第一次已把改动写盘，第二次断言",
 "   （`count == 1`）就报 0。表现为「报错但文件其实改对了」。对策：一次性改动",
 "   脚本也加**幂等守卫**（先查哨兵串，已改则跳过），别只看 traceback。",
 "2. ★ **沙箱 safe-delete 会让 `unlink` 抛 OSError**（`SAFE_DELETE_FAIL_CLOSED`）→",
 "   检查里的「清理临时文件」不能裸调 `unlink`，必须 `except OSError: pass`；",
 "   否则清理失败会把一条**本来通过**的检查判红（冒烟曾因此从 162✓ 掉到 143✓）。",
 "3. ★ **生成代码时，别把补丁脚本里的局部名带进去**：本轮 `Q`（引号常量）",
 "   两次漏进生成代码（`Q` 是在补丁脚本里定义的），一次 `NL` 也是。",
 "   生成前先自查：生成文本里出现的每个名字，在**目标文件**里是否可见。",
 "4. ★ **`assert cond,` 换行后接消息 → 语法错误**（隐式续行只在括号内生效）；",
 "   用 `assert (cond), \"msg\"` 或把消息与右括号同行。",
 "5. ★ 注入器正则要认 `-rc1b` 这类带字母的候选版（原来 `-rc[0-9]+`，第二次就匹配不到）。",
 "",
 "### 成本",
 "余额 19.18 → 14.56（本轮 ¥4.62）：P4 六跑 + P5 两跑 + P6 两跑。",
 ""])

MEM = NL.join([
 "- ★ **「指定口径」可能在某条臂上**根本不可算**：P4 的 ON/OFF 里，任务书口径读的",
 "  `stability` 只有多票路径才写，OFF 臂连键都没有，引擎却按 `(0+0)/n` 印出",
 "  「一致率 0% ⚠️ unstable」——**非读数被当成测量值**。凡「两臂对照」，先证",
 "  **两臂都真的产出了这个量**（`\"key\" in obj`，不是 `obj.get(k)`），再谈差值。",
 "  否则差值可能是「一边没算」。",
 "- ★ **测「同一条逻辑在两条路径上的差异」前，先确认两条路径产出同一把尺子**：",
 "  P4 里 `tri_state`（判决 vs 原标签）与 `stability`（三票之间）是两个量；",
 "  拿 A 臂的量比 B 臂的量，结论无效。",
 "- ★ **任务书给的检测代码可能恒不触发**：P6 骨架在「已补过默认值的容器」上数",
 "  「谁没显式声明」，条件恒真 → 计数恒满 → 警告永不出现。凡「检测缺省」的代码，",
 "  都要在**补默认值之前**判。",
 "- ★ **前提要先验**：P5 任务书写「`auto_plan` 已经带 orientation」——实测只有那条",
 "  **没有内部调用点**的路径带，`run()` 走的那条不带。接手任务书先核前提，别照抄。",
 "- ★ **一次性改写脚本也要幂等**：本机 heredoc 偶发重复执行，`count == 1` 断言会在",
 "  第二次报 0（文件其实已改对）。加哨兵守卫（已改则跳过），别把 traceback 当失败判据。",
 "- ★ **清理不是判据**：沙箱 safe-delete 会让 `unlink` 抛 OSError；`finally` 里的清理",
 "  一律 `except OSError: pass`，否则「删不掉临时文件」会把检查判红。",
 ""])

SKILL = NL.join([
 "## v1.22.1 追加：第二档（P4/P5/P6）的四条硬教训",
 "",
 "1. **「两臂对照」先证两臂都产出了同一个量**。P4 的 ON/OFF 里，指定口径读的",
 "   `stability` 只有多票路径才写；OFF 臂子问题**连键都没有**，引擎按 `(0+0)/n`",
 "   印出「一致率 0% ⚠️ unstable（＜50%）」——**非读数被当成测量值**。",
 "   判据用 `\"key\" in obj` 而不是 `obj.get(k) is not None`（后者两种情形同形）。",
 "   并且：**量不同就不比**（`tri_state` 是「判决 vs 原标签」、`stability` 是",
 "   「三票之间」，是两把尺子）。",
 "2. **任务书给的检测代码可能恒不触发**。P6 骨架 `sum(1 for a in out if \"tier\" in a",
 "   and a[\"tier\"] is not None)`：`out` 里每条都补过缺省 `tier`，两个条件恒真 →",
 "   计数恒满 → 警告永不出现。凡「检测缺省/未声明」，**必须在补默认值之前判**，",
 "   并写一条冒烟断言钉住「在原始条目上数」（本轮是 `P6.1.c` 查 `_n_explicit_tier`）。",
 "3. **先核任务书的前提**。P5 写「`auto_plan` 已带 orientation，带出来即可」——实测",
 "   只有那条**无内部调用点**的两次调用路径带；`run()` 走的单调用路径不带。",
 "   本版在同一次调用的 prompt 里一并要取向（**不加调用次数**），并用打桩断言",
 "   `len(calls) == 1` 钉住成本不变。",
 "4. **一次性改写脚本也要幂等**。本机 heredoc 偶发重复执行：第一次已写盘、第二次",
 "   `assert count == 1` 报 0 → 看起来「失败了但其实改对了」。加哨兵守卫；",
 "   并且 `finally` 里的清理一律 `except OSError: pass`（沙箱 safe-delete 会让",
 "   `unlink` 抛错，清理失败绝不能把检查判红）。",
 "",
 "## v1.22.1 追加：验收档的接法",
 "",
 "- `_v122_verify.py` 的档位：`phase_pN = _phase_todo(\"pN\")` 占位 → **直接替换成**",
 "  `def phase_pN(src, mod):` 真实现（同名，`PHASES` 那几行不用动）。",
 "  这样既保住「未开档判红」的机制，又不会漏注册（漏注册 = `PASS 0 / FAIL 0` 假绿）。",
 "- 验收函数里要用的常量（引号 `Q = chr(34)`、`NL = chr(10)`、`CRLF`）必须在",
 "  **函数体内**定义。补丁脚本里的局部名**不会**跟着生成代码走 —— 本轮 `Q`/`NL`",
 "  各漏进生成代码一次，表现为 `name 'Q' is not defined` 的 `pN.crash`。",
 "- 跨档验收时 `--src` 要指向**当前工作版**（冒烟 SRC 指向它）；用旧版跑会触发",
 "  全局 `G.smokeSRC` 判红 —— 那是版本错配，不是缺陷。",
 ""])


def main() -> int:
    append_crlf(".workbuddy/memory/2026-10-05.md", DAILY,
                "## v1.22.1 第二档 P4/P5/P6")
    append_crlf(".workbuddy/memory/MEMORY.md", MEM,
                "非读数被当成测量值")
    append_crlf("C:/Users/18432/.workbuddy/skills/dgtf-version-bump/SKILL.md",
                SKILL, "## v1.22.1 追加：第二档（P4/P5/P6）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

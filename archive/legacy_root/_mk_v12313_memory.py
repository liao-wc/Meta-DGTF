# -*- coding: utf-8 -*-
"""v1.23.13：追加当日工作记忆（append-only）。"""
from pathlib import Path

p = Path(".workbuddy/memory/2026-10-09.md")
ADD = """

---

## v1.23.13：统一自适应调度器（十二项逐项可接管）+ 清 `auto_plan` 双实现技术债

**源** `元DGTF-V1.23.12.py`；**主文件** 17975 行（+700）/ 纯 CRLF。报告 `v12313_报告.md`。

### 做了什么
把散在 8 处的「自动」收进**一个调度器** `auto_dispatch()`，十二项一次算完：
层集合 / 成本档 / 并行模式 / 圈数 / 取向路由 / 联网 / 思考 / 强度 /
停止阈值 / 联网降级 / 可判定性判定 / 落地层模板。
每项按 `显式 ＞ 配置 ＞ auto ＞ 默认` 取值，**逐项留痕**（值 / 来源 / 理由），
产物头部新增十二条表格。auto 的输入 = 题型特征（纯规则）+ 成本质量意图 +
**历史读数**（扫最近 N 份 `*.packed.json`：成本中位 / 被截断率 / 各层实际停圈 /
三态一致率 / 联网入池与失败 / 取向错配）——**零 LLM**。
落地三类都不改判定语义：进 `run()` 参数 / 写 `cfg["runtime"]` 由既有
`_apply_runtime` 落 / 写既有阈值键（`spiral.*`、`web_search.*`）。
全关开关 `auto.enabled=false` 可回退到 v1.23.12 行为。

### 技术债（已清）
`auto_plan()` 双实现 + 双 schema：新增 `_assemble_plan()` 唯一装配器（三条出口全过它，
单调用路径因此也带上 `route`/`cost_profile`/`max_calls`）+ `_normalize_orientation()`
唯一实现（原三份，fallback 做成显式参数）。

### ★★ 本轮最值钱的五条
1. **补丁脚本只留一处真相源**。首版混用「文本级 `s.replace`」与「行级 `lines[..]`」，
   中间一次 `s = "\\n".join(lines)` **静默丢掉前面所有文本级替换**（版本号没升、
   `_assemble_plan` 4 处调用全丢）——而 `ast.parse` 通过、脚本 EXIT=0。靠探针抓到。
   ⇒ 全部编辑都在 `lines` 上做，最后 join 一次、写一次盘。
   ★ 这是「状态漂移」的**第二次**（v1.23.12 是「先算索引后替换」）。
2. **判据可能绕过被测函数**：把合成 `hist` 直接喂 `auto_dispatch` ⇒
   `_auto_history` 被跳过，变异体「恒返回空」**假绿**。补「真实介质驱动」后才判红。
3. **策略判据必须断言输出的值**：`stop` 组只查「有理由」⇒ 恒返回 `{}` 也判过。
4. **判据耦合源码字面 ⇒ 重构误报**：`P5.2.b` 数 `"orientation": _ori` 出现次数；
   收进装配器后字面消失、行为未变 ⇒ 改行为断言。
   ★ 且该判据在 `smoke_test.py` 与 `_v122_verify.py` **各有一份副本**，改前要 grep 全仓库。
5. **★★ 「来源/标签」不是「写不写」的依据**（功能级 bug）：`_apply_auto_dispatch`
   首版只写「来源 = auto」的项 ⇒ `--web off` / `--profile quality` /
   `--thinking on` / `--effort max` **全部失效**。正确规则：写 {auto, 显式} 两项；
   `source` 是给留痕用的。是既有的**接线判据**（smoke `v1.23.4` 与 `V7.a`）抓到的
   ——接线判据有不可替代的价值。

### 验收
探针 71 项读数（十二项齐全与留痕 / 逐项独立 10 项各验一次 / 总开关 / 历史 5 正 3 负 /
技术债两路同 schema / 产物十二行表）；冒烟 0 ✗；变异体 **8 个全部判红**；
`load_config` 差异 ∅ 且 yaml 覆盖出厂全键并写出 `auto.*` 三键；
AST 登记 added 104→132 两向对账。git commit 见下一段。

### 挂账状态
无。后续方向：`mode` 的 LLM 兜底可以再省（改成保守 `serial` 就彻底零调用，
代价是放弃并行收益）；`stop` 只调两个阈值，未动 `similarity`/`stalled` 一族。
"""
p.write_text(p.read_text(encoding="utf-8") + ADD, encoding="utf-8")
print("记忆已追加，行数", p.read_text(encoding="utf-8").count("\n") + 1)

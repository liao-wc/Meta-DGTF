# -*- coding: utf-8 -*-
"""v1.23.16 变更记录：插进仓库根 CHANGELOG.md（最新在最前）。

幂等：先抠掉已有的 v1.23.16 段再插。
"""
import re
from pathlib import Path

HERE = Path(".").resolve()
CL = HERE / "CHANGELOG.md"
raw = CL.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

HEAD = "v1.23.16 相对 v1.23.15"
NEXT = "v1.23.15 相对 v1.23.14"

NEW = """v1.23.16 相对 v1.23.15

【要解决的问题】v1.23.15 同题真跑（两组 8 个层圈）暴露：自然停 **1** 次、
  被截断 **7** 次；12 个层圈里 **11 个** `idle_new_amp = 0`。诊断出四条根因：
  ① 主判据量的是「字面新增」不是「语义新增」——实测研究层 16 条 & 两两词集
     重叠**峰值 0.45**、达标（≥0.55）**0 对**，于是每圈都被算成「全新 &」；
  ② 唯一能识破「换措辞」的 sat 判定（LLM 判「有没有引入新结构维度」），结论
     **只对研究层生效**，元层判出来只打一行日志 ⇒ 元层结构上不可能自然停；
  ③ sat 判定的检查间隔被成本档惰性化（3 → 4）⇒ 层上限低于 4 的层永远跑不到它；
  ④ 跨圈比对只覆盖**近 2 圈**，跨 3 圈以上的重复抓不到。

【治本三条 · 停止判据】
- 新增模块级纯函数 `_sat_override(entry, sat_verdict, idle_new_amp, idle_stall,
  r_idle_limit, r_stall_limit)` —— serial 与并行 B **共用唯一实现**。四层同等生效：
  判「无新维度」⇒ `idle_new_amp = max(_, r_idle_limit)`；0 层没有「无新 &」这条
  通路（条件 2 排除 "0"）⇒ 它的落点是 `idle_stall = max(_, r_stall_limit)`。
  未判定（None）/ 判「有新维度」（True）⇒ 一律不动计数。
- `_lazy_every_n` 去掉惰性化（恒等返回 n）—— 停止判据的检查频率不该由省钱档位决定。
- 参照集从「近 `round_window`(2) 圈的 new_amps」改成「**池内全部 &**」（`list(snap_amps)`
  / `list(snap_threads)`，serial + 并行 B 两处）；`win_amps` / `win_threads` /
  `r_window` / `spiral.round_window` 键一并删除。sat 判定的 prompt 文案同步改述
  （「近几圈已有 &」→「池内已有 &」）。

【删除成本档维度 · 本版唯一改变默认行为的改动】
- 只保留一种行为（原 `quality`：不裁剪）。删除 `_COST_PROFILES` / `_profile_plan`
  / `_PROBE_SKIP_ROLES`，以及它带走的**五类省法**：① 阴阳展开合并成一次调用
  ② 探针按「收束/复裁」角色跳过 ③ 候选截断（`_build_inp_duel` 与 `_self_check`
  两处）④ `shape_chars` / `shape_items` 缩放 ⑤ 低频项惰性化。
- 配置键 `cost_profile`、CLI `--profile`（含 `auto` 分支 `_auto_profile`）**一并删除**；
  auto 项 **12 → 11**（去掉「成本档」），产物头部「自动调度」表随之少一行；
  `_assemble_plan` schema、`_auto_pick_cost_profile`、`_AUTO_PROFILES_ORDER`（死常量）、
  产物三处渲染行（`save_result` 的「成本档位」/ 显化行 / 落地层「💰 成本档」）全部删除。
- 历史兼容侧**保留**：`_hist_from_packed` / `_hist_from_md` / `_hist_add` 里对旧产物
  `profile` 字段的读取（`.get` 容错，用于读旧产物）。
- ★ 代价如实说明：删档 = 恢复「不裁剪」，真跑 token 会高于上一版的 balanced 档。
  去惰性化还让**池重估**从每 2 圈变成每圈（`re_eval_every_n` 也走 `_lazy_every_n`）。

【验收】
- 探针 40 项读数（改前 / 改后对表）：`_COST_PROFILES` / `_profile_plan` /
  `_auto_pick_cost_profile` / `_auto_profile` 全 False、`DEFAULT_CONFIG` 无键、
  auto **12 → 11**、`_lazy_every_n(3)` **4 → 3**、窗口串 **2 → 0**、
  sat 入口的 `entry in ("1","all")` 限制消失。
- 冒烟 exit 0 / **0 ✗ / 207 ✓**；新判据 `check_v12316_stop_therapy` 五组
  （档位维度四处不存在 / 惰性化归零 / `_sat_override` 六条含三组负对照 /
  停止可达：元层拿到 sat 结论必须给出理由 / 参照集是池内全量且跨圈重复在引擎
  判重口径下成立）。
- 变异体 **7 个全部判红**（sat 不推计数 / 惰性化复活 / 参照集换空表 /
  sat 只对研究层 / 档位常量复活 / auto 项退回 12 / stall 分支不推）。
- 审计脚本 `_probe_v1232_audit.py` 在本版上 PASS 65 / FAIL 0。
- 真跑同题对照（v1.23.15 auto 组：自然停 1/4 层）：见 `v12316_报告.md` §5.4。

【本轮修掉自己九处错】(1) ★★ AST 删语句取「最小」⇒ 留下孤立 `if`（IndentationError）、
  取「最外层」⇒ 上溯到包装它的大 If（把刚注入的新判据本身都删了）；正解是**只看
  语句首行**。(2) ★★ 重叠区间必须先合并再按下标删，否则按旧行号删内层/外层会错位。
  (3) 特征串不加括号才能覆盖 `if/else` 整块。(4) ★★ yaml 里写 `@@REALRUN@@` 占位符
  裸行 ⇒ `ScannerError`（冒烟只报「出厂 yaml 解析失败」，看不出是占位符）。
  (5) 拿「已注入版」的行号去改「原始版」⇒ 锚点命中 0 次。(6) `_is_dup` 是
  `_run_layer` 内的**局部函数**，模块级取不到 ⇒ 判据改用它的两个组成函数复现口径。
  (7) ★★ **有 FAIL 时后面判据根本不跑** —— 前 151 ✓ 里不含新判据（它在 main 尾部，
  被审计那条 FAIL 提前 return）⇒「✓ 数够多」不等于「新判据跑过」。
  (8) 变异体锚点缩进写成 8 空格（实际 4）。(9) ★ 删维度要 grep「消费点」不是
  「定义点」——`cand_limit` 有两处消费（`_build_inp_duel` 与 `_self_check`）。

────────────────────────────────────────────────────────────
★ v1.23.16 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.16.py`（18408 → 18247 行，纯 CRLF）+ 本段 + `v12316_报告.md`。

**改了什么**：自然停治本三条（sat 四层同等 / 去惰性化 / 参照集池内全量）；
删除成本档维度（五类省法下线、键与 CLI 参数删除、auto 项 12 → 11）。

**验收**：冒烟 0 ✗ / 207 ✓；变异体 7/7 判红；审计 PASS 65 / FAIL 0；
探针改前改后逐项对表；真跑同题对照读数见报告。

**未做**：`_expand_pair_merged_once` 成孤儿函数但未删（冒烟判据直接调用它）；
mock 驱动 sat 通路未跑通（sat 的行为判据由纯函数承担，真跑做最终裁决）；
联网侧两条规则仍零触发；上限扫描（up6/up10）仍未补。

"""


def _strip(txt, head, nxt):
    i = txt.find(head)
    if i < 0:
        return txt, False
    j = txt.find(nxt, i)
    assert j > i, "找不到下一段"
    return txt[:i] + txt[j:], True


s, hit = _strip(s, HEAD, NEXT)
if hit:
    print("已抠掉旧的 v1.23.16 段")
assert s.count(NEXT) == 1, "下一段锚点命中 %d 次" % s.count(NEXT)
s = s.replace(NEXT, NEW + NEXT, 1)

out = s if s.endswith("\n") else s + "\n"
b = out.replace("\n", "\r\n").encode("utf-8")
assert b.count(b"\r\r\n") == 0
CL.write_bytes(b)
t = b.decode("utf-8")
print("v1.23.16 段出现 %d 次 | 收束摘要 %d 次"
      % (t.count(HEAD), t.count("★ v1.23.16 收束摘要")))

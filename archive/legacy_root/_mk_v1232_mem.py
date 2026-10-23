# -*- coding: utf-8 -*-
"""[v1.23.2] 收尾：追加工作记忆 + 更新 skill（跑批结束后执行）。"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = "元DGTF-V1.23.2.py"

_n = len((HERE / SRC).read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")) - 1
_runs = []
_j = HERE / "_v1230_w6_runs.json"
if _j.is_file():
    _d = json.loads(_j.read_text(encoding="utf-8"))
    _runs = [r for r in (_d.get("runs") or []) if r.get("ok")]
_on = [r for r in _runs if r.get("arm") == "ON"]
_tri = sorted(r.get("ea_triage") for r in _runs if r.get("arm") == "OFF")
_wn = [r.get("web_n") for r in _on]
_votes = {}
for r in _runs:
    for s in (r.get("subs") or []):
        k = len(s.get("votes") or [])
        _votes[k] = _votes.get(k, 0) + 1

MEM = """

## v1.23.2 · 整体性检查 + §十 遗留全清 · 2026-10-05/06

新增 `元DGTF-V1.23.2.py`（%d 行，纯 CRLF）。**新增整体审计探针**
`_probe_v1232_audit.py`：**10 类机械检查 + 4 个自检变异体（全判红）**，
报出 **6 类真问题**并全部处置。

### ★ 最重要的一条：15 个 `api.thinking.stages.*` **永远选不中**

`thinking` 的解析是 `if th is None and stage: th = thinking_stages.get(stage)`
—— 只有 `stage` 非空才查分档表。而 `_decompose_normal` / `_probe_*` /
`_settle_research` / `re_anchor` … **共 16 个调用点根本没传 `stage=`**
⇒ 一律掉回 `thinking.default`。后果：**用户把 `decompose_normal` 改成
`enabled` 毫无效果，且没有任何提示**。
★ yaml 里那 15 行所在分组的注释写着「── 关：…思考无收益 ──」，**值却是
`enabled`** —— 注释与值矛盾，而实际行为一直是「关」。
处置：新增 `_thinking_stage(cfg,name)`（**以配置为准**，拼错返回 None）+ 接线 16 处
+ yaml 那 15 行改成 `disabled`（与注释一致、与实际行为一致）+ 销掉 `CONFIG_TUNED`
里 15 条过期登记。**行为零变化的机器证明**在 `--phase v1232` 的 `V1/V3/V4`。
另补 2 个「代码在传、配置没声明」的 stage（`adjudicate_sub_tristate_multi`
/ `anchor_crosscheck` 按默认值 `disabled`）。

### 其余 5 类发现

`web_search.tier_floor` **从未被读过**（装饰品键，本版让它当 W# tier 门）；
**3 个死类**（`Amp`/`Probe`/`Thread` 定义后零引用）→ 登记 `_AUDIT_DEAD_CLASSES`
（只标不删 + 过期登记也判红）；`used_as` 无枚举 → `_WEB_USED_AS` 封闭集合
（W4 第三票 `arbitration` → `tri_vote`）；2 个 `web_search.stages` 键「声明了不做」
→ 登记 `_AUDIT_CONFIG_EXEMPT`。

### 四条遗留（`v1231_报告.md` §十）

命中率补**检索级连续口径 + Wilson 95%% 区间**（n 从 6 跑 → 22 次检索，
区间不含 0 ⇒ **可判定**）；正交度改**按可用票对汇总**；**空票重试**
（`actions.tri_vote_retry_empty=1`；空票是失败不是弃权）；**tier 确认生效**
（`web_search.tier_confirmed`，默认空 = 零差异，**提案→生效无自动路径**，
变异体钉住「把提案当确认用」）。
本版重跑 10 跑（`_v1230_w6_runs.json`，src=本版）：OFF triage=%s、
ON 的 W#=%s、逐条可用票数分布=%s。

### 验收

smoke EXIT=0 / 0 ✗；探针 59 / 42 / 34 / 30 / **62**（全 0 FAIL，共 **10 个变异体**）；
`--phase all` 目标 0 FAIL；AST 登记表 added 79 / 未登记 0 / 过期 0；
`dgtf_config.yaml` 两版差异 **16 项全是「改前从未生效」的键**（有机器证明）。

### 本轮 5 个工程坑（都进 skill）

1. ★ **局部变量与模块级函数同名** ⇒ `UnboundLocalError`（`_web_search` 里的
   `_ws_cfg` 撞上我新加的模块函数；Python 把它当局部）。
2. ★ **变异体锚点随实现失效**：W# 进表那块中间插了 tier 门 ⇒ 原来「从
   `if getattr(pool,…)` 到 `break`」的连续锚不连续，命中 0 次（smoke + W2 探针各一处）。
3. ★ **判据只匹配双引号**，而 `%%r` 生成的是**单引号** ⇒ 抠到 0 个 ⇒ `V1/V3` 空过。
4. ★ **`int(x or 3)` 吃掉 0**（`tier_floor: 0` 的语义是「谁都不许进」）。
5. ★ 生成器里 **`"%%s"` 忘了套 `%% _k`** ⇒ 销账一行都没生效（`_k` 成了未使用变量）；
   同一轮 heredoc 还把生成器撕坏一次（`\\n` → `/n`，第 7 次）。
"""

MEM = MEM % (_n, _tri, _wn, json.dumps(_votes, ensure_ascii=False))

mp = HERE / ".workbuddy" / "memory" / "2026-10-06.md"
mp.parent.mkdir(parents=True, exist_ok=True)
if not mp.exists():
    mp.write_bytes(b"")
b = mp.read_bytes()
nl = b"\r\n" if b.count(b"\r\n") == b.count(b"\n") else b"\n"
with open(mp, "ab") as f:
    f.write(MEM.replace("\n", nl.decode()).encode("utf-8"))
print("记忆已追加", mp.name, mp.stat().st_size)

SK = """

## v1.23.2 追加：工程级整体审计（10 类）+ 四条新硬教训

### 0. 整体审计的 10 类（`_probe_v1232_audit.py`）

A 出口完整性/死类 · B 白名单四处一致 · C 版本一致性 · D 宪法红线 ·
E 圈号口径 · F `used_as` 枚举与消费方 · G 登记表两向对账 · H 文档引用存在性 ·
**J 配置键可达性**（每个键都要有读点）· **K thinking stage 接线**
（声明的键都要能被选中）。
★ **审计必须自带自检变异体**（本探针 4 个）：没有它，「全绿」只说明判据没跑。

### 1. ★ 「配置写了但没生效」要当成一类 bug 系统性地查

一次查出 **13 个**这样的键。两类判据：
  · **J 类**：`DEFAULT_CONFIG` 的每个键在源码里（DEFAULT_CONFIG 块之外）
    至少出现一次 —— 否则「用户改了没用」且**下次审计也看不出来**；
  · **K 类**：stage 型键还要能**被选中** —— 即代码里真的有人把它当 `stage=`
    传进去（或经 `_thinking_stage()` 解析）。只「出现在源码里」不够。
  两向都要：**未登记判红 + 过期登记判红**。

### 2. ★ 让配置生效 = 有风险的改动，必须配「行为零变化」的机器证明

接通 16 处 `stage=` 接线 + 把 yaml 的 15 行改成与实际行为一致。怎么证「零变化」：
**两版配置对读 + 逐步解析结果对比**（`V1`：改前该 stage 取 `thinking_default`、
改后取 `stages[k]`，两者必须相等；`V3`：两版配置的**全部差异**只允许是
「改前从未生效」的那两类）。没有这一步，接线会顺手把一个**从未生效的高成本档**
（thinking 开 ⇒ `max_tokens ≥ 32000`）悄悄打开。
★ 顺带一条判断纪律：**注释与值矛盾时，先怀疑值** —— 那 15 行注释写着「关」、
值是 `enabled`、实际行为是「关」；正解是**改值以对齐实际行为**（最小步），
而不是让行为跟着错值跑。

### 3. ★ 局部变量与模块级函数同名 = 定时炸弹

新增模块级函数 `_ws_cfg` 后，`MetaDGTF._web_search` 里早就有一个**同名局部变量**
（`_ws_cfg = (self.config or {}).get("web_search") or {}`）⇒ Python 把整个函数里的
`_ws_cfg` 都当局部 ⇒ 同一函数中**更早**的引用抛 `UnboundLocalError`
（报错行 17609，定义行 6462，隔了 1 万行）。
**凡新增模块级函数，先 grep 同名局部**（「名字先 grep 再用」的第 4 次）。

### 4. ★ 变异体的锚会随实现失效 —— 改到新语义，别删变异体

本版在「W# 进表」那块中间插了 tier 门 ⇒ 原来「从 `if getattr(pool,…)` 到
`break`」的**连续锚变不连续**，命中 0 次（smoke 与 W2 探针各一处）。
正解：把锚改成**尾段**（`_wi += 1` 到 `break`），变异体改 `pass` ——
判据意图（「W# 有没有进表」）一字未改。**「锚点 0 次」是本项目的经典假红来源**。

### 5. ★ 判据代码自己也会有 bug（本版 5 处）

  · 抠不出东西就**空过**（`V1/V3` 因正则只认双引号、而 `%r` 生成单引号 ⇒
    `_wired` 为空 ⇒ 判据变成恒真）；
  · **多行锚点** 因中间插入新代码而失效；
  · `int(x or 3)` **吃掉 0**（`tier_floor: 0` = 谁都不许进）；
  · 生成器里 `"%s"` **忘了套 `% _k`** ⇒ 循环体恒不命中（`_k` 未使用）；
  · **heredoc 撕坏生成器**（`\\n` → `/n`，写进去才发现）—— 第 7 次，
    一律走**脚本文件**。
  通则：**判据要先证「非空」再判**；改判据后必须看它的**数字变了**。

### 6. 小样本判据要报「功效」

`P2.4.a`（「≥1 题 triage ≥ 1 条」）读的是**随机触发的低概率机制**，n=3 时
同配置两次批次能给出 [1,0,0] 与 [0,...]。凡「能力存在性」判据，
要么把样本扩到**本版全部产物**（且**版本门控**），要么在报告里写明
「n 不足 ⇒ 只作观察」，**不许**为了让判据绿而放宽。
"""

sp = Path(r"C:\Users\18432\.workbuddy\skills\dgtf-version-bump\SKILL.md")
b2 = sp.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n"), "skill 不是纯 CRLF"
with open(sp, "ab") as f:
    f.write(SK.replace("\n", "\r\n").encode("utf-8"))
b3 = sp.read_bytes()
print("skill 已更新 CRLF-ok:", b3.count(b"\r\n") == b3.count(b"\n"),
      "CRCRLF:", b3.count(b"\r\r\n"))

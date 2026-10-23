# -*- coding: utf-8 -*-
"""[v1.23.1] 收尾：追加工作记忆 + 更新 skill（跑批结束时执行）。

数字尽量**从文件算**（`_v1230_w6_runs.json`），避免手抄错。
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------- 从跑批 json 算几个数 ----------------
d = json.loads((HERE / "_v1230_w6_runs.json").read_text(encoding="utf-8"))
runs = [r for r in (d.get("runs") or []) if r.get("ok")]
on = [r for r in runs if r.get("arm") == "ON"]
off = [r for r in runs if r.get("arm") == "OFF"]
ful = [r for r in runs if r.get("arm") == "ONFULL"]
scen_hit = 0
for tag in sorted({r.get("tag") for r in on}):
    if any((r.get("web_n") or 0) >= 1 for r in on if r.get("tag") == tag):
        scen_hit += 1
_n_votes = {}
for r in runs:
    for s in (r.get("subs") or []):
        k = len(s.get("votes") or [])
        _n_votes[k] = _n_votes.get(k, 0) + 1
_stages = sorted({s for r in on + ful for s in (r.get("web_stages") or [])})
_kinds = sorted({k for r in on + ful for k in (r.get("web_round_kinds") or [])})
_tp = sum(r.get("tier_proposals_n") or 0 for r in runs)

MEM = """

## v1.23.1 · 遗留收尾（`v123_报告.md` §七 四条全做完）· 2026-10-05/06 跨零点

新增 `元DGTF-V1.23.1.py`（%d 行，纯 CRLF，`__version__ = 1.23.1`）。四条遗留 + **4 处判据缺陷**：

1. **round_no 换真圈号**：原先所有环节取「拆解序号」（每跑恒 1）⇒
   `quota.per_stage_round`（任务书写「每环节**每圈**」）退化成「每跑」，
   **三层配额实际只剩两层**。改：圈内 1..N / 前置 0 + `round_kind`/`pre_seq` 留痕。
2. **tier 提案（待审）**：`_web_tier_proposal`（纯函数）+ `domains_*` +
   `[W-TIER?]`；默认 `tier_proposal=False` = 零副作用；**绝不改 `item["tier"]`**。
3. **三场景命中率 + 三票正交度**：10 跑真数据（3 场景×2 ON + 3 题×1 OFF + 1 全路由）。
4. **P2.4.a/b 复真**：当前版按 P2b 配置重跑三题（产物落 `outputs/p2_run{1,2,3}`）。

### 跑批读数（%d 跑：ON %d / OFF %d / 全路由 %d）

- 场景命中：**%d / 3 场景**在 ON 臂 `web_n ≥ 1`；覆盖环节 %s；`round_kind` 取值 %s。
- OFF 臂：`web_n` 全 0 且 `gate.run_total = 0` —— 干净的负对照。
- 逐条**可用票数**分布（票数→子问题条数）：`%s`
  ★ 「三票」经常只有 **2 票可用**：某票返回**合法 dict 但 `judgments` 为空**时，
  原先既不报错也不留痕 ⇒ 读者看不出「三票实际两票」。已补
  `[三态多票] N/3 票可用（空票 K 张）` 留痕（**纯留痕**，不动 `ok_votes` 位置）。
- tier 提案真跑旁证：提案 %d 条（默认关时 0 条）。

### 四处判据缺陷（都不在遗留清单里，但不修「验收」就是假的）

1. ★ **C4 的锚在兜底实现上**：C4（停止与清算分开）原先只查 `settle_deferrals`
   —— 那是 **LLM 清算失败时的回落**；主路径 `_settle_research`
   （含「升级 → `undecidable`」写点）**完全没防护**。已扩到 4 个结算函数 +
   主路径变异体，并把**「旧锚对主路径变异体不判红」本身做成负对照**
   （`_probe_v123_w34.py` 26 → 34 条）。
   线索来源：真跑产物里 `_tri_final=partial` 而 `decidability=undecidable`
   且 `decidability_log` 为空 —— 「同一产物的两行数字对不上」又一次是最快入口。
2. ★ **`P2.4` 取产物取「文件名排序第一」**：目录里旧产物与新产物并存 ⇒
   判据读到**旧的那份** ⇒ 「用当前版复真」变成「拿旧读数冒充新读数」。
   已改取 mtime 最新 + 把历史产物清出（备份 `outputs/_p2a_hist_run{1,2,3}`）。
3. **W34 `A4` 的锚随实现失效**（调用点加了 `r_actual + 1`）——
   判据随实现更新，且改成**更强**的语义（同时钉位置与传参）。
4. **三票「空票」无声**（见上）。

### 验收

smoke EXIT=0 / 0 ✗ / **172 ✓**；探针 **59 / 42 / 34 / 29**（全 0 FAIL，含
**6 个变异体**）；`--phase v123_w1/w2/w34/w5/w6` 全 0 FAIL；AST 登记表 added 73 /
未登记 0 / 过期 0；`dgtf_config.yaml` 已同步（`load_config` 前后**逐字相同**）。
差异：对 v1.23.0 **纯删除行 0**。

### 遗留1 的**如实结论**（不许写成「已证明」）

- 「第三票更特立独行」有 ON 臂正证据（agree12 0.333 > agree23 0.0 / agree13 0.167）；
- 但 **OFF 臂只有 2 票可用 ⇒ 负对照缺失**，「组间 ≥ 组内」**不可判定**
  （有效重复组不足）；命中率只有 2 跑/场景 ⇒ 只作**方向性观察**。
""" % (
    len((HERE / "元DGTF-V1.23.1.py").read_bytes().decode("utf-8")
        .replace("\r\n", "\n").split("\n")) - 1,
    len(runs), len(on), len(off), len(ful), scen_hit,
    "、".join(_stages) or "—", "/".join(_kinds) or "—",
    json.dumps(_n_votes, ensure_ascii=False), _tp,
)

mp = HERE / ".workbuddy" / "memory" / "2026-10-05.md"
mp.parent.mkdir(parents=True, exist_ok=True)
if not mp.exists():
    mp.write_bytes(b"")
b = mp.read_bytes()
nl = b"\r\n" if b.count(b"\r\n") == b.count(b"\n") else b"\n"
with open(mp, "ab") as f:
    f.write(MEM.replace("\n", nl.decode()).encode("utf-8"))
print("记忆已追加", mp.stat().st_size)

SK = """

## v1.23.1 追加：把「遗留收尾」做成一次可复用的四步（+4 条新硬教训）

### 0. 遗留收尾的四步范式（本轮走了一遍）

1. **先把「遗留」逐条翻译成「可判定的动作」**：代码改动（round_no / tier 提案）
   vs 真跑补证（三场景 / P2.4）。两者混在一起时，先做代码改动，
   否则真跑数据立刻过期（本轮顺序即如此）。
2. **凡「口径/语义」类遗留，先问一句：这个语义名不对有没有**实质后果**？**
   `round_no` 取拆解序号，看着是命名问题，实际让**三层配额退化成两层**。
   判据要落在**行为**（同圈拦、新圈放），不是「命名说通」。
3. **凡「补一个自动机制」的遗留，先想「为什么它原本没做」**：
   tier 自动判定被明确列为「不做」，因为**判错比不判更危险**。
   正解是做**提案 + 待审**（默认关、纯留痕、不改任何字段），
   而不是把「不做」直接翻成「做」。
4. **凡「补真跑」的遗留，先给结论写清「可判定性门槛」**：
   组间 ≥ 组内、n 不足即「不可判定」。**测出来了但不可判定**也是结论，
   而且必须与「没测」分开写。

### 1. ★ 判据的锚要对准「实现本体」，不是「同类里最好找的那个函数」

C4（停止与清算分开）原先锚在 `settle_deferrals` —— 一个 **7 行的兜底函数**
（LLM 清算失败才回落）。真正跑主路径的 `_settle_research`
（含「升级 → `undecidable`」写点）**完全没有防护**。
**验证方法**：往**主路径**注入一次违规，看旧判据是否判红；
不判红就说明锚错了。并且要把「旧锚不判红」本身做成**负对照**留在判据里。
★ 通则：一个概念有「主路径 + 兜底」两条实现时，判据必须**锚主路径**，
兜底也要覆盖（本项目「同一条逻辑两条实现」的第 9 次）。

### 2. ★ 判据取产物要取「最新」，不能取「排序第一」

`sorted(d.glob("*.md"))[0]` —— 产物名以时间戳开头 ⇒ 目录里旧产物存在时
**永远读到旧的那份**，于是「用当前版复真」变成「拿旧读数冒充新读数」。
锚不能依赖「目录里恰好只有一份产物」这个隐含前提。
做法：`key=lambda p: p.stat().st_mtime` 取 `[-1]`，并把历史产物备份后清出。

### 3. ★ 变异体必须打在「判据读的那个东西」上

「留痕存在性」判据的变异体，第一版把留痕的**前缀改名** ——
判据找的是「票可用」四个字，改名后仍命中 ⇒ 变异体不判红、等于没测。
正解：把 `if _empty_votes:` 关成 `if False:`（**真的抠掉行为**）。
通则：变异体改的是**判据的输入**，不是判据的文案。

### 4. ★ 「合法 dict 但内容为空」是第三类失败（不是成功、也不是异常）

三票判决里，某票返回 `{"judgments": []}` ⇒ 既不抛错、`ok_votes` 还 +1，
产物只表现为「这条没人投」。实测 3 跑里 **2 跑**如此 ⇒
「三票」名义三票、实际两票，而**读者看不出原因**。
通则：`isinstance(x, dict)` 只是「形状对」；**「形状对但内容空」要有自己的留痕**。
凡「N 个来源投票/取数」的机制，都要报**可用来源数**，不能只报总数。
"""

sp = Path(r"C:\Users\18432\.workbuddy\skills\dgtf-version-bump\SKILL.md")
sb = sp.read_bytes()
assert sb.count(b"\r\n") == sb.count(b"\n"), "skill 不是纯 CRLF"
with open(sp, "ab") as f:
    f.write(SK.replace("\n", "\r\n").encode("utf-8"))
b2 = sp.read_bytes()
print("skill 已更新 CRLF-ok:", b2.count(b"\r\n") == b2.count(b"\n"),
      "CRCRLF:", b2.count(b"\r\r\n"))

# -*- coding: utf-8 -*-
"""v1.23.14：在 CHANGELOG.md 最前插入本版段（幂等：先抠旧段再插）。"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"
raw = CL.read_bytes()
crlf = raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")
SEP = "  " + "\u2500" * 60

NEXT_H = "v1.23.13 相对 v1.23.12"
HEAD = "v1.23.14 相对 v1.23.13"
if s.count(HEAD) == 1:
    i = s.index(HEAD)
    j = s.index(NEXT_H, i)
    s = s[:i] + s[j:]
    print("已抠掉旧的 v1.23.14 段")

NEW = """v1.23.14 相对 v1.23.13

【主题】把「自动调度」真正接上**真实历史语料**：修一个让它读不到历史的静默 bug，
  取样从 1 份扩到 217 份，阈值从「拍脑袋」换成**实测分位 / 相对判据**。

【为什么】v1.23.13 的十二项自适应读不到历史，两个原因：
  ① `_auto_history` 只扫 `**/*.packed.json` —— 而 `outputs/` 里有 **368 份产物 md**、
     只落了 **1 份** packed（旧版本不落 packed）⇒ 历史样本=1，所有阈值实际都在走
     「无历史」分支；
  ② 它把「实际停圈」的字段名读成了 `rounds`，真实字段是 **`rounds_run`**
     —— `dict.get` 静默返回 None，「实际停圈」**一整版都没生效**；
     而产物里也没有任何渲染点写这个量 ⇒ 信号既没被读、也没被记。

【做什么】
  · 修字段名（`rounds` → `rounds_run`）；产物头部新增「**实际停圈**」一行
    （`rounds_run` + `rounds_cap`），并把这条信号落进产物 —— 语料此后才积累得起来。
  · 历史取样**扩到三类来源**：packed 全量 / 产物 md 头部（只读前 8KB）/
    仓库根 `*_runs.json` 跑批记录。实测样本 **1 → 217**（1 + 200 + 16），
    扫描耗时 0.16s。新增 `history_md` / `history_batch` 两个开关可关。
  · 读数扩到**分位**（token / calls 的 p50 / p75）+ **按题型分桶**
    （事实型 / 决策型），策略变成「同类题比同类题」。
  · 阈值改实测：
    · 成本档降档改**相对判据**（同类成本中位 ≥ 全语料 p75 才降档），
      不再写死「40 万 token」——实测该读数对**取样窗口敏感**
      （p75 全语料 1,050,814 vs 最近 200 份 711,161，差 1.5 倍）。
    · 圈数改**三级回退**：实际停圈（需 ≥3 份样本）→ 种子上限（实测 p50：
      修行 4 / 研究 4 / 对撞 5 / 元 6）→ 按层实测默认。**样本数不足不采纳**，
      防单条噪声盖掉 200 份分布。
  · `auto.history_limit` 20 → **200**；新增 `auto.history_md` / `auto.history_batch`。
  · 产物的历史读数行**报出样本量、来源与每个读数的 n**，让人自己判断可信度。

【验收】
  · 语料分析：`_hist_corpus.py`（快速）/ `_hist_corpus_calib.py`（校准版：
    引擎判据分组 + cap 与实际停圈分开）；读数落 `_hist_corpus_summary.json` /
    `_hist_calib.json`。**全语料 384 条**（1 packed + 367 md + 16 batch）。
  · 探针 `_probe_v12314_hist.py` 41 项读数（三源 / 字段名 / 分桶 / 三级回退 /
    相对判据 / 落产物），含 **6 组负对照**（关掉两源掉回 1 份、空串抽取返回 {}、
    packed 里 `rounds` 不认、样本不足退回上限、同类不贵不降、一致率低不降）。
  · 冒烟 exit 0 / 0 ✗ / 209 ✓（守卫 101→102）。
  · 变异体 7 个全部判红（字段名读错 / md 源不扫 / 跑批源不扫 / 不按题型分桶 /
    忽视样本门槛 / 成本档退回绝对阈值 / 实际停圈不落产物），control 判绿。
  · ★ 首版判据在 **M5 / M6 上假绿** —— 两条都是「判据选错了分辨样例」：
    M5 用 0/1 层测样本门槛，那一层 `_layer_floor` 是 4，「采纳 2」与「不采纳 4」
    都被钳到 4；改**元层**（floor 5）才判红。M6 的合成样例里「绝对阈值」与
    「相对判据」结论恰好一致；补一条**两者会分歧**的样例（同类 90 万 < 全语料
    p75 500 万）才判红。⇒ **判据的样例要选在两种实现会分歧的地方**。
  · `load_config` 差异 == `{auto.history_limit}`（20→200，本版有意改）；
    yaml 覆盖 DEFAULT_CONFIG 全键（缺 0）并写出全部 5 个 `auto` 键；
    AST 登记 added 132→142 两向对账；主文件 17984 → 18286 行 / 纯 CRLF。

【未做 / 边界（如实记账）】
  · 三条规则**当前无数据支撑**：被截断率只有 6 层样本、三态一致率 n=1、
    联网失败与空结果 0 次。规则保留 + 在产物里标注 n，**不宣称已校准**。
  · `history_limit=200` 仍有窗口效应（读数随窗口变），未做分层抽样 / 时间衰减。
  · 未真跑：取样与阈值都是纯规则，真实语料 + 合成样例即可覆盖。

@@SEP@@
★ v1.23.14 收束摘要
@@SEP@@

**交付物**：`元DGTF-V1.23.14.py`（18286 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + `auto` 段两个新键 + `history_limit` 20→200 + 升级段）。

**改了什么**：修「实际停圈」字段名静默 bug + 产物新增该行；历史取样扩到三类来源
  （1 → 217 份样本）；读数扩到分位并按题型分桶；成本档改相对判据、圈数改三级回退
  （带样本门槛）。

**验收**：语料分析 384 条 + 探针 41 项（6 组负对照）；冒烟 0 ✗ / 209 ✓；
  7 个变异体全部判红（含首版两处假绿被修）；`load_config` 差异恰为本版有意改的
  一项；AST 登记两向对账绿。

**未做**：三条零样本规则的校准、窗口加权、真跑验证。

""".replace("@@SEP@@", SEP)

assert s.count(NEXT_H) == 1, "下一段锚点命中 %d 次" % s.count(NEXT_H)
s = s.replace(NEXT_H, NEW + NEXT_H, 1)
out = s.replace("\n", "\r\n").encode("utf-8") if crlf else s.encode("utf-8")
CL.write_bytes(out)

chk = CL.read_bytes().decode("utf-8").replace("\r\n", "\n")
secs = re.findall(r"^v(1\.2\d(?:\.\d+)?) 相对", chk, re.M)
sums = [l.strip() for l in chk.split("\n") if "★ v1.2" in l and "收束摘要" in l]
dup = {t: sums.count(t) for t in set(sums) if sums.count(t) > 1}
print("段数 %d | 首三段 %s | 收束标题 %d | 重复 %s"
      % (len(secs), secs[:3], len(sums), dup or "无"))

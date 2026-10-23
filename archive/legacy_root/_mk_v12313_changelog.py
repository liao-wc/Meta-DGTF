# -*- coding: utf-8 -*-
"""v1.23.13：在 CHANGELOG.md 最前插入本版段（幂等：先抠旧段再插）。"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"
raw = CL.read_bytes()
crlf = raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")
SEP = "  " + "\u2500" * 60

NEXT_H = "v1.23.12 相对 v1.23.11"
HEAD = "v1.23.13 相对 v1.23.12"

if s.count(HEAD) == 1:
    i = s.index(HEAD)
    j = s.index(NEXT_H, i)
    s = s[:i] + s[j:]
    print("已抠掉旧的 v1.23.13 段")

NEW = """v1.23.13 相对 v1.23.12

【主题】把「自动」从散落的 8 处收进**一个统一自适应调度器**：十二项逐项可
  单独接管，每项按「题型 / 成本质量 / 效率 / 历史读数」自适应，逐项留痕；
  并清掉 `auto_plan()` 的双实现与双 schema 技术债。

【为什么】v1.23.12 之前：成本档 / 联网 / 思考强度散在 main 三条纯规则；
  模式与圈数散在 run 两次 LLM；取向路由一处；停止 / 联网降级 / 配额写死在
  yaml。三个后果 —— ① 读者答不出「这一次是谁定的 route / 圈数 / 联网」；
  ② 做不到「只让 auto 管一项」（`--rounds` 默认 `"0"`、`--route` 默认全四层，
  「没给」与「给了」不可区分）；③ 停止 / 降级阈值是常量，不吃题型与历史。

【做什么】
  · 新增 `auto_dispatch()`：十二项一次算完 —— 层集合 / 成本档 / 并行模式 /
    圈数 / 取向路由 / 联网 / 思考 / 强度 / 停止阈值 / 联网降级 /
    可判定性判定 / 落地层模板。每项按 `显式 ＞ 配置 ＞ auto ＞ 默认` 取值，
    逐项留痕（值 / 来源 / 理由）。
  · auto 的输入三类，**全部零 LLM**：`_auto_features`（纯规则题型特征）、
    已给的 cost/effort/rounds（成本质量意图与效率约束）、
    `_auto_history`（扫最近 N 份 `*.packed.json`：成本中位 / 被截断率 /
    各层实际停圈 / 三态一致率 / 联网入池与失败 / 取向错配）。
  · 逐项策略：12 个纯函数 `_auto_pick_*`。规则能定的不调 LLM（事实短题直接
    `serial`，省一次调用），拿不准才交 `_decide_parallel_mode` 兜底。
  · 落点三类、**都不改判定语义**：直接进 `run()` 参数（route/mode/rounds/
    orientation/landing/decidability）；写 `cfg["runtime"]` 由既有
    `_apply_runtime` 落（web/thinking/effort，唯一写入者）；写既有阈值键
    （`spiral.*` / `web_search.*`）。
  · 产物头部新增「**自动调度**（逐项来源）」十二条表格 + 题型特征 + 历史读数。
  · CLI：`--route/--rounds/--appendix` 默认改 **None**（区分「没给」与
    「给了」）；新增 `--landing` / `--decidability`。
  · 取向与落地层**解耦**：v1.23.12 之前 `auto` 在路由侧按 decision、在模板侧
    按题面分流，同一趟自相矛盾（靠「取向错配」告警自证）；现在取向管砍层、
    landing 管模板，各有自己的来源与理由。
  · 全关开关 `auto.enabled: false` ⇒ 十二项一律退回配置 / 默认，
    行为回到 v1.23.12（**可回退**）。

【技术债】`auto_plan()` 双实现 + 双 schema（v1.21.71 F8 起挂账）：
  · 新增 `_assemble_plan()` —— **唯一装配器**，三条出口（单调用正常 / 低置信 /
    失败 + 两段式出口）全过它 ⇒ schema 只有一种；单调用路径因此也带上了
    `route` / `cost_profile` / `max_calls`（由缺变有）。
  · 新增 `_normalize_orientation(v, fallback)` —— **唯一实现**，`fallback`
    做成显式参数（外部 API 要保守值、热路径要「未知」），原三份归一化消失。
  · 顺带把 `P5.2.b` 从「数源码字面 `"orientation": _ori`」改成**行为判据**
    （低置信打桩 ⇒ 断言 `mode == "serial"` 且 `orientation == "boundary"`）。

【验收】
  · 探针 `_probe_v12313_dispatch.py`（零 LLM，合成输入 + 合成历史）71 项读数：
    十二项齐全与留痕；**逐项显式接管 10 项各验一次**（每项都断言「只改这一项」）；
    总开关关掉后无一项为 auto；历史自适应 5 正 3 负；技术债（唯一实现 +
    两路 schema 逐键相同）；产物十二行表。
  · 冒烟 exit 0 / 0 ✗ / 208 ✓（守卫 100→101）。
  · 变异体 8 个全部判红（显式泄漏 / 总开关失效 / 历史不读 / 单调用绕过装配器 /
    两段式绕开装配器 / 产物表不渲染 / **显式值不落配置** / stop 策略空），control 判绿。
  · ★ 首版判据有**两处假绿**，靠变异体抓出：M3（判据把 hist 直接喂进调度器，
    绕过了 `_auto_history` 本身）与 M7（判据从没看过 `stop` 算出来的**值**）。
    分别补「真实介质驱动」与「值断言」后才判红。
  · ★ **修掉一个自己引入的功能级 bug**：`_apply_auto_dispatch` 首版只写
    「来源是 auto」的项 ⇒ `--web off` / `--profile quality` / `--thinking on` /
    `--effort max` **全部失效**（值只存在于 plan 里、没人搬进 cfg）。正确规则：
    写来源 ∈ {auto, 显式} 的项；`source` 是给**留痕**用的，不是给「写不写」用的。
    是既有的**接线判据**（smoke `v1.23.4` 与 `_v122_verify` `V7.a`）抓到的。
  · ★ 三条判据随实现更新（都不是放宽，是换成**行为断言**）：
    `P5.2.b`（原数源码字面 `"orientation": _ori`）、
    smoke `v1.23.4` 的三开关接线、`v1.23.11` 的联网接线（原查
    `_web_auto_for_facts(" ".join(args.question))` 与 `"web": _web` 两处字面）。
    ★ 同一判据可能在**多个文件里有副本**（`P5.2.b` 同时在 `smoke_test.py` 与
    `_v122_verify.py`），改判据前要 grep 全仓库。
  · `load_config` 逐字差异 ∅；yaml 覆盖 DEFAULT_CONFIG 全键（缺 0）
    且文本层面写出 `auto.*` 三键。AST 登记 added 104→132（两向对账）。
  · 主文件 17275 → 17984 行（+709）/ 纯 CRLF。

【未做 / 边界】未真跑（十二项都是纯规则或配置写值，合成输入即可覆盖；
  唯一 LLM 交互走既有 `_decide_parallel_mode`，未改）。**历史读数在真实样本
  下的稳定性**要攒够样本才看得出（当前 `outputs/` 只有 1 份 packed），属采样
  而非工程。`stop` 只调两个阈值，未动 `similarity` / `stalled` 一族。

@@SEP@@
★ v1.23.13 收束摘要
@@SEP@@

**交付物**：`元DGTF-V1.23.13.py`（17984 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + 新增 `auto` 三键 + 升级段）。

**改了什么**：新增统一自适应调度器（一次算完十二项，逐项来源留痕）+ 12 个
  策略纯函数 + 历史读数加载器 + 产物「自动调度」表；CLI 三个默认值改 None 并
  新增 `--landing/--decidability`；取向与落地层解耦；清 `auto_plan` 双实现
  技术债（唯一装配器 + 唯一取向归一化）。

**验收**：探针 71 项读数（含逐项独立、总开关、历史 5 正 3 负）；
  冒烟 0 ✗ / 208 ✓；8 个变异体全部判红（含首版两处假绿被修）；
  `load_config` 差异 ∅ 且 yaml 覆盖出厂全键；AST 登记两向对账绿。

**未做**：真跑验证（属采样问题，非工程问题）。

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

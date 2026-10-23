# -*- coding: utf-8 -*-
"""v1.23.12：在 CHANGELOG.md 最前插入本版段（可重复运行：先抠掉旧段再插）。"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"
raw = CL.read_bytes()
crlf = raw.count(b"\r\n") == raw.count(b"\n")
s = raw.decode("utf-8").replace("\r\n", "\n")
SEP = "  " + "\u2500" * 60

NEXT_H = "v1.23.11 相对 v1.23.10"
HEAD = "v1.23.12 相对 v1.23.11"

# ── 幂等：先抠掉已有的 v1.23.12 段（段与段之间没有 `---` 分隔线，
#    直接从本段标题切到下一段标题）─────────────────────────────
if s.count(HEAD) == 1:
    i = s.index(HEAD)
    j = s.index(NEXT_H, i)
    s = s[:i] + s[j:]
    print("已抠掉旧的 v1.23.12 段")

NEW = """v1.23.12 相对 v1.23.11

【主题】把「外部锚点」拆成**两条通道**分别写明：文本锚点（`external_anchor`
  —— 锚点**文件**）/ 联网检索（`web_search` —— **联网**）。全在渲染层。

【为什么】v1.23.11 真跑产物里，联网明明收了 6 条（`pool.meta` 的
  `[W-OK] …收 3 条` ×2，W1–W6，零失败），但产物只写一行
  「**外部锚点**：无（本产物不含外部事实校验；…）」—— 读者据此会认为
  本次**没有做任何外部校验**。两套机制互相独立（一个关着不代表另一个没跑），
  旧实现只渲染其中一套。

【做什么】
  · 新增 `_web_lane_stats(res)`：联网侧读数（开/关/未记录、条数、W# 编号、
    环节数、tier 分布、失败条数与 kind），纯函数、零 LLM。
  · 新增 `_anchor_lane_lines(res)`：**单一实现**，输出两条通道行，在产物
    **四处**共用 —— 头部 / 显化说明 / decision 落地 / boundary 落地。
    两处落地层各加一节「### 七、外部锚点（两条通道分开记账）」，节首写明
    两者独立、一条没有时也各自写明。
  · `save_result`：头部改由 `_anchor_lane_lines` 出两条通道行；
    锚点的**明细**（对照 / 分级 / triage 降级 / 冲突 / 入池）**原样保留**
    —— 两条通道是**多一条出口**，不是换掉这些读数；
    「本次未接入外部校验」留痕**改为仅在联网关时**出现（旧实现只看锚点
    文件在不在 ⇒ 联网开着也写「未接入」，口径错位）。

【验收】
  · 探针 `_probe_v12312_anchor_lanes.py` 用 **v1.23.11 真跑的 packed 原文**
    驱动 `save_result`（零 LLM 调用）：改前「外部锚点 · 联网」在产物里
    不可见，改后**四处同时出现**，头部写出
    `**外部锚点 · 联网**（`web_search`）：**开** —— 收 6 条
    （W1、W2、W3、W4、W5、W6；2 个环节；tier 3×6）；失败 0 条`，
    文本通道写「无」。7 组对照（三态 / 失败留痕 / 零条 / 异常 / 决策题
    不提示 / 收 0 条）全部符合预期。
  · 冒烟 exit 0 / 0 ✗ / 207 ✓（守卫 99→100）。
  · 变异体 `_probe_v12312_mutants.py`：control 判绿；
    M1 丢联网通道 / M2 联网恒报关 / M3 错误数清零 / M4 落地层漏接 /
    M5 头部漏接 / M6 锚点明细被吃掉 —— **六个全部判红**。
  · ★ 首版判据在 M5 上**假绿**：头部那处调用被删后仍判过 —— 产物正文后面
    还有「显化说明」，两条通道又从那里出现一次，而判据查的是「整篇产物」。
    已收紧为**首个二级标题之前**的头部区间。
  · ★ 首版改动把锚点明细当「旧单通道块」整段撤掉 ⇒ `--phase all` 的
    `[4.7] 头部含『锚点分级』+『triage 降级』` 判红（那是**信息**，
    不是旧形态）。已恢复明细，并把这条写进判据 G 段 + M6 变异体。
  · 旧关闭态断言（`v1.21.73` 的 `[A]`）**随实现更新**（语义不放宽）：
    仍要求「关闭时不许出现『已接入』」，锚点改到新实现那条文本通道的写法，
    并**新增**「联网通道整条不许丢」。
  · `load_config` 逐字差异 0 项；AST 登记 added 102→104（两向对账）；
    主文件 17171 → 17275 行（+104）/ 纯 CRLF。

【未做】无。

@@SEP@@
★ v1.23.12 收束摘要
@@SEP@@

**交付物**：`元DGTF-V1.23.12.py`（17275 行 / 纯 CRLF）；本段；`dgtf_config.yaml`
  （头部版本 + 升级段，**无新键 ⇒ 行为逐字不变**，`load_config` 逐字差异 0 项）。

**改了什么**：两个新纯函数（`_web_lane_stats` / `_anchor_lane_lines`）+ 产物
  四处渲染点接线 + 锚点明细保留 + 未校验留痕改为仅联网关时出现。

**验收**：真实 packed 驱动的 before→after 对表（联网 6 条在产物里由不可见
  变为四处可见）；冒烟 0 ✗ / 207 ✓；6 个变异体全部判红（含首版两处假绿被修）；
  `load_config` 差异 0 项；AST 登记两向对账绿。

**未做**：无。

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

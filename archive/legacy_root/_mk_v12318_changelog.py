# -*- coding: utf-8 -*-
"""v1.23.18 CHANGELOG 段（幂等：先抠旧的同版段再插）。"""
from pathlib import Path

P = Path(".").resolve() / "CHANGELOG.md"
raw = P.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

HEAD = "v1.23.18 相对 v1.23.17"
NEXT = "v1.23.17 相对 v1.23.16"

NEW = '''v1.23.18 相对 v1.23.17

【要解决的问题】把「外部锚点」默认打开。但只翻一个默认值不行 ——
  `enabled=true` + 没配 `path` 在改前是**一条错误路径**（`_load_anchors` 记
  `"enabled=True 但没有给 path"`）：只翻默认值 ⇒ **每一次默认运行都在产物头部
  写「已接入 0 条；⚠️ 接入失败」、正文写「锚点异常」**。一把开关换来每跑一个假故障。

【改了什么】
- `external_anchor.enabled` 出厂默认 **false → true**（`DEFAULT_CONFIG` + 出厂 yaml
  两处一致）。
- **造出「未挂文件」这个独立干净态**：`_load_anchors` 在 `path` 为空时置
  `self._anchor_unconfigured = True` 并 **不记 error**（改前正是记 error）；
  `_anchor_crosscheck` 的 base dict 新增 `unconfigured` 键，且无锚点时**不再**塞
  「没有可用锚点（未开启或加载失败）」兜底文案。
  ★ **负对照**：`path` 非空但文件不存在 ⇒ **仍然记 error**（失败不许被吞成「未挂文件」）。
- **文本通道渲染两态 → 四态**：缺失⇒`**关**` / 未挂⇒`**开（未挂锚点文件）**` /
  已接入⇒`**开** —— 已接入 N 条` / 失败⇒`**开** —— ⚠️ 接入失败`。
  ★ 缺席态文案由「无」改成「**关**」，与联网通道对称。
- **产物「锚点明细」未挂文件时不再写五行零**（原先写「结论 0 条 / 印证 0 / 冲突 0 /
  无对应 0 / 入池 0」—— 读起来像「对照做过、结果全是 0」）；改成一行
  「**锚点对照**：未做 —— 通道开着但**没有挂锚点文件**」。
- **事实题「未接入外部校验」留痕改成按两条通道的实际状态发言**（改前写
  「两条通道都关：锚点文件无、联网检索关」—— 锚点默认开着之后这句就不成立了）。

【判据】
- **改**两处旧判据（判据随实现更新，不是放宽）：`[A]` 关闭态夹具原来**靠默认关**
  才成立 ⇒ 改成**显式关**；`[A]` 与 `check_v12312_anchor_lanes` case A 的文案断言
  「…：无」→「…：关」（后者还改成**只取文本通道那一行**再查，比原来更准）。
- **新增** `check_v12318_anchor_default_on`：出厂值（DEFAULT + yaml 都 true、
  不预置 path）/ 干净态行为 + **负对照**（path 不存在仍记 error）/ 渲染四态互不冒充 /
  产物不写五行零且不写「锚点异常」。
- 变异体 **4/4 判红**（默认开回退 / 干净态记 error / 渲染缺未挂态 / 明细仍写零行）。

【验收】
- 探针 12 项读数变化：`A_def_enabled` False→**True**；`B_err`
  `'enabled=True 但没有给 path'`→**`''`**；`B_unconfigured` 无→**True**；
  四态渲染各说各的（改前「未挂文件」与「失败」都渲染成「已接入 0 条」）；
  五行零明细 → **false×4**；留痕话术两版对照（含**新增的 `E2` 真跑形态**：
  「锚点通道：**开着但未挂文件**」）。
- 冒烟 `exit 0 / ✗ 0 / ✓ @@SMOKE@@`。
- 整体审计 **PASS 67 / FAIL 0**；配置三向：`load_config` 差异**恰为**
  `{external_anchor.enabled: False → True}`；yaml 列全 `DEFAULT_CONFIG` 全部键；
  登记表无过期条目（yaml 值改后仍 == 默认 ⇒ 无需登记）。
- 主文件 18258 → **18287** 行 / 纯 CRLF；AST 符号新增/消失 **0**。

【未做 / 遗留（如实记账）】
- **没有 `--anchor on/off` 命令行开关**（锚点只有配置文件一个入口）；本版不加。
- `external_anchor` **仍不是 auto 调度项**（v1.23.13 明确排除），保持原分工。
- 出厂 yaml **不预置 `path`**（锚点快照是题相关的；`anchors/` 下有 6 份真实快照，
  要用就把 `path` 指过去）。
- 真跑只跑了**不带锚点文件**这一态；「已接入 N 条」「接入失败」两态由冒烟的
  `[B]`/`[C]` 用**整次 mock run** 覆盖，没有再花一次真跑。
- 未挂文件时走 `logger.info`（不是 warning）—— 日志里会多一行 INFO。

'''

if HEAD in s:
    i = s.index(HEAD)
    j = s.index(NEXT, i)
    s = s[:i] + s[j:]
    print("已抠掉旧的 v1.23.18 段")

assert s.count(NEXT) == 1, "下一段锚点命中 %d 次" % s.count(NEXT)
s = s.replace(NEXT, NEW + NEXT, 1)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
t = out.decode("utf-8")
print("v1.23.18 段数:", t.count("v1.23.18 相对 v1.23.17"),
      "| 段序前 3:", [x for x in t.split("\n") if x.startswith("v1.23.1")][:3])

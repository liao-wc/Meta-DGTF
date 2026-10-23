# -*- coding: utf-8 -*-
"""同步 v1.23.64 的版本引用、符号注册表、配置头与 CHANGELOG 段。"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD, NEW = "元DGTF-V1.23.63.py", "元DGTF-V1.23.64.py"

# ── 1. 门禁脚本的 SRC ──────────────────────────────────────
for fn in ("smoke_test.py", "_mut_v12332.py"):
    p = HERE / fn
    t = p.read_text(encoding="utf-8")
    old = 'SRC = HERE / "%s"' % OLD
    if old in t:
        p.write_text(t.replace(old, 'SRC = HERE / "%s"' % NEW), encoding="utf-8")
    elif ('SRC = HERE / "%s"' % NEW) not in t:
        raise SystemExit("%s 里没有旧/新 SRC" % fn)
    print("SRC updated:", fn)

# ── 2. AST 注册表：新增符号逐条解释 ────────────────────────
REASONS = {
    "ArgumentationFramework": "F4 论证框架：grounded 扩展 + 负担排序 + 弱连通分量",
    "attackers": "F4 取某论证的攻击者集合",
    "burdens": "F4 负担式排序（阻尼迭代求不动点）",
    "components": "F4 攻击图的弱连通分量",
    "defeated": "F4 不在 grounded 扩展里的论证",
    "grounded_extension": "F4 grounded 语义不动点",
    "find": "F4 连通分量内部辅助（并查集）",
    "_strength": "F4 负担并列时的证据强度破平",
    "_bocpd_pred": "F3 NIG 共轭的 Student-t 预测密度",
    "bocpd_run": "F3 贝叶斯在线变点检测（run-length 后验）",
    "_ev_log_wealth": "F1 e-process 对数财富的网格混合",
    "evalue_bernoulli": "F1 任意停时 e-value（0/1 序列）",
    "anytime_decided_e": "F1 e-process 版「多数已确立」停止判据",
    "anytime_decided": "F1 停止判据分派：hoeffding（默认）/ evalue",
    "conformal_quantile": "F2 保形分位数（有限样本修正）",
    "conformal_pvalue": "F2 保形 p 值",
    "conformal_prediction_set": "F2 保形预测集（多标签/空集=弃权）",
    "arguments_from_playbook": "F4 playbook 条目 → 论证图",
    "resolve_playbook_conflicts": "F4 只标不删的冲突裁决（并列保持 undecided）",
    "_eml_pid_alive": "EML 锁：陈旧锁回收前的活进程判定",
    "_retry_delay": "LLM 重试：指数退避 + 抖动 + Retry-After",
    "_retryable": "LLM 重试：错误分类（4xx 除 408/409/429 不重试）",
}
p = HERE / "_v122_ast_registry.json"
reg = json.loads(p.read_text(encoding="utf-8"),
                 object_pairs_hook=__import__("collections").OrderedDict)
reg["current"] = NEW
reg["n_symbols_current"] = 636
reg["added"] = 347
for k, why in REASONS.items():
    reg["registry"][k] = {"phase": "F", "reason": why}
p.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n",
             encoding="utf-8")
print("registry entries:", len(reg["registry"]))

# ── 3. 配置头版本 ─────────────────────────────────────────
p = HERE / "dgtf_config.yaml"
t = p.read_text(encoding="utf-8")
old = "# 元 DGTF · v1.23.63 配置文件"
if old in t:
    p.write_text(t.replace(old, "# 元 DGTF · v1.23.64 配置文件"), encoding="utf-8")
elif "# 元 DGTF · v1.23.64 配置文件" not in t:
    raise SystemExit("yaml 头既不是旧版也不是新版")
print("yaml header updated")

# ── 4. CHANGELOG 新段（插在 --- 与 v1.23.63 之间）─────────
SEC = """v1.23.64 相对 v1.23.63

【主题】任意停时统计 / 保形预测 / 贝叶斯变点 / 抽象论证四条前沿内核进主文件；
EML 原子落盘与锁的正确性；重试的错误分类与抖动；Windows GBK 编码面收口。

【问题（本轮全项目审计，证据见 v12364_报告.md）】

| 问题 | 证据 | 影响 |
|---|---|---|
| 门禁在 GBK 下必崩 | _run_gate.py 打印 EXIT 时 UnicodeEncodeError；bench_calibrate.py 打 ✓ 崩 | 本机默认环境下五道门不可跑，且**退出码 1 会冒充失败** |
| EML 整表重写非原子 | _eml_finish 新增行时裸 open("w") | 崩溃/断电会截断记忆库；坏行又被静默跳过 ⇒ 静默丢证据 |
| 锁失败仍裸奔写库 | _eml_finish 不看 eml_lock 的 yield 值 | 并发真跑时可能无锁读-改-写 |
| 陈旧锁只看 mtime | 长跑持锁 > stale 会被第二个进程抢走 | 互斥失效（理论可复现，测试用活 pid 负对照钉住） |
| 4xx 也重试 | LLM.call 对所有异常一视同仁 | 参数错/鉴权错重试 3 次，白烧钱与时间 |
| 无抖动 | backoff ** attempt | 并行分层同拍重试（thundering herd） |
| anytime 只有一条统计口径 | stitched Hoeffding | 小样本下停得更晚（实测中位 54 圈 vs 37 圈） |

【修法 · 前沿内核 F（纯函数，无新依赖）】

· F1 e-process（Ramdas et al. 2023）：对任意停时 I 类错误 ≤ α；
  与 stitched Hoeffding 同签名分派，默认仍是 hoeffding（零行为差）。
  判据：800 次 140 步仿真的**边跑边看**假阳率 0.031 ≤ 0.05；
  功效中位 37 圈 vs Hoeffding 54 圈。
· F2 保形预测（Vovk et al. 2005）：有限样本修正分位数、p 值、预测集；
  覆盖率判据 0.940 ≥ 0.9；空校准集返回 +inf（保守全弃权）。
· F3 BOCPD（Adams & MacKay 2007）：NIG 共轭 + run-length 后验；
  5σ 漂移在 0..7 步内检出，平稳序列误报 0（合成负对照）。
· F4 Dung 论证（Dung 1995）+ 负担排序：playbook 同 (kind,cond) 动作冲突
  只标 arg_status / defeated_by，不删行、不改 status；精确并列保持 undecided
  （红线「未对齐是合法状态」）。默认关。

【修法 · 工程】

· eml_rewrite_jsonl 改 tmp + os.replace，且新增 allow_grow（只增不删）；
  _eml_finish 的新增/不变两条路都走它，删除裸 open("w") 分支。
· eml_lock：monotonic 计时、pid:token、回收前问活进程、释放只删自己的锁。
· eml_read_jsonl：坏行计数 + logger.warning（不再静默当空库）。
· LLM.call：4xx（除 408/409/429）不重试；抖动 [0.5,1.0]×backoff；
  尊重 Retry-After（上限 60s）。
· _force_utf8_streams 同时给子进程设 PYTHONUTF8/PYTHONIOENCODING（setdefault）。

【新配置键（默认保守）】
· stop.anytime_mode = hoeffding
· playbook.argumentation.enabled = false / semantics = grounded

【验证】
· 冒烟 265 ✓ / 0 ✗（+1 为本轮新判据）
· 跨档验收 PASS 319 / FAIL 0
· 工程审计 PASS 69 / FAIL 0
· 开发期判据 DEV PASS 33 / FAIL 0（_chk_v12364_dev.py）
· 内核判据 KERNEL PASS 24 / FAIL 0（_chk_v12364_kernel.py）

★ v1.23.64 收束摘要

交付物：元DGTF-V1.23.64.py（27433 行 / 纯 CRLF / +626 −50）；
四条前沿内核进单文件；两项工程加固（原子落盘 / 锁正确性）；
两项重试优化（错误分类 / 抖动）；GBK 编码面修复。

改了哪几处：主文件 12 个替换块 + 1 个插入块；smoke_test.py SRC；
_mut_v12332.py SRC；_v122_ast_registry.json（+22 符号）；dgtf_config.yaml 头；
CHANGELOG.md 本段；v12364_报告.md 新建。

验收数字：见上。

未做：保形/BOCPD 尚未接进停止判据（只有只读诊断脚本）；AGM 信念修正
未做；e-process 只做了 Bernoulli 型（多分类要新做 Dirichlet 型）。

---

"""
p = HERE / "CHANGELOG.md"
t = p.read_text(encoding="utf-8")
anchor = "---\n\nv1.23.63 相对 v1.23.62\n"
if "v1.23.64 相对 v1.23.63" in t:
    print("CHANGELOG already has v1.23.64; skip")
elif anchor not in t:
    raise SystemExit("CHANGELOG 锚点缺失")
else:
    p.write_text(t.replace(anchor, "---\n\n" + SEC + "v1.23.63 相对 v1.23.62\n", 1),
                 encoding="utf-8")
    print("CHANGELOG updated")
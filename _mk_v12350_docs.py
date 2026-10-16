# -*- coding: utf-8 -*-
"""v1.23.50 文档同步：① yaml 头 + 升级段；② CHANGELOG 本版段；③ backlog 段；④ 报告。

★ 无新配置键（`resume_ckpt` / `max_minutes` 是 `run()` 的**形参**）⇒ yaml 只改头与升级段，
  app `_KEY_CN` 无需改。
CRLF 安全：逐个文件字节级/换行同级替换。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def patch(fname, pairs, *, crlf=None, checks=()):
    p = HERE / fname
    b = p.read_bytes()
    _crlf = b.count(b"\r\n")
    _lf = b.count(b"\n")
    mode = crlf if crlf is not None else (_crlf > 0)
    if mode:
        assert _crlf == _lf and b.count(b"\r\r\n") == 0, "%s 非纯 CRLF" % fname
        t = b.decode("utf-8").replace("\r\n", "\n")
    else:
        assert _crlf == 0 and b.count(b"\r\r\n") == 0, "%s 非纯 LF" % fname
        t = b.decode("utf-8")
    for i, (o, n) in enumerate(pairs, 1):
        c = t.count(o)
        print("  %-28s 锚点%d 命中 %d" % (fname, i, c))
        assert c == 1, "%s 锚点 %d 不唯一/不存在" % (fname, i)
        t = t.replace(o, n, 1)
    for ck in checks:
        assert ck in t, "%s 缺校验串：%s" % (fname, ck)
    out = t.replace("\n", "\r\n").encode("utf-8") if mode else t.encode("utf-8")
    assert out.count(b"\r\r\n") == 0
    p.write_bytes(out)
    b2 = p.read_bytes()
    assert b2.count(b"\r\r\n") == 0
    assert (b2.count(b"\r\n") == b2.count(b"\n")) if mode else (b2.count(b"\r\n") == 0)
    print("  OK %s" % fname)


# ── ① yaml：头版本 + 升级段 ─────────────────────────────────────────
patch("dgtf_config.yaml", [(
    "# \u5143 DGTF \u00b7 v1.23.49 \u914d\u7f6e\u6587\u4ef6\n",
    "# \u5143 DGTF \u00b7 v1.23.50 \u914d\u7f6e\u6587\u4ef6\n",
), (
    "# \u3010v1.23.48 \u2192 v1.23.49\u3011\u8dd1\u4e2d\u5feb\u7167 \u2014\u2014 \u65b0\u589e\u914d\u7f6e\u952e runtime.live_checkpoint / runtime.ckpt_interval\n",
    "# \u3010v1.23.49 \u2192 v1.23.50\u3011\u65ad\u70b9\u7eed\u8dd1 + \u5feb\u7167\u8bb0\u8d26 + route \u6b7b\u6355\u83b7 + \u5899\u949f\u9884\u7b97\n"
    "#   \u2460 \u6839\u56e0\uff08\u4eca\u5929\u771f\u4e8b\u6545\uff09\uff1aA/B \u771f\u8dd1\u88ab\u5bbf\u4e3b\u56de\u6536\u4e24\u6b21\uff0818.2 / 12.7 \u5206\u949f\uff09\u2014\u2014\n"
    "#      v1.23.49 \u7684\u5feb\u7167\u53ea\u80fd\u300c\u7559\u75d5\u300d\u4e0d\u80fd\u300c\u63a5\u7740\u8dd1\u300d\uff0c\u800c\u4e14\u8fde\u70e7\u4e86\u591a\u5c11\u90fd\u67e5\u4e0d\u51fa\u6765\u3002\n"
    "#   \u2461 run(..., resume_ckpt=\u8def\u5f84)\uff1a\u590d\u7528\u5feb\u7167\u91cc**\u5df2\u5b8c\u6210\u7684\u5c42**\uff08\u4e0d\u91cd\u8dd1\u3001\n"
    "#      \u4e0d\u518d\u82b1\u90a3\u90e8\u5206\u94b1\uff09\uff0c\u5e76\u8fd8\u539f\u5b83\u4eec\u7684\u6c60\uff08\u4e0b\u6e38\u8bfb\u4e0a\u6e38\u6c60\uff09\u3002\n"
    "#   \u2462 \u5feb\u7167\u52a0\u8bb0\u8d26\uff1a`llm_calls` / `llm_tokens` / \u5404\u5c42 `rounds_run` \u21d2 \u88ab\u6740\u8dd1\u6b21\u4e5f\u80fd\u7ed3\u7b97\u6210\u672c\u3002\n"
    "#   \u2463 \u5feb\u7167\u91cc\u7684 `route` \u539f\u4e3a**\u6b7b\u6355\u83b7**\uff08\u5f15\u64ce\u4ece\u4e0d\u8bbe `_route`\uff09\u21d2 \u6052 `[]`\uff1b\u5df2\u4fee\u3002\n"
    "#   \u2464 run(..., max_minutes=N)\uff1a\u5c42\u95f4\u5899\u949f\u9884\u7b97 \u21d2 \u4f18\u96c5\u505c\uff08\u5feb\u7167\u72b6\u6001 `paused`\uff09\n"
    "#      + \u4ea7\u7269\u4ea4\u4ee3 `pending_layers` \u21d2 **\u5206\u7247\u8dd1\u5b8c**\uff0c\u4e0d\u649e\u5bbf\u4e3b\u7684\u56de\u6536\u7a97\u53e3\u3002\n"
    "#   \u2605 \u65e0\u65b0\u914d\u7f6e\u952e\uff08\u4e24\u9879\u90fd\u662f `run()` \u5f62\u53c2\uff09\u21d2 \u51fa\u5382\u884c\u4e3a\u9010\u5b57\u4e0d\u53d8\uff1b\n"
    "#     \u4e0d\u4f20 `resume_ckpt` / `max_minutes=0` \u65f6\u4e0e v1.23.49 \u9010\u5b57\u76f8\u540c\u3002\n"
    "\n"
    "# \u3010v1.23.48 \u2192 v1.23.49\u3011\u8dd1\u4e2d\u5feb\u7167 \u2014\u2014 \u65b0\u589e\u914d\u7f6e\u952e runtime.live_checkpoint / runtime.ckpt_interval\n",
)], checks=['v1.23.50', 'resume_ckpt'])

# ── ② CHANGELOG：本版段插在最前 ─────────────────────────────────────
SEC50 = """v1.23.50 相对 v1.23.49

【主题】断点续跑（复用已完成层）+ 快照记账 + `route` 死捕获 + 墙钟预算。

【问题】真实事故：今天 A/B 真跑被宿主回收**两次**（18.2 min / 12.7 min），烧掉约 ¥2
  而 **v1.23.49 的快照只能「留痕」不能「接着跑」** ⇒ 钱不可回收；连「这跑烧了多少」
  都查不出来（快照没记账）；快照里的 `route` 是**死捕获**（引擎从不设 `_route`）⇒ 恒 `[]`。

【修法】
  · `run(..., resume_ckpt=<快照路径>)`：复用快照里**已完成层**（不重跑、不再花那部分钱），
    并**还原其池**（下游层读上游池，池不还原则续跑结果与一次跑完不同）。
    层完成判据 = `_results[e]` 有值（该字段**只在层跑完后赋值**）。
    三道硬校验：状态可续（running/interrupted/paused）、题面逐字相同、**只支持 serial**
    （并行模式的 `_results` 由并发填）——不过就**按原样全跑并说明理由**，绝不静默混跑。
  · 快照加记账：`llm_calls` / `llm_tokens` / 各层 `rounds_run`。
  · 快照带 `mode`；`run()` 补 `self._route = list(route)`（记**生效** route）。
  · `run(..., max_minutes=N)`（默认 0 = 关）：层间墙钟预算 ⇒ 优雅停（快照 `paused`、
    产物交代 `pending_layers`）⇒ 切片跑完，避开宿主回收窗口。
  ★ **无新配置键** ⇒ 不传参时与 v1.23.49 **逐字相同**。

【验收】冒烟 248/0（+`check_v12350_resume`：构造性证明 + 两条负对照 + 预算优雅停）·
  verify 319/0 · AUDIT 69/0 · 变异体 99/99（+M101 续跑不跳过已完成层）。

★ v1.23.50 收束摘要：交付「断点续跑 + 快照记账 + route 修复 + 墙钟预算」；主文件 26471 行 /
  纯 CRLF / AST OK / 新增符号 2（`View.from_dict` / `load_resume_snapshot`）已登记 / 零新键。
  未做：并行模式（A/B/C/stage）的续跑（本版只支持 serial）。

"""
patch("CHANGELOG.md", [(
    "---\n\nv1.23.49 \u76f8\u5bf9 v1.23.48\n",
    "---\n\n" + SEC50 + "v1.23.49 \u76f8\u5bf9 v1.23.48\n",
)], checks=["v1.23.50 收束摘要"])

# ── ③ backlog 段（LF） ──────────────────────────────────────────────
patch("_方案_v12342_成本与闭环优化.md", [(
    "> **挂账**：记忆库目录两处解析未收敛（bandit）/ 历史 ~72 条冒烟 episode 未清 / `_smoke_*.log` 入库口径矛盾。\n",
    "> **挂账**：记忆库目录两处解析未收敛（bandit）/ 历史 ~72 条冒烟 episode 未清 / `_smoke_*.log` 入库口径矛盾。\n"
    ">\n"
    "> ## ★★ v1.23.50「断点续跑」（由真事故催生的第二件基础设施）\n"
    "> **触发**：A/B 真跑被宿主回收**两次**（18.2 / 12.7 min，约 ¥2）——v1.23.49 的快照\n"
    "> 只能留痕不能续跑 ⇒ 钱不可回收；且**记账缺失**（查不出烧了多少）。\n"
    "> **修法**：`run(resume_ckpt=…)` 复用已完成层（含池还原）+ 快照记账 + `route` 死捕获修复\n"
    "> + `run(max_minutes=N)` 墙钟预算（优雅停 `paused`，切片跑完）。**零新配置键**。\n"
    "> 冒烟 248/0 · verify 319/0 · AUDIT 69/0 · 变异体 99/99（+M101）。\n"
    "> **随后**：③ A/B 真跑改用「带续跑的分片跑」，被杀只损失当前层。\n",
)], crlf=False, checks=["v1.23.50"])

print("ALL OK")

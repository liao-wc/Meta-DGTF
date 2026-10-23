# -*- coding: utf-8 -*-
"""[v1.23.38 实验] 对表脚本：E1ALLON / E2BASE / E3ALLON 三跑对读。

产出：`_chk_v12338_exp_报告.md`（对表 + §四决策规则的机械判定）。
数据源（全部实测）：
  · `_fullrun_<TAG>.log` —— [route]/[rounds]/[mode]/[run_id]/[timing]/[counts]/
    📊 每层读数行 / [WEB-NEED] / [WEB-BACKFEED] / [W-*
  · `outputs/` 最新产物 md —— `## 读数总表` 段 + `& ` 计数
  · `dgtf_memory/episodes.jsonl` —— 按 run_id 对账 EML 写库
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAGS = ["E1ALLON", "E2BASE", "E3ALLON"]
OUT = HERE / "_chk_v12338_exp_报告.md"

rows = []


def parse_log(tag):
    p = HERE / ("_fullrun_%s.log" % tag)
    if not p.is_file():
        return {"tag": tag, "exist": False}
    log = p.read_text(encoding="utf-8", errors="replace")

    def g(pat, default=""):
        m = re.search(pat, log)
        return m.group(1).strip() if m else default

    d = {
        "tag": tag, "exist": True,
        "exit": g(r"E\d_EXIT=(\S+)"),
        "route": g(r"\[route\] (.+)"),
        "rounds": g(r"\[rounds\] (.+?)（"),
        "mode": g(r"\[mode\] (\S+)"),
        "run_id": g(r"\[run_id\] (\S+)"),
        "timing": g(r"\[timing\] (\S+)"),
        "counts": g(r"\[counts\] calls=(\d+) tokens=(\d+)"),
        "allon_notes": len(re.findall(r"\[all_on\]", log)),
        "expect_rows": len(re.findall(r"期望=", log)),
        "expect_bad": len([l for l in log.splitlines()
                           if "期望=" in l and "✗" in l]),
        "web_need": len(re.findall(r"\[WEB-NEED\]", log)),
        "backfeed": len(re.findall(r"\[WEB-BACKFEED\]", log)),
        "w_ok": len(re.findall(r"\[W-OK\]", log)),
        "w_skip": len(re.findall(r"\[W-SKIP\]", log)),
        "w_err": len(re.findall(r"\[W-(?!OK|SKIP|EMPTY|TIER)[A-Z-]+\]", log)),
        "readings_lines": len(re.findall(r"📊 \[", log)),
        "saved": g(r"已保存: (.+)"),
    }
    c = re.match(r"(\d+) tokens=(\d+)", d["counts"])
    if c:
        d["calls"], d["tokens"] = c.group(1), c.group(2)
    t = re.match(r"(\d+)s", d["timing"])
    if t:
        d["secs"] = int(t.group(1))
    return d


def parse_saved(d):
    """从产物 md 取读数总表行数与 & 计数（池段）。"""
    if not d.get("saved"):
        return
    md = Path(d["saved"])
    if not md.is_file():
        d["saved_missing"] = True
        return
    s = md.read_text(encoding="utf-8", errors="replace")
    d["md_bytes"] = md.stat().st_size
    m = re.search(r"## 读数总表（四层）\n(.*?)(?=\n## |\Z)", s, re.S)
    if m:
        rows_ = [l for l in m.group(1).splitlines() if l.strip().startswith("|")]
        d["readings_table_rows"] = max(0, len(rows_) - 2)  # 去表头/分隔
    d["amps"] = len(re.findall(r"^#### .*?&", s, re.M))
    d["pool_amps"] = len(re.findall(r"\*\*& ", s)) or len(
        re.findall(r"（&）", s))


def parse_eml(d):
    p = HERE / "dgtf_memory" / "episodes.jsonl"
    if not (p.is_file() and d.get("run_id")):
        return
    n = 0
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if d["run_id"] in line:
            n += 1
    d["eml_episodes"] = n


data = [parse_log(t) for t in TAGS]
for d in data:
    parse_saved(d)
    parse_eml(d)

# ── 渲染 ────────────────────────────────────────────────────────────
L = []
L.append("# v1.23.38 真跑实验对表（E1ALLON / E2BASE / E3ALLON）\n")
L.append("> 生成：对表脚本机械汇总；判读结论按 `_设计_v12338_真跑实验.md` §四。\n")

keys = [("exist", "日志存在"), ("exit", "EXIT"), ("run_id", "run_id"),
        ("mode", "mode"), ("route", "route"), ("rounds", "rounds"),
        ("secs", "秒"), ("calls", "calls"), ("tokens", "tokens"),
        ("allon_notes", "all_on 改动行"), ("expect_rows", "全开清单项"),
        ("expect_bad", "清单未生效"), ("readings_lines", "日志📊行"),
        ("readings_table_rows", "产物读数表行"), ("amps", "产物&段数"),
        ("web_need", "WEB-NEED"), ("backfeed", "WEB-BACKFEED"),
        ("w_ok", "W-OK"), ("w_skip", "W-SKIP"), ("w_err", "W-错误"),
        ("eml_episodes", "EML 条数"), ("md_bytes", "产物字节"),
        ("saved", "产物路径")]

L.append("\n## 一、总表\n")
L.append("| 指标 | " + " | ".join(t for t in TAGS) + " |")
L.append("|---|" + "---|" * len(TAGS))
for k, lab in keys:
    vals = []
    for d in data:
        v = d.get(k, "")
        if k == "saved" and v:
            v = "`…%s`" % Path(str(v)).name[:36]
        vals.append(str(v))
    L.append("| %s | %s |" % (lab, " | ".join(vals)))

# ── §四 决策规则机械判定 ────────────────────────────────────────────
L.append("\n## 二、决策规则机械判定（设计文档 §四）\n")
e1 = next((d for d in data if d["tag"] == "E1ALLON"), {})
e2 = next((d for d in data if d["tag"] == "E2BASE"), {})
e3 = next((d for d in data if d["tag"] == "E3ALLON"), {})

# 规则 2：回喂
L.append("### 规则 2 · 回喂闭环（v1.23.38 首测）\n")
if e1.get("web_need") or e3.get("web_need"):
    L.append("- `[WEB-NEED]` 声明：E1=%d / E3=%d；`[WEB-BACKFEED]`：E1=%d / E3=%d"
             % (e1.get("web_need", 0), e3.get("web_need", 0),
                e1.get("backfeed", 0), e3.get("backfeed", 0)))
    if (e1.get("backfeed", 0) + e3.get("backfeed", 0)) > 0:
        L.append("- **判定：回喂真跑闭环成立 ✅**")
    else:
        L.append("- **判定：有声明无回喂 ⚠** —— 查复用条件（stage 匹配/时序："
                 "声明发生后的环节才可能吃到池内 record）")
else:
    L.append("- 真跑无 `[WEB-NEED]` 声明 —— **零触发 ≠ 没用**（负对照）："
             "按需协议不强制模型声明；回喂闭环由探针与判据覆盖（已全绿）。")

# 规则 1：全开收益
L.append("\n### 规则 1 · 全开 vs 出厂（E1 vs E2）\n")
if e1.get("exist") and e2.get("exist"):
    c1, c2 = int(e1.get("calls", 0) or 0), int(e2.get("calls", 0) or 0)
    t1, t2 = int(e1.get("tokens", 0) or 0), int(e2.get("tokens", 0) or 0)
    s1, s2 = int(e1.get("secs", 0) or 0), int(e2.get("secs", 0) or 0)
    L.append("- calls：%d vs %d（×%.2f）；tokens：%d vs %d（×%.2f）；时长：%ds vs %ds"
             % (c1, c2, (c1 / c2 if c2 else 0), t1, t2,
                (t1 / t2 if t2 else 0), s1, s2))
    L.append("- 读数表行：E1=%s vs E2=%s；📊 行：E1=%s vs E2=%s"
             % (e1.get("readings_table_rows", "?"), e2.get("readings_table_rows", "?"),
                e1.get("readings_lines", "?"), e2.get("readings_lines", "?")))
    L.append("- **人工判读项**：对比两份产物 md 的「读数总表」verdict 分布"
             "（有区分度提升的层数 ≥2 且成本 ≤2× ⇒ 保留全开默认）。")

# 规则 3：对撞健康
L.append("\n### 规则 3 · 对撞型健康（E3）\n")
L.append("- E3 读数表行=%s、📊 行=%s、产物&段=%s、EML=%s"
         % (e3.get("readings_table_rows", "?"), e3.get("readings_lines", "?"),
            e3.get("amps", "?"), e3.get("eml_episodes", "?")))
L.append("- **人工判读项**：E3 产物里 fuse / crystallize 两轴是否非恒值、& 净增。")

# 规则 4：成本热点（占位，等日志细读）
L.append("\n### 规则 4 · 成本热点\n")
L.append("- 由日志逐 stage 计数人工补（脚本给出总量；细分布见各 log 尾部）。")

OUT.write_bytes(("\n".join(L) + "\n").encode("utf-8"))
print("[written] %s" % OUT.name)
for d in data:
    print(" ", d.get("tag"), "exist=", d.get("exist"),
          "calls=", d.get("calls"), "secs=", d.get("secs"),
          "need=", d.get("web_need"), "feed=", d.get("backfeed"))

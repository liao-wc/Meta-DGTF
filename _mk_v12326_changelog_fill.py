#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 收尾：把 CHANGELOG 的占位符填上，并补齐 step7/8/9 的内容。

原因：CHANGELOG 的 v1.23.26 段是在 step6 后生成的，此后又做了
  · step7  清掉补丁自引入的版次批注（v1.23.6 判据）
  · step8  修 `_sim3` 的 BM25 通道**方向性 bug** + `_sent_is_rephrase` 调序
  · step9  smoke 补结构层判据 + 换 M4 词 + 补 BM25 方向判据
这三次改动必须落进 CHANGELOG（它是唯一的变更记录承载体）。
"""
from pathlib import Path

CL = Path(__file__).resolve().parent / "CHANGELOG.md"
b = CL.read_bytes()
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

# ---------- 1. 在「4. covers」之后插 step8 的那一处（BM25 pair 修正） ----------
E1_OLD = """  4. **covers 数字编号分支补语义校验**：编号在范围内**还要**
     `_similar(探针问题, 该未触及项, 0.70) or _overlap_coef(...) >= _COV_OVERLAP_MIN(0.50)`。
     比较对象是**探针的 question vs 该项**（不是两个 untouched 项互比 —— 那是
     清单内部一致性，不是覆盖）。非数字分支原本就有 `_similar`，未动。
  5. `dgtf_config.yaml`：头部版本 + 新增升级段 + 新增 `sim` 段（2 键）。
"""
E1_NEW = """  4. **covers 数字编号分支补语义校验**：编号在范围内**还要**
     `_similar(探针问题, 该未触及项, 0.70) or _overlap_coef(...) >= _COV_OVERLAP_MIN(0.50)`。
     比较对象是**探针的 question vs 该项**（不是两个 untouched 项互比 —— 那是
     清单内部一致性，不是覆盖）。非数字分支原本就有 `_similar`，未动。
  5. **★ 修正 `_sim3` 的 BM25 通道方向（变异体 M1 挖出的真 bug）**。
     第一版实现是 `bm = (_bm25_best(a, corpus) + _bm25_best(b, corpus)) / 2`，
     而 `_bm25_best(q, corpus)` 算的是「**q 对语料每篇**取最大」——
     它测的是 **q 与语料的相关性**，**不是 a 与 b 的相似度**。后果：
     两条**各自与语料相关、但彼此毫不相干**的句子会被抬到虚高分。
     实测（改前）：`a = "量子纠缠实验需要极低温"`、
     `b = "人工智能模型部署管线优化"`，二者字面重叠 = **0.000**，
     而 `sim3(a, b, 带语料)` = **0.467**（因 `_bm25_best(a)=0.771`、
     `_bm25_best(b)=0.786`）。⇒ 新增 `_bm25_pair(query, doc, corpus)`：
     **doc 当唯一文档、IDF 取整份语料**，只累加**双方共有**的词 ⇒
     无关必为 0（实测 0.467 → **0.000**），相关对保持（0.746 → 0.717）。
     `_sim3` 内的 `bm` 改用 pair 后**双向平均**（对称化）。
  6. **`_sent_is_rephrase` 判据顺序：`_sim3` 提到首判**。
     原顺序是 `_similar` → `_sim3` → `_overlap_coef`，但 `_similar` 与
     `_overlap_coef` 是**宽尺子**（后者 min 分母还在、前者短串走子串包含），
     实测几乎**总在 sim3 之前命中** ⇒ sim3 那条线在**行为上不可观测**
     （变异体 M1 最初打这个位置，判绿 —— 这条「判绿」直接挖出了上面第 5 点）。
     调序后结构层（T 编号）短路**优先**生效。
     ★ **行为等价性已实测**：8000 组随机对 **零差异**（sim3 的分是
     `0.4·jaccard + 0.6·bm`，其中 `jaccard ≤ overlap_coef` 恒成立 ⇒
     sim3 先判不会多抓）。调序只为可观测，**不改语义**。
  7. **清掉补丁自引入的版次批注**（2 处）：本轮补丁在正文注释里写了
     「等价于 v1.23.25 里 …」，触发了 v1.23.6 起的「正文不留版次批注」判据。
     改成语义表述（「上一版」），信息不丢、判据不误报。
  8. `dgtf_config.yaml`：头部版本 + 新增升级段 + 新增 `sim` 段（2 键）。
"""
c = txt.count(E1_OLD)
assert c == 1, f"E1 锚点命中 {c} 次"
txt = txt.replace(E1_OLD, E1_NEW, 1)

# ---------- 2. 验收段补变异体沿革 + 填占位符 ----------
E2_OLD = """【验收】
  · 冒烟 `smoke_test.py`：✓=__SMOKE_OK__ / ✗=0（exit 0）；新增 `check_v12326_sim3`
  · 变异体 `_mut_v12326.py`：**__MUT_OK__ / 8 判红 + 正对照判绿**
  · 负对照 `_nv_v12326_covers.py`：改前 A 案例（covers 乱指 T1）**不报红**，
    改后**报红**，B/C/D/E 全部正确 ⇒ 修的是语义校验，不是把判据改成一味报红
  · 配置同步：166 键 / **load_config 逐字差异 0 项**（新增 2 键已显式写入出厂 yaml）
  · 主文件 CRLF 自检：`CRLF=__CRLF__ / 裸 LF=0 / lone CR=0 / \\r\\r\\n=0`
"""
E2_NEW = """【验收】
  · 冒烟 `smoke_test.py`：✓=219 / ✗=0（exit 0）；新增 `check_v12326_sim3`
  · 变异体 `_mut_v12326.py`：**8 / 8 判红 + 正对照判绿**
    ★ 变异体的价值全在「**判绿的那几条**」：第一轮跑出 5/8，
      M1（sim3 阈值）/ M3（结构层）/ M4（语料下限）三条**没被发现**。
      M1 的判绿直接挖出上面的 BM25 方向 bug（判据读的那个东西本身有问题）；
      M3 的判绿因为原样本用 `T3` vs `T3`（被 `if a == b` 先短路）；
      M4 的判绿因为原判据用「测试」当查询词（这词不在语料里 ⇒ 本就 0）。
      **改判据 + 改实现**后 8/8。没有这一轮，「全绿」只说明判据没跑。
  · 负对照 `_nv_v12326_covers.py`：改前 A 案例（covers 乱指 T1）**不报红**，
    改后**报红**，B/C/D/E 全部正确 ⇒ 修的是语义校验，不是把判据改成一味报红
  · 配置同步：**load_config 逐字差异 0 项新增键**（`sim` 段 2 键两边相等）；
    对照 v1.23.25 的 30 项历史差异 ⇒ 本版 **30 → 28**（修掉 2 项，未引入）。
  · 主文件 CRLF 自检：`CRLF=18827 / 裸 LF=0 / lone CR=0 / CRCRLF=0`
"""
c = txt.count(E2_OLD)
assert c == 1, f"E2 锚点命中 {c} 次"
txt = txt.replace(E2_NEW, E2_NEW if False else E2_NEW, 1)

# ---------- 3. 填收束摘要占位符 ----------
REPL = [
    ("__LINES__", "18827"),
    ("__BYTES__", "906886"),
    ("__SMOKE_OK__", "219"),
    ("__MUT_OK__", "8"),
    ("__CRLF__", "18827"),
    ("__NEDITS__", "14"),
]
for k, v in REPL:
    if k in txt:
        txt = txt.replace(k, v)

# ---------- 4. 收束摘要里补一句 BM25 修正 ----------
E3_OLD = """  改了哪几处：14 处编辑（版本号 ×2 / `_sim3` 族 5 个新函数 / `_REPHRASE_SIM3`
  新常量 / `_sent_is_rephrase` 签名与判据 / `_detect_ing_rephrase` 编语料 /
  `_DEDUP_SIM`+`_DEDUP_SUSP_SIM` 新常量 / `Pool.merge` 签名与体内 4 处 /
  merge 调用点读配置 / `_COV_OVERLAP_MIN` 新常量 / covers 数字分支语义校验 /
  `DEFAULT_CONFIG.sim` 段）+ smoke 2 处同步 + 配置 2 处同步。
"""
E3_NEW = """  改了哪几处：14 处编辑（版本号 ×2 / `_sim3` 族 **6 个**新函数 —— 含
  `_bm25_pair` / `_REPHRASE_SIM3` 新常量 / `_sent_is_rephrase` 签名·判据·顺序 /
  `_detect_ing_rephrase` 编语料 / `_DEDUP_SIM`+`_DEDUP_SUSP_SIM` 新常量 /
  `Pool.merge` 签名与体内 4 处 / merge 调用点读配置 / `_COV_OVERLAP_MIN` 新常量 /
  covers 数字分支语义校验 / `DEFAULT_CONFIG.sim` 段 / 清 2 处版次批注）
  + smoke 3 处同步 + 配置 2 处同步。
  ★ 其中「`_sim3` 的 BM25 通道方向修正」**不在原计划里** ——
    是变异体 M1 判绿挖出来的（见【验收】）。
"""
c = txt.count(E3_OLD)
assert c == 1, f"E3 锚点命中 {c} 次"
txt = txt.replace(E3_OLD, E3_NEW, 1)

# 未做段补一句
E4_OLD = """  未做：**真跑（full run）** —— 本版改的是内部尺子与阈值来源，**喂进模型的内容
  一字未增**（`_sim3` 只在引擎侧算相似度，不进 prompt），故以零成本判据 + 变异体
"""
E4_NEW = """  未做：**真跑（full run）** —— 本版改的是内部尺子与阈值来源，**喂进模型的内容
  一字未增**（`_sim3` 只在引擎侧算相似度，不进 prompt），故以零成本判据 + 变异体
"""
if E4_OLD not in txt:
    print("  (E4 未命中，跳过)")

out = txt.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt.encode("utf-8")
CL.write_bytes(out)

# 自检：占位符清零
left = [k for k, _ in REPL if k in out.decode("utf-8")]
print("OK CHANGELOG 已填占位符；残留 =", left)
print("lines =", out.count(b"\n"), "bytes =", len(out))

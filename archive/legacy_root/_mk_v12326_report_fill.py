#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 收尾：填报告占位符 + 把 step8/9 的发现写进报告。

改四处：
  ① 头部与 4.3 的占位符（行数/字节/冒烟/变异体/CRLF）；
  ② 4.4 `sim3` 实测值表 —— 带 corpus 那一列是 step8 前的读数，已失效；
  ③ 第 5 节变异体表 —— M1 已改打点（原来打 sim3 阈值判绿），补「判绿挖出真 bug」；
  ④ 第 7 节符号清单 —— 补 `_bm25_pair`；配置同步口径与 CHANGELOG 对齐。
"""
from pathlib import Path

RP = Path(__file__).resolve().parent / "v12326_报告.md"
b = RP.read_bytes()
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

EDITS = []

# ① 占位符
EDITS.append(("__LINES__", "18827"))
EDITS.append(("__BYTES__", "906886"))
EDITS.append(("__SMOKE_OK__", "219"))
EDITS.append(("__MUT_OK__", "8"))
EDITS.append(("__CRLF__", "18827"))

# ② 配置同步口径（4.3 表内）
EDITS.append((
    "| 配置同步 | 166 键 / **load_config 逐字差异 0 项** |",
    "| 配置同步 | **本轮新增键 0 差异**（`sim` 两键两侧相等）；对照基线："
    "出厂 yaml 与 `DEFAULT_CONFIG` 的历史差异 v1.23.25=30 项 → 本版=28 项（**修掉 2 项**） |",
))

# ③ 4.4 表（带 corpus 那列是 step8 前读数，重测）
EDITS.append((
    """| 对 | `_overlap_coef`（旧） | `_sim3` 无 corpus | `_sim3` 有 corpus |
|---|---|---|---|
| 模型 部署 / 模型 训练 | 0.500 | **0.333** | 0.422 |
| 神经网络 优化 / 神经网络 训练 | 0.500 | 0.333 | 0.540 |
| 长句（8 词）/ 长句（5 词，被包含） | **1.000** | 0.625 | 0.745 |
| `T3` / `T3` | — | **1.000** | 1.000 |
| `T3` / `T4` | — | 0.000 | 0.000 |""",
    """| 对 | `_overlap_coef`（旧） | `_sim3` 无 corpus | `_sim3` 有 corpus |
|---|---|---|---|
| 模型 部署 / 模型 训练 | 0.500 | **0.333** | 0.398 |
| 神经网络 优化 / 神经网络 训练 | 0.500 | 0.333 | 0.467 |
| 低温超导材料制备工艺 / 超导材料低温制备工艺研究 | **1.000** | 0.833 | 0.839 |
| `T3` / `T3` | — | **1.000** | 1.000 |
| `T3` / `T4` | — | 0.000 | 0.000 |
| `T3` / `3`（字符串不等、编号相同） | — | **1.000** | 1.000 |
| 量子纠缠实验需要极低温 / 人工智能模型部署管线优化（**无关但各自与语料相关**） | 0.000 | 0.000 | **0.000**（改前 0.467，见 §5.1） |

★ 最后一行是本版**最重要的一条读数**：它把 `_sim3` 的一个**方向性 bug** 钉出来
（BM25 通道测的是「各自与语料的相关性」而非「两两相似度」）。详见 §5.1。""",
))

# ④ 第 5 节变异体表 + M1 沿革
EDITS.append((
    """| # | 变异体 | 打在 | 期望 |
|---|---|---|---|
| M1 | `_sim3` 阈值抬到 0.99 | 复述判据的比较 | 判红 |
| M2 | Jaccard 分母换回 `min` | A 组分母来源（退回短句高估） | 判红 |
| M3 | 结构层短路返回 0.0 | L4 编号相等的短路 | 判红 |
| M4 | `_BM25_MIN_CORPUS` 降到 0 | B 组降级条件 | 判红 |
| M5 | BM25 归一化去掉 | B 组值域 | 判红 |
| M6 | `_DEDUP_SIM` 默认改 0.5 | C 组默认值 | 判红 |
| M7 | `merge` 忽略 `thr` 参数 | C 组「阈值接上了吗」 | 判红 |
| M8 | covers 数字分支退回裸 `True` | D 组语义校验 | 判红 |

★ 沿用 v1.23.25 的两条防呆：**SRC 换绝对路径**（否则畸形体因路径错冒充判红）；
**加载/执行抛错不算判红**（那只说明判据没跑）。""",
    """| # | 变异体 | 打在 | 期望 |
|---|---|---|---|
| M1 | `_bm25_pair` 换回 `_bm25_best` | B 组「无关对必须归零」（**BM25 方向**） | 判红 |
| M2 | Jaccard 分母换回 `min` | A 组分母来源（退回短句高估） | 判红 |
| M3 | 结构层短路返回 0.0 | L4 编号相等的短路 | 判红 |
| M4 | `_BM25_MIN_CORPUS` 降到 0 | B 组降级条件 | 判红 |
| M5 | BM25 归一化去掉 | B 组值域 | 判红 |
| M6 | `_DEDUP_SIM` 默认改 0.5 | C 组默认值 | 判红 |
| M7 | `merge` 忽略 `thr` 参数 | C 组「阈值接上了吗」 | 判红 |
| M8 | covers 数字分支退回裸 `True` | D 组语义校验 | 判红 |

★ 沿用 v1.23.25 的两条防呆：**SRC 换绝对路径**（否则畸形体因路径错冒充判红）；
**加载/执行抛错不算判红**（那只说明判据没跑）。

### 5.1 ★ 第一轮只判红 5/8 —— 「判绿的那三条」才是本轮的产出

| 未判红 | 症状 | 根因 | 处置 |
|---|---|---|---|
| **M1** | `_sim3` 阈值抬到 0.99 后**仍判绿** | `_sent_is_rephrase` 里 `_similar` / `_overlap_coef` 是宽尺子，几乎总在 sim3 之前命中 ⇒ sim3 那条线**行为上不可观测** | 判据先做「行为等价性实测」（8000 组零差异）确认调序不改语义，再把 sim3 提到首判 |
| **M3** | 结构层返回 0.0 后**仍判绿** | 判据样本用 `T3` vs `T3`，被 `_sim3` 开头的 `if a == b: return 1.0` 先短路 | 改样本为 `T3` vs `3`（**字符串不等、编号相同**）⇒ 变异后 1.000 → 0.000 |
| **M4** | 语料下限降 0 后**仍判绿** | 判据查询词用「测试」，**这词不在语料里** ⇒ 本就 0 分，判不出降级失效 | 查询词换成语料里真实存在的（「只有一个句子」）⇒ 变异后 0.0 → 0.277 |

**M1 的判绿又牵出一个真 bug（本版最有价值的发现）**：
把 sim3 提到首判后再看 M1，仍然判绿 ⇒ 顺藤查出 `_sim3` 的 BM25 通道实现是

    bm = (_bm25_best(a, corpus) + _bm25_best(b, corpus)) / 2

而 `_bm25_best(q, corpus)` = 「**q 对语料每篇**取最大」—— 它测的是 **q 与语料的相关性**，
**不是 a 与 b 的相似度**。后果：两条**各自与语料相关、但彼此毫不相干**的句子会被抬到
虚高分（实测 `a`/`b` 字面重叠 0.000，`sim3` 却有 **0.467**）。

修法 = 新增 `_bm25_pair(query, doc, corpus)`：**doc 当唯一文档、IDF 取整份语料**，
只累加**双方共有**的词 ⇒ 无关必为 0（实测 **0.467 → 0.000**），相关对保持
（0.746 → 0.717）。M1 随之改打这个点，**判红**。

★ 结论：**「全绿」的判据若没跑过变异体，等于没测**。这一轮 5/8 的读数
（而不是最终的 8/8）才是本轮质量的证据。""",
))

# ⑤ 符号清单补 _bm25_pair + 签名
EDITS.append((
    """**新增模块级函数**
- `_bm25_corpus(items) -> (doc_tfs, dfs, avgdl, N)`
- `_bm25_best(query, corpus) -> float`
- `_jaccard(a, b, top_n) -> float`
- `_sim3(a, b, corpus=None, top_n) -> float`
- `_sim3_pair(a, b, corpus=None, top_n) -> (float, dict)`""",
    """**新增模块级函数**
- `_bm25_corpus(items) -> (doc_tfs, dfs, avgdl, N)`
- `_bm25_best(query, corpus) -> float`（**q 对语料取最大** ⇒ 测「与语料的相关性」）
- `_bm25_pair(query, doc, corpus) -> float`（**两篇之间**的 BM25 ⇒ 测「a 与 b 的相似度」；
  step8 新增，修 M1 挖出的方向 bug）
- `_jaccard(a, b, top_n) -> float`
- `_sim3(a, b, corpus=None, top_n) -> float`
- `_sim3_pair(a, b, corpus=None, top_n) -> (float, dict)`

★ `_bm25_best` **不删**：它仍是「query 对语料检索」的正确工具（如 `_detect_ing_rephrase`
  之外可能的整批检索场景）；两个函数的语义分工已在 docstring 写明。""",
))

for old, new in EDITS:
    c = txt.count(old)
    assert c == 1, f"锚点命中 {c} 次：{old[:50]!r}"
    txt = txt.replace(old, new, 1)

out = txt.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt.encode("utf-8")
RP.write_bytes(out)
left = [k for k in ("__LINES__", "__BYTES__", "__SMOKE_OK__", "__MUT_OK__",
                    "__CRLF__", "__NEDITS__") if k in out.decode("utf-8")]
print("OK 报告已更新；残留占位符 =", left)
print("lines =", out.count(b"\n"), "bytes =", len(out))

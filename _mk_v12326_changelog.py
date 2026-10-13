# -*- coding: utf-8 -*-
"""v1.23.26 CHANGELOG 段（插在 v1.23.25 段之前）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"

b = CL.read_bytes()
assert b.count(b"\r\r\n") == 0
_is_crlf = b.count(b"\r\n") > 0
txt = b.decode("utf-8")
if _is_crlf:
    txt = txt.replace("\r\n", "\n")

SEG = """v1.23.26 相对 v1.23.25

【要解决的问题】上一轮对 14 圈真实产物做了「锚点重述 / 探针设计」的量化诊断
（`_分析_锚点重述与探针设计_v12325.md`），结论是：**机制骨架都对，坏的是尺子和接口**。
本版只做「尺子」那一半（**不动 LLM 接口** ⇒ 可零成本独立验证），共四处：

  ① `_overlap_coef` 对短句**系统性高估** —— 根因级。
     `_overlap_coef(a,b) = |A∩B| / min(|A|,|B|)`。min 分母是**有意**引入的
     （为了让「短句被长句整段包住」接近 1，那正是复述的形状），但它同时让
     **两条 3 词短语共享 1 个名词就得 0.5**。实测：
     `_overlap_coef("模型 部署", "模型 训练")` = **0.500**；
     而 `_similar(同对)` = **0**（因 `min(len)<=8` 走子串包含）。
     两把尺子在同一对上结论**完全相反**，而 `_overlap_coef` 被 **19 处**调用、
     跨禁词 / 未追踪 / 线头 / 复述四种语义场景 —— **一把尺子量五件事**。
  ② 池内去重阈值是**硬编码字面量**（`Pool.merge` 三处 0.9 + 一处 0.85），
     「参数按层可覆盖」这条红线在池内形同虚设 —— **一处都改不了**。
  ③ `probe_no_target_covered` 的**数字编号分支只查编号在范围内**，不校验语义：
     covers 乱指 `T1`（编号合法、语义完全无关）**实测不报红**（见本版负对照）。
  ④ BM25 缺失：`_kw` 是**平权词袋**（「模型」与「是」权重相同），无 IDF。

【改了哪几处】
  1. **新增 `_sim3` 三级尺子**（`_bm25_corpus` / `_bm25_best` / `_jaccard` / `_sim3`
     / `_sim3_pair`，模块级，接在 `_overlap_coef` 之后）。
     · L1 字面层 = **对称 Jaccard**（分母 = **并集**，不是 min ⇒ 消除短句虚高）；
     · L2 稀疏层 = **BM25**（纯 Python，`_BM25_K1=1.5` / `_BM25_B=0.75`），
       语料 = **本圈池内条目**，归一化 `raw/(raw+k1)` 压回 [0,1)；
     · L4 结构层 = 两侧都是 `T3` 式编号且相等 ⇒ 直接 `1.0`（符号必然命中，
       不受相似度尺子影响）；
     · **语料 < 4 篇自动关闭 BM25 通道**（小语料 IDF 不可靠）⇒ 退回纯 Jaccard，
       降级路径与主路径是**同一个函数**，读数可比；
     · **对称性**：`sim3(a,b) == sim3(b,a)`（冒烟逐位验证）。
     · 同一对实测 `_sim3("模型 部署","模型 训练")` = **0.333**（旧 0.500）。
  2. **复述检测切到 `_sim3`**：`_sent_is_rephrase(s, u, corpus=None)` 主判据换成
     `_sim3 >= _REPHRASE_SIM3`（新常量 0.62）。`_detect_ing_rephrase` 内部
     **只编一次语料**并传给每句判定 —— 否则 IDF 随调用次序变，
     同一对句子会给出不同的分（同一圈内必须同一把尺子）。
     ★ `_overlap_coef >= _REPHRASE_OVERLAP` 那一条**保留**：它管的是
     「s 的关键词几乎全在 u 里」这个**特定几何**，是 sim3 抓不到的一类；
     两条判据各管各的形状（docstring 已写明）。
  3. **池内去重阈值可配**：`Pool.merge` 加 `thr=` / `susp_thr=` 参数，
     默认取新常量 `_DEDUP_SIM=0.90` / `_DEDUP_SUSP_SIM=0.85`
     （= **原字面量逐位相同**）；调用点从 `self.config["sim"]` 读；
     `DEFAULT_CONFIG` 新增 `"sim"` 段。**不配置就与 v1.23.25 行为一致**。
  4. **covers 数字编号分支补语义校验**：编号在范围内**还要**
     `_similar(探针问题, 该未触及项, 0.70) or _overlap_coef(...) >= _COV_OVERLAP_MIN(0.50)`。
     比较对象是**探针的 question vs 该项**（不是两个 untouched 项互比 —— 那是
     清单内部一致性，不是覆盖）。非数字分支原本就有 `_similar`，未动。
  5. `dgtf_config.yaml`：头部版本 + 新增升级段 + 新增 `sim` 段（2 键）。

【不在本版范围（下一版）】`expected_gain` 取消自报改引擎算 EIG、子模批选、
`link` 反查、「空探针」判据双向化、`AspectUnit` 结构化、`BeliefItem` 四态机 ——
这些都要动 LLM 接口，需真跑验证，见设计报告 §4.2 的 v1.23.27 / v1.23.28。

【验收】
  · 冒烟 `smoke_test.py`：✓=__SMOKE_OK__ / ✗=0（exit 0）；新增 `check_v12326_sim3`
  · 变异体 `_mut_v12326.py`：**__MUT_OK__ / 8 判红 + 正对照判绿**
  · 负对照 `_nv_v12326_covers.py`：改前 A 案例（covers 乱指 T1）**不报红**，
    改后**报红**，B/C/D/E 全部正确 ⇒ 修的是语义校验，不是把判据改成一味报红
  · 配置同步：166 键 / **load_config 逐字差异 0 项**（新增 2 键已显式写入出厂 yaml）
  · 主文件 CRLF 自检：`CRLF=__CRLF__ / 裸 LF=0 / lone CR=0 / \\r\\r\\n=0`

★ v1.23.26 收束摘要
  交付物：`元DGTF-V1.23.26.py`（__LINES__ 行 / __BYTES__ bytes / 纯 CRLF；
  上一版 18593 行 / 896053 bytes）。
  改了哪几处：__NEDITS__ 处编辑（版本号 ×2 / `_sim3` 族 5 个新函数 / `_REPHRASE_SIM3`
  新常量 / `_sent_is_rephrase` 签名与判据 / `_detect_ing_rephrase` 编语料 /
  `_DEDUP_SIM`+`_DEDUP_SUSP_SIM` 新常量 / `Pool.merge` 签名与体内 4 处 /
  merge 调用点读配置 / `_COV_OVERLAP_MIN` 新常量 / covers 数字分支语义校验 /
  `DEFAULT_CONFIG.sim` 段）+ smoke 2 处同步 + 配置 2 处同步。
  验收数字：冒烟 __SMOKE_OK__✓/0✗；变异体 __MUT_OK__/8；负对照 5/5；
  配置 0 差异；CRLF 自检全 0。
  未做：**真跑（full run）** —— 本版改的是内部尺子与阈值来源，**喂进模型的内容
  一字未增**（`_sim3` 只在引擎侧算相似度，不进 prompt），故以零成本判据 + 变异体
  + 负对照替代真跑；如需真跑证据，留待下次 `--phase all` 时顺带看复述率读数变化。

"""

_a = "v1.23.25 相对 v1.23.24"
assert txt.count(_a) == 1, txt.count(_a)
txt = txt.replace(_a, SEG + _a, 1)

out = txt.replace("\n", "\r\n").encode("utf-8") if _is_crlf else txt.encode("utf-8")
CL.write_bytes(out)
print("OK CHANGELOG 已插入 v1.23.26 段（占位符待填）")
print("lines =", out.count(b"\n"), "bytes =", len(out))

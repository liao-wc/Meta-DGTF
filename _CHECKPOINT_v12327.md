# v1.23.27 续跑检查点（2026-10-13）

## 已完成（Step0 ~ Step7）

| Step | 内容 | 补丁脚本 | 主文件大小 |
|---|---|---|---|
| Step0 | 底座盘点（2 个 Explore 并行） | — | 906886 |
| Step1 | 复制出 v1.23.27 + 改版本号两处 | `_patch_v12327_step1.py` | 906886 |
| Step1b | smoke SRC 指新版 / yaml 头部版本 | `_patch_v12327_src.py` / `_patch_v12327_yaml_head.py` | — |
| Step2 | 基线探针 `_baseline_v12327.json` + 建 `_mut_v12327.py` 骨架解 H1 | — | — |
| Step3 | **A1** AspectUnit 结构化 + 双写（6 处替换） | `_patch_v12327_step3.py` | 910871 |
| Step4 | **A2** 覆盖对账符号化 + **A3** 双读数（4 处） | `_patch_v12327_step4.py` | 917880 |
| Step5 | **D1** BeliefItem 四态机 + **D2** 迁移规则（7 处） | `_patch_v12327_step5.py` | 928043 |
| Step5b | 清 Step3/4/5 自引入的 **16 处版次批注** | `_patch_v12327_step5b.py` | 928101 |
| Step6 | **D3** 语义熵（sim3 聚类，2 处） | `_patch_v12327_step6.py` | 932394 |
| Step7 | **E1** EIG 可计算化 + **E2** 子模批选（2 处） | `_patch_v12327_step7.py` | 940130 |
| Step8 | **E3** covers 双查 + **E4** link 反查 + **E5** 双向判据（5 处） | `_patch_v12327_step8.py` | ~946614 |
| Step8c | 修 E1 归一化「同尺」bug（见结论③） | `_patch_v12327_step8c.py` | ~947000 |
| Step8b | 修 **判据侧** order-dependent 假红（见结论⑤） | `_patch_v12327_step8b.py` | smoke_test.py 改 |
| Step9 | **E6** 自适应停止（常量 + 纯函数 + Pool 字段 + 四处留痕） | `_patch_v12327_step9.py` | 951701 |
| Step9c | 补接线：响应根级 `no_probe_reason` → view（E5 读了没人写） | `_patch_v12327_step9c.py` | 952571 |
| Step9d | 补 Step9 漏掉的四处 `stop_floor` 定义（`NameError`） | `_patch_v12327_step9d.py` | ~954000 |
| Step10 | 插 `check_v12327_five_mechanisms()` + 填满 **8 变异体** | `_patch_v12327_step10.py` / `_mut_v12327.py` | 主文件改 E1 |
| Step11 | 真跑（四层螺旋，~65min） | — | — |
| Step12a | `dgtf_config.yaml` 补 3 键（差异 0 项） | `_patch_v12327_step12a.py` | yaml |
| Step12b | `CHANGELOG.md` 加 v1.23.27 段 | `_patch_v12327_step12b.py` | CHANGELOG 30 段 |

### ★ 修 E1「命中整簇」bug（Step10 过程中发现）
`probe_information_gain` 原本「命中一条 ⇒ 只移除那一条」。当未决集合里
有**同簇**成员时（B1~B2 同簇、B3 独立），只移 B1 ⇒ {B2,B3} 不再同簇 ⇒
归一化后 **h_after > h_before** ⇒ G 被夹成 0。
修法：先算簇归属，命中 ⇒ 移除**整个同簇**。实测 `h_before=0.5794 /
h_after=0.6309`（修前 G=0）→ 修后 G>0。

## 关键实测结论

### ① Step5b：补丁自引入版次批注（本轮第 1 个真坑）
Step3/4/5 的注释里写了 `# [v1.23.27 A1] …` —— 触发 `check_v1236_no_version_tags()`：
- 15 行成块批注 + 1 处 docstring 前导标记（`add_aspect_unit` 的 docstring 以
  `[v1.23.27 A1]` 开头），行号 [1283,1292,3775,3780,3785,3880,4179,4199,4251,
  4343,4364,4389,4561,4567,5222] + 3829。
- **修法**：不是改判据、不是放宽阈值，是**改注释本身** —— 把版次标记换成
  不带版次的语义标签（`[A1 方面单元]` / `[D1 信念条目]` / `[A2 符号对账]` /
  `[A3 双读数]` / `[D1/D2 信念四态]` / `[D2 迁移规则]` / `[A2/A3 符号对账]`）。
  **保留设计理由，只剥标记**（不整行删 —— 注释里有「为什么双写」「为什么
  resolved 优先级最高」这类设计意图）。
- 复验：v1236 ✓（负对照 v1.23.5 判红 441 行）/ v1237 ✓（CHANGELOG 46 段）。

### ② `check_v12320_quiet_output()[⑤]` 是 **order-dependent 假红**（本轮第 2 个真坑）
**现象**：全套冒烟里它判红（`命中 0 次`），单独跑却 ✓。

**根因**：`inspect.getsource(mod.DGTF.dump_round)` 在跑到它之前
**已经被某个前置 check 弄失效**（`linecache` 缓存 / 模块替换副作用）⇒
`getsource` 抛异常被 `except Exception` 吞掉 ⇒ `bad.append(...)` 报
「命中 0 次」—— **报的原因是 `""` 里没有 `self.dump_rounds`，不是守卫没接线**。

**诊断证据**：
- 单跑 `check_v12320_quiet_output()` → `True` / `count self.dump_rounds = 2`
- 按 `main()` 顺序跑到它 → `False`，报 `[⑤] 命中 0 次`
- 最小复现：把 `inspect.getsource` 猴补丁成「异常时返回 `''`」→
  **单独跑也复现 True→False**。⇒ 完全确认是 `getsource` 失效，
  **不是主文件问题**（Step2 基线跑同样报这一条，与我的改动无关）。

**注意**：这条判据自带「反假绿」设计缺陷 —— `except Exception` 把
「取不到源码」和「源码里没有该串」**混成同一个 bad 项**，
读起来像「守卫没接线」，实际是「判据自己没拿到源码」。

### ③ Step7 实测发现 E1 的 G **恒为 0**（待修，Step8 处理）
实测三组：
```
unrelated G= 0.0 no_assignment
targeted  G= 0.0 hits=['B1'] h_before=1.0
submodular picked=2  trace=[{picked:极低温…, g:0.0, hits:[B1]},
                            {picked:如何提升…, g:0.0, hits:[]}, {stop:no_candidate_with_gain}]
```
**原因**：3 条两两不相关的未决主张 ⇒ `H_before = ln3/ln3 = 1.0`；
移除任一条后剩 2 条**仍两两不相关** ⇒ `H_after = ln2/ln2 = 1.0` ⇒
**G ≡ 0**。归一化到各自 ln(n) 让「移除一条」的熵降被归一化抵消掉了。

⇒ **真正的修法**：`E_a[H_after]` 必须用 **同一把尺子**（`H_before` 的
归一化基准 `ln(n_before)`），不能用「移除后集合自己的 ln(n_after)」。
否则「归一看不见移除的效应」—— 这正是我自己在 Step7 里写下的
「两臂对照前先证两臂都产出了这个量且是同一把尺子」，结果自己踩了。

### ④ Step2 基线跑了 15 分钟仍未收尾
`_smoke_v12327_step2.log` 跑到 397 行仍在 `check_v1234_runtime`（编号
不是顺序编号，实际是流程中段）。全套冒烟耗时远超预期，需耐心等。

### ⑤ Step8b：假红**不是** p2b 造成的（结论② 的更精确版本）
**新证据**（三个诊断脚本 `_diag_getsource2/3/4.py`）：
- 按 `main()` 顺序跑 **前 74 个 check**（p2b 之前）→ `getsource=41526` 稳定；
- **只跑 p2b**（新 import）→ `41526` 稳定，`p2b` 返回 True；
- 跑到 **p2b + 其后 8 个 check** → 仍 `41526` 稳定。
⇒ **p2b 无罪**。之前 `_diag_getsource.txt` 里 `LAST=p2b / 50 字符` 只是
「最后一个跑的就是它」，不是「它弄坏的」—— **相关不等于因果**。

**真正的修法（判据侧，不追凶手）**：两者都用 `except Exception` 把
「取不到源码」和「源码里没这个串」混成同一个 bad 项 —— 这是**方向错的
断言**。加共享 helper `_src_of(func)`：先 `inspect.getsource`，短于 200
字符就退回**读源文件 + ast 按 def 名切块**，两条路都失败才 raise，调用点
把「判据没取到源码」与「源码里没这个串」**分开报**。
⇒ 无论 `getsource` 何时失效，判据给出的是**真结论或诚实报错**，不再是
误导性的「死代码」。

### ⑥ Step9 设计要点（E6）
- **纯函数 `e6_stop_verdict(seen, max_gain, min_gain, stop_floor)`** ——
  判据与变异体的落点。返回 `(is_stop, reason)`。
- ★ `seen == 0` ⇒ **`(False, "no_candidate")`**，**不是停止**：
  「模型没给候选」≠「候选都推不动」。混为一谈会让「模型偷懒」被读成
  「池已收敛」。这正是 E5 双向判据的同一个思想。
- ★ 边界取**严格小于**：`max_gain == stop_floor` 不算停。
- ★ 与 `min_gain`（0.3）是**两把尺子**：那是「模型自报值不值得做」，
  `stop_floor` 是「还能不能降不确定度」。默认 0.02 刻意压低 ——
  停止是强动作，宁可多跑一圈。
- 落地四处（research / duel / meta / phase），**只留痕不改行为**：
  `pool.note_probe_stop()` 记 `{layer, seen, max_gain, stop_floor,
  stop, reason}` 进 `probe_stop_history`，`to_dict` **白名单出口**
  （空 Pool 不凭空出键）。

## 待办

- [x] Step8：E3 covers 双查 + E4 link 反查 + E5 双向判据
- [x] Step8b：修判据侧 order-dependent 假红（见结论⑤）
- [x] Step8c：修 E1 的「归一化同尺」bug（结论③）
- [x] Step9：E6 自适应停止规则（+9c 接线 / +9d stop_floor 定义）
- [x] Step10：同步冒烟判据 + 变异体（9/9 判红；全套 **0 ✗ / 220 ✓**）
- [x] Step12a：`dgtf_config.yaml` 补 3 键（差异 0 项）
- [x] Step12b：`CHANGELOG.md` 加 v1.23.27 段 + `★ v1.23.27 收束摘要`
- [x] **Step11：真跑 + 产物核对完成**
      `--phase all` / 199 calls / 2938969 tokens / 1h07m55s / **EXIT=0**
      产物核对（`_verify_v12327_artifacts.py`）：**无产物侧缺口**
- [ ] Step12d：记忆更新（已 append，待最终润色）
- [ ] Step12e：git 提交（**只圈本版文件，不含 `dgtf_app/*`**）
- [ ] 挂账：`dgtf_app` 侧 `sim.dedup` / `sim.dedup_susp` 未进 `_KEY_CN`
- [ ] 下版候选：探针 `gain_source` 标记未落盘（`expected_gain` 数值已落盘）

### ⑦ Step11 真跑期间查清的两处（详见 `v12327_报告.md` §3.2）

- **E6 停止路径真跑 0 次触发**：四处记录点都在 `if not out:` 分支，
  真跑每层都产出了探针 ⇒ 不进分支。**设计正确，但是覆盖边界**。
  ⇒ 补源码层语义判据（四点各自往回 160 字符内有 `if not out:`）
  + `M9` 变异体（`if not out:` → `if True:`）判红背书。
  ⇒ **9/9 判红**。
- **`aspect_units` 无 `to_dict` 出口**：不影响运行（消费方同进程读内存），
  但产物里查不到 `A{n}`，审计链路弱。**本版不动，列下版候选**。
- **假疑点澄清**：日志 `^  A[0-9]\.` = 0 不是未接线 ——
  `--show-view` 默认 off，`shape_of` 三个调用点全是**喂 LLM 的提示词**。

### ⑧ `check_v12315` 假红：判据自己污染读数来源（已修，见报告 §3.3）

- 症状：全套冒烟报「上限放大后样本数没增加（62 → 33）」等两条红。
- 根因**两个独立原因叠加**：① 判据自己往 `outputs/` 写夹具目录，
  而它读的「历史语料」**也是** `outputs/` —— 被测物与读数源同一个活目录；
  ② 并行线 `dgtf_app/selftest.py` 同时在增删 `outputs/` 里的文件
  （日志有 `WinError 2` 直接证据）。
- 隔离验证（`_diag_v12315_race.py`）：活目录读到 n=425 / tri_n=295
  （不稳），**冻结快照稳定 n=303 / tri_n=195**（连跑两次逐位相同）。
- 修法：三处读数改**冻结快照**（`mkdtemp` + `copy2` 保 mtime）+ 尾部清理。
  **阈值一字未改** —— 修的是读数来源，不是判据松紧。
- 判别力背书 `_mut_v12315_snapshot.py`：`_lim` ×999 的变异体
  ⇒ `fact 20→164` / `nonfact 20→228` ⇒ **判红 1/1**。



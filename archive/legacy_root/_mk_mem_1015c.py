# -*- coding: utf-8 -*-
"""追加 2026-10-15 记忆：EML 学习面扩面 + 真跑逮到的缺陷 + 两处事故。"""
import io, os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".workbuddy", "memory", "2026-10-15.md")
ADD = u"""
---

## 六、★ 「所有可配置行为纳入自我学习 + 与调度融合」（用户指令）

### 先调研再动手（三条事实决定可行性）
| 事实 | 出处 |
|---|---|
| `DGTF(entry, self.llm, self.config)` —— **共用同一个 config dict** | 实测 6 处 |
| 动作开关**唯一读入口** = `_action_on(config, name, default)` | `def _action_on` |
| 思考档**唯一读入口** = `LLM.call` 的 `th = self.thinking_stages.get(stage)` | L8805 |

⇒ **只要在这两个入口加「运行时覆盖」，全部相关行为立刻可运行时调**
—— 而「可运行时调」正是「**能被 EML 学**」的前提。

### 四件事
1. `_action_on` 加运行时覆盖（**运行时 > actions 段 > output 别名 > 默认**）；
2. `MetaDGTF.run` 把 `self._control` 挂进 `config["_control"]`
   （★ 只加**下划线键**：不进产物、不落盘、不算配置项）；
3. 控制面白名单扩到 `actions.` / `thinking.` / `stop.` / `duty.`（各自带边界）；
4. EML 新增两个 key（**都接真实消费方**）：
   · **`thinking_hint`**（三态一致率 < 33%）⇒ `thinking.<stage>` + **同步写
     `llm.thinking_stages`**（消费方 = `LLM.call` 的思考档查表）；
   · **`action_hint`**（成本 > p75 且职责未升）⇒ `actions.<名>`（消费方 =
     `_action_on` 经第 1 条）。

实测对账：**生成侧 6 类 ↔ 应用侧 7 分支 ↔ 豁免 []**。

### ★★ 判据升级：功能性断言是唯一防线
`M73`（`action_hint` 写白名单外 ⇒ 控制面拒 ⇒ **新的学了不做**）与
`M74`（`thinking_hint` 不同步 ⇒ **消费方读不到**）**都不会让源码级判据变红** ——
**只有「真喂一条候选、再看消费方有没有变」才抓得到**。
⇒ 判据补两条功能性断言（喂 `thinking_hint` 看 `llm.thinking_stages`；
喂 `action_hint` 看控制面 `applied`）。**两条都判红** ⇒ 防线有效。

---

## 七、★★ 真跑逮到的**真缺陷**（用户口径「真跑还能发现新问题」的实例）

**现象**：`_fullrun_V1236FULL`（11 项全开）的 `quant.json` 里**四层都只有 3 个读数**
（缺 `yin_yang_divergence`），而上一次 `V1234FULL` 是**四层四读数齐（16 条）**。

**根因**（读码确认）：
```
_expand_pair: merge_expand 开且恰好两臂 ⇒ _expand_pair_merged_once ⇒ **提前 return**
              ⇒ 下面那句 `self._quant_pending_yy = _yy` **永不执行**
run:          `if _yy:` 取到 None ⇒ **不写读数**
```
⇒ 合并路径**既没算分歧、也没记「本路径不适用」** ⇒ 产物里
「**本层没有分歧读数**」与「**分歧读数为空**」**分不开**。

**修法**（照**既有语义**，不另造一套）：`yin_yang_divergence()` 的 docstring 就写着
「任一侧为空 ⇒ `divergence=None` 且 `verdict=""`（不表态）」⇒ 合并路径按同一口径
**显式记一档**（`merged=True` + `verdict=""` + why）。
**变异体 M72** 复现该缺陷并判红。

★ **这是「上一轮的降本开关」引入的缺陷**，**判据与冒烟都没抓到**，
靠**真跑产物对比**才暴露 —— 正是用户要的那种检查。

---

## 八、两处工程事故（都已修）

1. **排序脚本把注释归给了前一个条目**：`("Mn ` 之前的连续注释是**这一条**的说明，
   而我的切块把它们留在上一块尾部 ⇒ **注释错位**（M56 的注释跑到 M55 下面）。
   内容没丢（只是归属乱）⇒ **从 git 恢复 + 修脚本 + append 重加**。
2. **第四次「插入位置 ≠ 编号」**：新变异体仍被插在 M56 前 ⇒ `--only` 跑错靶子。
   ⇒ 写 `_mk_v12336_mutsort.py`（**按编号排序**，并输出「非升序对」自检）+
   修好注释归属。**从此文件自己保持有序**。

---

## 九、验收与任务全景

| 项 | 结果 |
|---|---|
| 主文件 | **25572 行 / 纯 CRLF / AST OK** |
| 冒烟 | **228 ✓ / 0 ✗ / EXIT=0** |
| `--phase all` | **PASS 319 / FAIL 0**（EXIT=0） |
| 变异体 | **M72~M75 判红**；共 **75** 条 |

**在办任务**（★ 不只当前这条线）：
| 任务 | 状态 |
|---|---|
| EML 学习面扩展 | ✅ 本轮完成 |
| 联网按需协议（`===WEB-NEED===`） | ⏳ 设计已有（`_方案_v12335` §三.1） |
| 圈级心跳（需跨圈状态） | ⏳ 设计已有（报告 §八） |
| 挂账 #2 等待型 | ⏳ 只配判据 |
| 挂账 #3 留痕不删 | ✅ 保持 |

**下一步（用户指定顺序）**：变异体全量（进行中）→ **全部测试完成后最后跑一次真跑**
→ **确认没问题才存档**。
"""


def main():
    raw = io.open(P, "rb").read()
    assert raw.count(b"\r\n") == 0, "记忆应为 LF-only"
    s = raw.decode("utf-8")
    if "所有可配置行为纳入自我学习" in s:
        print("已存在该节"); return
    s = s.rstrip("\n") + "\n" + ADD
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK 记忆已追加；行数 %d" % s.count("\n"))


main()

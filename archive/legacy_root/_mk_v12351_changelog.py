# -*- coding: utf-8 -*-
"""往 CHANGELOG.md 插 v1.23.51 段（最新在最前）。纯 CRLF 往返。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "CHANGELOG.md"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")

SEC = """v1.23.51 相对 v1.23.50

【主题】`_eml_finish` 幂等：**一个跑次只学一条 episode**。

【问题】A/B 真跑把 `_eml_finish` 调了两次（`run()` 内部已经调过一次）——于是每个
  跑次写出**两条完全相同**的 `episode`、`used_outcomes` 与 `weight` 被罚两遍
  （实测 7 个条目 weight 多扣 0.05/次，事后要靠清账脚本收拾）。
  为什么上一版没暴露：**「`run_id` 必须在 `_eml_finish` 之前盖章」是 v1.23.50 才修的**
  —— 在那之前内部那次拿到空 id，被「匿名跑次一律不写库」的闸挡掉，于是调用方那次
  看起来"正常"。**修好一个锁，会让原本被它挡住的 bug 显形。**

【修法】
  · `_eml_finish` 在**拿到跨进程锁之后、写 episode 之前**加守卫：已有**同 `run_id`
    且除 `t` 外逐字相同**的 `episode` ⇒ 直接返回（`dup_skipped`），不写库、不再罚 weight。
  · 判据用「读数逐字相同」而不是只看 `run_id`：墙钟预算 `paused` 的跑次也会写一条
    **半程样本**，续跑完成时读数不同 ⇒ **必须能写**，否则完整样本永远进不了库。
  · `_fullrun_V1250AB.py` 的双调用改成**条件补调**（只有真的没有 `playbook` 块、
    或那块是异常兜底时才补）。引擎守卫不能替代这一处：守卫返回的是 `dup_skipped`
    留痕，拿它覆盖产物会把学习块降级成空壳。
  · **无新配置键**；单次调用行为逐字不变。

【数据清账（独立提交）】`_fix_eml_dup_20261016.py` 把已脏的记忆库摘干净：
  `episodes` 99→97 行、`nogoods` 21→19 行、7 个条目 `weight` 按逆运算补回
  （L0001 `.30` / L0003 `.35` / L0004 `.50` / L0006 `.75` / L0007 `.75` /
  L0008 `.40` / L0009 `.75`）；`MEMORY.md` 不动（`t_used` 按 `run_id` 去重，
  证据数本来就是对的）。

---

★ v1.23.51 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.51.py`（26530 行 / 纯 CRLF）+ 冒烟新判据
`check_v12351_eml_once_per_run` + 变异体 M102 + 清账脚本 + 本段。

**改了什么**：`_eml_finish` 幂等守卫（锁内、写前，按「同 `run_id` + 读数指纹」判重）；
A/B 脚本改条件补调；记忆库清账。4 个改动块 / 删 2 行 / 增 34 行。

**验收**：冒烟 248 ✓ / 0 ✗（含新判据）；`--phase all` PASS 321 / FAIL 0；
AUDIT 69/0；变异体 100/100（M102 判红 = 判据有牙）；app 自检 368/0；
两版 `load_config` 逐字相同（无新键）。**不跑真跑** —— 判据是「哪条通道会经过这行代码」，
答案是**只有重复调用才经过**，而重复调用正是要消灭的行为。

**未做**：并行模式续跑；`paused` 不写 EML；记忆库目录解析归一；下一轮 A/B
（须冻结 bandit + 同口径比 S）。

"""

ANCHOR = "v1.23.50 相对 v1.23.49\n"
assert s.count(ANCHOR) == 1, "锚点命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, SEC + ANCHOR)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("CHANGELOG.md：%d → %d 行（插入 v1.23.51 段）" % (n0, s.count("\n")))

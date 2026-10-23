# -*- coding: utf-8 -*-
"""往 CHANGELOG.md 插 v1.23.53 段（最新在最前）。纯 CRLF 往返。"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "CHANGELOG.md"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")

SEC = """v1.23.53 相对 v1.23.52

【主题】记忆库目录**一处解析**：`bandit` 不再偷偷写回仓库。

【问题（挂账「目录两处解析未收敛」）】记忆库的落点在**两个地方**解析：
  · episode / playbook → `playbook.dir`（空则 `eml_dir()`）
  · bandit → `auto.bandit.dir`（空则 `eml_dir()`，**恒指仓库**）
  ⇒ 任何设了 `playbook.dir` 的调用方（冒烟、A/B 脚本、想隔离库的人）都会让
  **bandit 偷偷写进生产 `dgtf_memory/`**。冒烟隔离因此要三个旋钮
  （`output.save_dir` + `playbook.dir` + `auto.bandit.dir`）—— **漏一个就污染**，
  这类「漏一格」的事故本项目已经栽过（一次冒烟的跑次把真实条目的证据数抬高）。

【修法】
  · 新增唯一解析 `eml_store_dir(cfg)`，三处都走它：
    `auto.bandit.dir`（显式，**仍优先**） ＞ `playbook.dir` ＞ 仓库根 `dgtf_memory/`。
  · 为什么是**模块级函数**而不是实例方法：bandit 的**载入**发生在实例属性
    `_eml_cfg` 赋值**之前**，用实例状态会静默回落到 `eml_dir()` —— 那正是要修的
    bug 本身。读 `self.config` 没有这个顺序问题。
  · `_load_bandit` / `_save_bandit` 各加一个 `fallback` 形参（默认 None ⇒ 旧行为）。
  · **无新配置键**；生产默认（`playbook.dir` 空）解析结果与旧版**逐字相同**。

---

★ v1.23.53 收束摘要
────────────────────────────────────────────────────────────

**交付物**：`元DGTF-V1.23.53.py`（26567 行 / 纯 CRLF）+ 冒烟新判据
`check_v12353_eml_dir_single` + 变异体 M104 + 本段。

**改了什么**：新增 `eml_store_dir()`（唯一解析）；`_load_bandit` / `_save_bandit`
加 `fallback`；三处调用点统一；版本号两处。10 个改动块 / 删 9 行 / 增 30 行；
AST 登记 +1 个符号（588）。

**验收**：冒烟 252 ✓ / 0 ✗（含新判据）；`--phase all` PASS 319 / FAIL 0；
AUDIT 69/0；变异体 102/102（M104 判红 = 判据有牙）；app 自检 368/0；
两版 `load_config` 逐字相同。**不跑真跑**：默认路径解析结果不变，能力由
「真入口：`playbook.dir` 里种的 bandit 能被读到、写也只写那儿」证明；
另有**旧版对照**（同 cfg 跑 v1.23.52 ⇒ 仍写 `eml_dir()`）。

**未做**：并行模式续跑（★ 查清了：`max_minutes` 只挂在 `_run_serial` 上 ⇒
并行模式**根本不会暂停**，所以并行续跑只服务「被强杀」；要做得重做并行调度器的
半程状态，风险最高、收益最低，等真有并行跑次再说）；下一轮 A/B（须冻结 bandit
+ 同口径比 S）。

"""

ANCHOR = "v1.23.52 相对 v1.23.51\n"
assert s.count(ANCHOR) == 1, "锚点命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, SEC + ANCHOR)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("CHANGELOG.md：%d → %d 行（插入 v1.23.53 段）" % (n0, s.count("\n")))

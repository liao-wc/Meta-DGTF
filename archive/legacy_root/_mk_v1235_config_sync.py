# -*- coding: utf-8 -*-
"""v1.23.5 出厂配置同步。

本版**没有新增 DEFAULT_CONFIG 键** ⇒ 不需要补漏键，同步只剩两件事：
  1. 头部版本 → v1.23.5（冒烟 C3 会核「yaml 头 == __version__」）。
  2. 补一段【v1.23.4 → v1.23.5】升级说明（最新在最前）。

验收：load_config(改前 yaml) 与 load_config(改后 yaml) **逐字差异 0 项**
      （值不动 = 行为不动）。yaml 是纯 CRLF，走 read_bytes/write_bytes。
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v1235"
MAIN = HERE / "元DGTF-V1.23.5.py"

if not BAK.exists():
    BAK.write_bytes(YAML.read_bytes())


def read_lf(p):
    b = p.read_bytes()
    s = b.decode("utf-8")
    assert b.count(b"\r\r\n") == 0
    assert s.count("\r\n") == s.count("\n"), "%s 非纯 CRLF" % p.name
    return s.replace("\r\n", "\n")


def write_crlf(p, s):
    assert "\r" not in s
    b = s.replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0
    p.write_bytes(b)
    chk = p.read_bytes()
    assert chk.count(b"\r\n") == chk.count(b"\n")
    assert chk.count(b"\r\r\n") == 0


def rep1(s, old, new, tag):
    n = s.count(old)
    assert n == 1, "%s：命中 %d 次" % (tag, n)
    return s.replace(old, new)


s = read_lf(YAML)

# ---- 1) 头部版本 ----
if "# 元 DGTF · v1.23.4 配置文件" in s:
    s = rep1(s, "# 元 DGTF · v1.23.4 配置文件",
             "# 元 DGTF · v1.23.5 配置文件", "头部版本")
else:
    print("  [skip] 头部版本已同步")

# ---- 2) 升级段 ----
UPGRADE = """# 【v1.23.4 → v1.23.5】清挂账：调度归一化收口 + 布尔兼容可观测化
#   ★ **本版不改任何配置键、不改任何默认值** ⇒ 升级后行为**逐字不变**。
#     改的是引擎内部：把「同一套调度规则写了三份」收口成唯一实现。
#   ① pending_fix #1（已收口）自动调度的归一化规则：
#      原在 `_decide_parallel_mode` / `plan_resources` / `auto_plan`
#      三处各写一份（模式白名单 3 处、confidence 解析 3 处、圈数归一化
#      2 处）。现在抽成 `_plan_conf` / `_normalize_plan_mode` /
#      `_normalize_plan_rounds` 三个唯一实现，三处各留一行调用。
#      ★ 对你的影响：**无**（改前/改后同一支探针 16 组输入逐字相同）。
#      ★ 唯一可观测变化：模型返回非数字 confidence 不再抛 ValueError，
#        而是按 0.0 处理（保守方向 ⇒ 退 serial）。
#   ② pending_fix #3（可观测化）`external_anchor.as_evidence`：
#      布尔写法 `true` / `false`（v1.21.75 的旧写法）**仍然认**，
#      但走一次会在日志里留一条 warning，提示迁到五档字符串
#      （off / record / crosscheck / evidence / gate）。
#      ★ 本版**不删**兼容分支 —— 删了会让外部配置静默降级（true 不在
#        五档里 ⇒ 落 off，「作证据」变「关闭」且无任何提示）。
#        等留痕确认没人走再删。
#      ★ 本文件与引擎默认值两处**都已经是字符串档**，无需改动。
#   ③ pending_fix #2（未动）单票三态判决 `_adjudicate_sub_tristate`
#      整段保留作退路，等多票稳定若干批后再评估归档。本版只给它配了
#      判据，代码未动。
#   ★ 登记表随之更新：`docs/机制审计-v122.md` 的 pending_fix 从 3 项
#     变 2 项（#1 移入 ## resolved），产物头部也会印「pending_fix 2 项」。
#
"""

_ANCHOR = "# 【v1.23.3 → v1.23.4】新增**运行期三项总控**（联网 / 思考 / 强度）"
if "【v1.23.4 → v1.23.5】" not in s:
    s = rep1(s, _ANCHOR, UPGRADE + _ANCHOR, "插入升级段")
else:
    print("  [skip] 升级段已存在")

write_crlf(YAML, s)
print("配置同步完成")

# ---- 验收：load_config 逐字差异 ----
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("dgtf_v1235", str(MAIN))
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_v1235"] = m
spec.loader.exec_module(m)

a = m.load_config(str(BAK))
b = m.load_config(str(YAML))
da = json.dumps(a, sort_keys=True, ensure_ascii=False, default=str)
db = json.dumps(b, sort_keys=True, ensure_ascii=False, default=str)
print("  [验收] load_config 前后逐字相同：%s（差异 %d 项）"
      % (da == db, 0 if da == db else -1))
if da != db:
    import difflib
    for line in list(difflib.unified_diff(da.split(","), db.split(","),
                                          lineterm=""))[:20]:
        print("     ", line)

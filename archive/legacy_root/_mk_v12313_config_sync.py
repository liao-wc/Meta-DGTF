# -*- coding: utf-8 -*-
"""v1.23.13：配置文件同步（头部版本 + 新增 `auto` 段 + 升级段）。

★ 本版**新增 3 个配置键**（`auto.enabled` / `auto.allow_route_trim` /
  `auto.history_limit`），所以 `load_config` 差异不再是 0，而是**恰好这 3 项**——
  验收口径随之改成「差异 == 新增键集合，且逐字等于出厂默认值」。
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v12313"
MAIN = HERE / "元DGTF-V1.23.13.py"

raw = YML.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
if not BAK.exists():
    BAK.write_bytes(raw)
    print("回滚点：", BAK.name)
s = raw.decode("utf-8").replace("\r\n", "\n")

OLD = "# 元 DGTF · v1.23.12 配置文件"
assert s.count(OLD) == 1, "头部版本命中 %d 次" % s.count(OLD)
s = s.replace(OLD, "# 元 DGTF · v1.23.13 配置文件", 1)

AUTO_SEC = """# ============================================================
# 统一自适应调度器（v1.23.13）—— 十二项逐项可单独接管
#   优先级：命令行显式 ＞ 本配置（**改过**才认）＞ auto ＞ 出厂默认
# ------------------------------------------------------------------
# enabled：总开关。true（出厂）= auto 按题型/成本/历史接管十二项；
#   false ⇒ 全项退回「配置 / 默认」，行为回到 v1.23.12（**可回退**）。
# allow_route_trim：false ⇒ auto 永不砍层（层集合恒为 0,1,both,all）。
# history_limit：调度器扫多少份 `outputs/*.packed.json` 做历史读数
#   （成本中位 / 被截断率 / 各层实际停圈 / 联网命中与失败 / 取向错配）。
# ★ 想固定某一项：命令行显式传（`--route/--profile/--parallel/--rounds/
#   --orientation/--landing/--decidability/--web/--thinking/--effort`），
#   或改这里对应的键（如 `spiral.round_stall_limit` / `web_search.quota`）。
#   产物头部「自动调度」表会逐项写出**取值 / 来源 / 理由**。
# ============================================================
auto:
  enabled: true
  allow_route_trim: true
  history_limit: 20

"""
ANCHOR = "# 【v1.23.11 → v1.23.12】外部锚点拆成两条通道分别写明（文本 / 联网）"
assert s.count(ANCHOR) == 1, "升级段锚点命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, AUTO_SEC + ANCHOR, 1)

UP = """# 【v1.23.12 → v1.23.13】十二项收进一个统一自适应调度器
#   ★ **本版新增 3 个键**（`auto.*`，出厂见上方；另有一个可回退总开关）。
#   之前「自动」散在 8 处，读者无从知道「这一次是谁定了 route / 圈数 / 联网」。
#   现在十二项 —— 层集合 / 成本档 / 并行模式 / 圈数 / 取向路由 / 联网 /
#   思考 / 强度 / 停止阈值 / 联网降级 / 可判定性判定 / 落地层模板 ——
#   每项按 `显式 ＞ 配置 ＞ auto ＞ 默认` 独立取值，逐项留痕（产物头部有表）。
#   auto 的输入是**题型特征 + 成本质量意图 + 历史读数**（零 LLM）。
#   ★ 行为变化（如实说明）：不给命令行时，十二项默认由 auto 接管。
#     例：事实型短题会走 economy / serial / 联网开 / 思考关 / 落地层 boundary。
#     要回到 v1.23.12 的「按配置来」：`auto.enabled: false`。
#   ★ 技术债已清：`auto_plan()` 两条路径经**唯一装配器** `_assemble_plan`
#     输出同一 schema（此前单调用路径缺 route / cost_profile / max_calls）；
#     取向归一化合并成唯一实现 `_normalize_orientation`（原三份）。
#   ★ 判据：`check_v12313_auto_dispatch`（十二项 + 逐项独立 + 总开关 +
#     历史自适应 5 正 3 负 + 唯一实现与两路同 schema + 产物表）+ 7 个变异体。
#
"""
ANCHOR2 = "# 【v1.23.10 → v1.23.11】把「如实记账」里剩下的两条做完"
assert s.count(ANCHOR2) == 1, "升级段 2 锚点命中 %d 次" % s.count(ANCHOR2)
s = s.replace(ANCHOR2, UP + ANCHOR2, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
YML.write_bytes(out)
ytxt = out.decode("utf-8")

spec = importlib.util.spec_from_file_location("cfgsync13", MAIN)
m = importlib.util.module_from_spec(spec)
sys.modules["cfgsync13"] = m
spec.loader.exec_module(m)


def flat(d, pre=""):
    o = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict):
            o.update(flat(v, pre + k + "."))
        else:
            o[pre + k] = v
    return o


a, b = flat(m.load_config(str(BAK))), flat(m.load_config(str(YML)))
diff = {k: (a.get(k, "<缺>"), b[k]) for k in set(a) | set(b) if a.get(k) != b.get(k)}
# ★ 验收口径（本版**新增键**，与「无新键」版不同）：
#   `load_config` 会把 yaml 叠到 DEFAULT_CONFIG 上 ⇒ 新键靠 DEFAULT_CONFIG
#   补齐，两版 load 结果**本来就相等**。所以本版的判据是三条：
#     ① 逐字差异为 ∅（yaml 没有引入任何**非默认**覆盖）；
#     ② yaml 文本层面真的写出了 `auto.*` 三键（人能看见、能改）；
#     ③ yaml 覆盖 DEFAULT_CONFIG 的全部键（漏一个就是「写了但没生效」）。
_keys_auto = [k for k in ("enabled", "allow_route_trim", "history_limit")
              if ("  " + k + ":") in ytxt]
_missing = sorted(k for k in flat(m.DEFAULT_CONFIG) if k not in b)
print("load_config 键数：改前 %d / 改后 %d" % (len(a), len(b)))
print("① 逐字差异项：", sorted(diff) or "无")
print("② yaml 里写出的 auto 键：", _keys_auto)
print("③ yaml 缺 DEFAULT_CONFIG 键：", _missing or "无")
_ok = (not diff) and len(_keys_auto) == 3 and not _missing
print("验收：", "PASS" if _ok else "FAIL")
sys.exit(0 if _ok else 1)

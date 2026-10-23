# -*- coding: utf-8 -*-
"""v1.23.14：配置文件同步（头部版本 + auto 段三个键 + 升级段）。"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v12314"
MAIN = HERE / "元DGTF-V1.23.14.py"

raw = YML.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
if not BAK.exists():
    BAK.write_bytes(raw)
    print("回滚点：", BAK.name)
s = raw.decode("utf-8").replace("\r\n", "\n")

# ① 头部版本（幂等：已经是就不改）
OLD = "# 元 DGTF · v1.23.13 配置文件"
NEW = "# 元 DGTF · v1.23.14 配置文件"
if OLD in s:
    assert s.count(OLD) == 1
    s = s.replace(OLD, NEW, 1)
    print("头部版本已升级")
else:
    assert NEW in s, "头部版本既不是 13 也不是 14"
    print("头部版本已是 v1.23.14（跳过）")

# ② auto 段补两个新键 + history_limit 改 200
OLD2 = """auto:
  enabled: true
  allow_route_trim: true
  history_limit: 20
"""
NEW2 = """auto:
  enabled: true
  allow_route_trim: true
  # 语料实测：outputs/ 里有 368 份产物 md + 16 条跑批记录；默认只扫 20 份
  # 等于把历史样本丢了 95%。200 够覆盖现有语料（实测扫描耗时 ~0.16s）。
  history_limit: 200
  # 历史取样源开关：
  #   history_md    —— 扫产物 md 的头部行（只读前 8KB，覆盖最广）
  #   history_batch —— 扫仓库根的 *_runs.json 跑批记录（富字段、样本少）
  # 关掉任一项都会显著减少样本（判据里有负对照守着这一点）。
  history_md: true
  history_batch: true
"""
if OLD2 in s:
    assert s.count(OLD2) == 1
    s = s.replace(OLD2, NEW2, 1)
    print("auto 段已升级（200 + 两个源开关）")
else:
    assert "history_md: true" in s, "auto 段既不是旧版也没有新键"
    print("auto 段已是新版（跳过）")

# ③ 升级段
UP = """# 【v1.23.13 → v1.23.14】用**真实历史语料**校准自适应调度
#   ★ 新增 2 个键（`auto.history_md` / `auto.history_batch`）；
#     `auto.history_limit` 默认 20 → **200**。
#   ① 修一个**静默 bug**：`_auto_history` 把「实际停圈」的字段名读成了
#      `rounds`，真实字段是 `rounds_run` ⇒ `dict.get` 返回 None，
#      「实际停圈」**永远取不到**。产物里也没有任何渲染点写它。
#   ② 历史取样从「只扫 packed」（全仓只有 1 份）扩到**三类来源**：
#      packed 全量 / 产物 md 头部 / 跑批 JSON ⇒ 实测样本 1 → **217 份**。
#   ③ 读数扩到分位（token/calls 的 p50/p75）+ 按题型分桶
#      （事实型 79 / 决策型 132），策略变成「同类题比同类题」。
#   ④ 阈值从「拍脑袋」换成**实测**：
#      · 成本档降档改用**相对判据**（同类成本中位 ≥ 全语料 p75 才降），
#        不再写死「40 万 token」；实测 tokens_p75 = 711,161、calls_p75 = 135。
#      · 圈数改三级回退（实际停圈 → 种子上限 → 按层实测默认），
#        并按样本数决定信不信（实际停圈需 ≥3 份样本，防单条噪声）。
#        实测种子上限 p50：修行 3 / 研究 3 / 对撞 5 / 元 6。
#      · 被截断率实测 0.33（但只有 6 层样本）、三态一致率实测 n=1、
#        联网失败 0 条 / 空结果 0 次 ⇒ 这三条规则**当前无数据支撑**，
#        保留但如实标注，不作为「已校准」。
#   ⑤ 产物新增「**实际停圈**」一行（`rounds_run` + `rounds_cap`）——
#      此前这条信号既没被读也没被记，本版把它落进产物，语料才积累得起来。
#   ★ 对你的影响：**无需改配置**。但若你的 `outputs/` 很大，首次调度会多花
#     ~0.2 秒扫历史（只读每个 md 的前 8KB）。想关掉扩源：
#     `auto.history_md: false` / `auto.history_batch: false`。
#   ★ 判据：`check_v12314_history_corpus`（三源/字段名/分桶/门槛/相对判据/
#      落产物，含 6 组负对照）+ 7 个变异体。
#
"""
ANCHOR = "# 【v1.23.12 → v1.23.13】十二项收进一个统一自适应调度器"
assert s.count(ANCHOR) == 1, "升级段锚点命中 %d 次" % s.count(ANCHOR)
s = s.replace(ANCHOR, UP + ANCHOR, 1)

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
YML.write_bytes(out)
ytxt = out.decode("utf-8")

spec = importlib.util.spec_from_file_location("cfgsync14", MAIN)
m = importlib.util.module_from_spec(spec)
sys.modules["cfgsync14"] = m
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
diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
_keys = [k for k in ("enabled", "allow_route_trim", "history_limit",
                     "history_md", "history_batch")
         if ("  " + k + ":") in ytxt]
_missing = sorted(k for k in flat(m.DEFAULT_CONFIG) if k not in b)
print("load_config 键数：%d / %d | 逐字差异项：%s"
      % (len(a), len(b), sorted(diff) or "无"))
print("yaml 里写出的 auto 键：", _keys)
print("yaml 缺 DEFAULT_CONFIG 键：", _missing or "无")
# ★ 本版**改了默认值**（history_limit 20→200），所以差异不再要求为空，
#   而是要求「差异恰好是本版有意改的那一项，且旧值 20 / 新值 200」。
_expect = {"auto.history_limit"}
_ok = (diff == _expect and a.get("auto.history_limit") == 20
       and b.get("auto.history_limit") == 200
       and len(_keys) == 5 and not _missing)
print("差异 == %s 且 20→200：%s" % (sorted(_expect),
                                a.get("auto.history_limit") == 20
                                and b.get("auto.history_limit") == 200))
print("验收：", "PASS" if _ok else "FAIL")
sys.exit(0 if _ok else 1)

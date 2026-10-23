# -*- coding: utf-8 -*-
"""v1.23.15：配置文件同步（头部版本 + `auto.history_halflife_days` + 升级段）。"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YML = HERE / "dgtf_config.yaml"
BAK = HERE / "_bak_dgtf_config.pre_v12315"
MAIN = HERE / "元DGTF-V1.23.15.py"

raw = YML.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
if not BAK.exists():
    BAK.write_bytes(raw)
    print("回滚点：", BAK.name)
s = raw.decode("utf-8").replace("\r\n", "\n")

OLDV = "# 元 DGTF · v1.23.14 配置文件"
NEWV = "# 元 DGTF · v1.23.15 配置文件"
if OLDV in s:
    assert s.count(OLDV) == 1
    s = s.replace(OLDV, NEWV, 1)
    print("头部版本已升级")
else:
    assert NEWV in s
    print("头部版本已是 v1.23.15（跳过）")

OLD2 = """  history_md: true
  history_batch: true
"""
NEW2 = """  history_md: true
  history_batch: true
  # 历史读数的**时间衰减半衰期**（天）。0 = 不衰减（等权）。
  # 语料跨十几天，旧样本是旧配置下的读数；不加权会把新读数拉向旧行为。
  history_halflife_days: 14
"""
if OLD2 in s:
    assert s.count(OLD2) == 1
    s = s.replace(OLD2, NEW2, 1)
    print("auto 段已补 history_halflife_days")
else:
    assert "history_halflife_days" in s
    print("auto 段已含该键（跳过）")

UP = """# 【v1.23.14 → v1.23.15】把「未做 / 边界」四条做完
#   ★ 新增 1 个键（`auto.history_halflife_days`，出厂 14 天）。
#   ① **分层抽样**：`auto.history_limit` 的语义从「总样本数」改成
#      **「每题型上限」** —— 按题型分两桶各自取最多 N 条。原语义下窗口一缩，
#      事实型会被整体挤掉，「按题型比同类」退化成「比全语料」。
#      扫描上限相应放宽到 4×N（两桶都要收满）。
#   ② **时间衰减**：历史读数改**加权分位**，权重 = 0.5^(age/半衰期)。
#      语料跨十几天，旧样本是旧配置下的读数；不加权会把新读数拉向旧行为。
#   ③ **抽取器补齐**：产物里 254/368 份都写了「**三态判决一致率**」这一行，
#      而上一版抽取器漏了它 ⇒ 该读数只有 n=1，规则形同没校准。
#      本版补抽（实测 n=255、p10=0.167、中位 0.333）；联网行也一并抽取。
#      ★ 抽不到的字段**不写键**（`web_fail=0` 与「没有这一行」是两件事）。
#   ④ **三条规则按实测定**：
#      · 三态一致率的异常线：0.5 → **0.167（实测 p10）**，并要求 ≥30 份样本。
#        原 0.5 落在实测**中位数之上**（中位 0.333）⇒ 会拦掉 54% 的情况，
#        这条「质量优先保护」实际等于把降档功能废掉。
#      · 截断率要 ≥24 **层**样本才表态（实测语料只有 6 层）。
#      · 圈数三级回退保留（实际停圈需 ≥3 份样本）。
#   ★ 对你的影响：**无需改配置**。首次调度仍约 0.2~0.6 秒扫历史。
#   ★ 判据：`check_v12315_history_calibration`（分层夹具 / 衰减数值 / 抽取补齐 /
#      三条规则两向）+ 7 个变异体。真跑对照实验见 `v12315_报告.md`。
#
"""
MARK = "# 【v1.23.14 → v1.23.15】"
ANCHOR = "# 【v1.23.13 → v1.23.14】用**真实历史语料**校准自适应调度"
# ★ 幂等：上一版的这个脚本**没**给升级段做幂等，我跑了两次 ⇒ yaml 里
#   同一段出现两次（已手工去重）。本版显式判重再插。
if MARK in s:
    print("升级段已存在（跳过插入）")
else:
    assert s.count(ANCHOR) == 1, "升级段锚点命中 %d 次" % s.count(ANCHOR)
    s = s.replace(ANCHOR, UP + ANCHOR, 1)
    print("升级段已插入")

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
YML.write_bytes(out)
ytxt = out.decode("utf-8")

spec = importlib.util.spec_from_file_location("cfgsync15", MAIN)
m = importlib.util.module_from_spec(spec)
sys.modules["cfgsync15"] = m
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
                     "history_md", "history_batch", "history_halflife_days")
         if ("  " + k + ":") in ytxt]
_missing = sorted(k for k in flat(m.DEFAULT_CONFIG) if k not in b)
print("load_config 键数：%d / %d | 逐字差异项：%s"
      % (len(a), len(b), sorted(diff) or "无（新增键由出厂值补齐）"))
print("yaml 里写出的 auto 键：", _keys)
print("yaml 缺 DEFAULT_CONFIG 键：", _missing or "无")
_dup = ytxt.count("# 【v1.23.14 → v1.23.15】")
if _dup != 1:
    print("★ 升级段出现 %d 次（应为 1）" % _dup)
_ok = (not diff) and len(_keys) == 6 and not _missing and _dup == 1
print("验收：", "PASS" if _ok else "FAIL")
sys.exit(0 if _ok else 1)

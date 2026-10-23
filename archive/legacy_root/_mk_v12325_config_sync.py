# -*- coding: utf-8 -*-
"""v1.23.25 配置同步：头部版本 + 新增升级段 + DEFAULT_CONFIG 新键（按默认值补写）。

★ 验收 = `load_config` 逐字差异 0 项。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
OV, NV = "1.23.24", "1.23.25"


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r\r\n") == 0
    assert b.count(b"\r\n") == b.count(b"\n")
    return b.decode("utf-8").replace("\r\n", "\n")


def write_crlf(p: Path, t: str) -> None:
    assert "\r" not in t
    p.write_bytes(t.replace("\n", "\r\n").encode("utf-8"))
    c = p.read_bytes()
    assert c.count(b"\r\r\n") == 0 and c.count(b"\r\n") == c.count(b"\n")


T = read_crlf(YAML)

# ---------------- ① 头部版本 ----------------
_a = f"# 元 DGTF · v{OV} 配置文件"
assert T.count(_a) == 1, T.count(_a)
T = T.replace(_a, f"# 元 DGTF · v{NV} 配置文件", 1)
print("  ok [头部版本]")

# ---------------- ② 新增升级段 ----------------
_SEG = f"""# 【v1.23.24 → v1.23.25】「结构覆盖率」按它**本来的视角（结构侧）**重设计并加回
#   ★ **无新增配置键、无默认值改动** ⇒ 本文件除本段与头部版本外一字未动。
#   零、为什么不是简单「加回来」
#     · v1.23.24 把旧「结构覆盖率」换名成「独立度」是对的 —— 旧算式
#       「|被 structural_amps 撞上的 und_aspects| / |und_aspects|」与提示词
#       要求 structural_amps「独立提炼、不得复述」**方向相反**，实测恒 0。
#     · 但本版要**重新设计**它，而不是就此取消。三轮诊断排除了六个候选凭据
#       （详见 `v12325_报告.md` §2）：structural_amps 撞方面 / aligned 撞方面 /
#       covered 撞方面 / struct_trace.newly / amp.polarity / A# 引用 ——
#       前四个要么方向错、要么已被别的读数占用，后两个要么零判别力、
#       要么实测引用数为 0（模型只引 C#）。
#     · 结论：`structural_amps` 是「被消费的表述」，**不是被引用的凭据**。
#       所以「以方面为分母」的任何算式都会继承错位 ⇒ 换分母。
#   一、新算式（自触及）
#     · 结构覆盖率 = 「结构被研究出**自己触及**的概率」
#       = |后续圈自己的产物（线头 / 探针 / 自报触及）里再次呼应到的
#           structural_amps| / |structural_amps|
#     · 分母 = **结构条数**（与「独立度」同分母）；视角 = 「有多活」。
#     · ★ 与「独立度」正交：独立度量「有多**新**」（不与评估阶段的疑问
#       重合），本读数「有多**活**」（后续圈还碰它）。实测 Pearson r ≈ 0.13。
#     · 阈值 `_overlap_coef >= 0.3`（全局判「重合」的口径）。
#   二、三读数并列（产物第七节）
#     「清晰度（模型自评）｜独立度（结构视角·有多新）｜
#       对齐覆盖率（方面视角·对上几成）｜结构覆盖率（结构视角·有多活）」
#   三、旧键一字未动
#     `last_struct_coverage` / `struct_coverage_history` / `last_struct_hit` /
#     `struct_trace` 照旧解析；只有旧键的历史 packed 仍渲染成
#     「结构覆盖率 …（旧口径…）」，重渲染不丢信息也不误导。
#   【怎么退回旧行为】用 v1.23.24 主文件（无配置开关 —— 改的是口径与渲染）。

"""
_anchor = "# 【v1.23.23 → v1.23.24】"
assert T.count(_anchor) == 1, T.count(_anchor)
T = T.replace(_anchor, _SEG + _anchor, 1)
print("  ok [新增升级段]")

write_crlf(YAML, T)
print(f"  已写回 {YAML.name}")

# ---------------- ③ DEFAULT_CONFIG 新键核对 ----------------
sys.path.insert(0, str(HERE))
import importlib.util
spec = importlib.util.spec_from_file_location("dg25", str(HERE / "元DGTF-V1.23.25.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["dg25"] = mod
spec.loader.exec_module(mod)


def _flat(d, pre=""):
    o = {}
    for k, v in (d or {}).items():
        kk = f"{pre}.{k}" if pre else k
        if isinstance(v, dict):
            o.update(_flat(v, kk))
        else:
            o[kk] = v
    return o


# ★ 正确验收：**本版无新增配置键** ⇒ 自己 yaml 与上一版 yaml 的
#   **加载结果**必须逐字相同（拿 DEFAULT_CONFIG 比会被 28 项出厂偏离误伤）。
_cfg_new = mod.load_config(str(YAML))
_cfg_old = mod.load_config(str(HERE / "_bak_dgtf_config.pre_v12325.yaml"))
_fn, _fo = _flat(_cfg_new), _flat(_cfg_old)
_only_n = sorted(set(_fn) - set(_fo))
_only_o = sorted(set(_fo) - set(_fn))
_diffv = [(k, _fo[k], _fn[k]) for k in _fo if k in _fn and _fn[k] != _fo[k]]
print(f"  新 yaml 键 {len(_fn)} / 旧 yaml 键 {len(_fo)}")
print(f"  只在新：{_only_n}   只在旧：{_only_o}")
print(f"  值不同：{len(_diffv)} 项")
for k, a, b in _diffv[:10]:
    print(f"    {k}: 旧={a!r} 新={b!r}")
assert not _only_n and not _only_o and not _diffv, "本版无新增键 ⇒ 必须逐字相同"
print("  ★ 验收：与上一版 yaml 的加载结果逐字差异 0 项 ✓")
print("=" * 78)

# -*- coding: utf-8 -*-
"""v1.23.26 配置同步：头部版本 + 新增升级段 + DEFAULT_CONFIG 新键（按默认值补写）。

★ 验收 = 与上一版 yaml 的加载结果差异**恰好等于本版新增的两个键**（值 = 默认）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
OV, NV = "1.23.25", "1.23.26"


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
_SEG = """# 【v1.23.25 → v1.23.26】五机制算法重构 · 第一期：**换尺子**（不动 LLM 接口）
#   ★ 本版**新增 2 个配置键**（`sim.dedup` / `sim.dedup_susp`），默认值
#     = v1.23.25 里的硬编码字面量 ⇒ **不改这两个键时行为与 v1.23.25 一致**。
#
#   零、本版改什么（设计依据见 `_设计_五机制算法重构_v12326.md`）
#     上一轮对 14 圈真实产物的诊断给出根因：**尺子失真** + **模型自报量空转**。
#     本版只做前者的一半（不改 LLM 接口，可独立验证），即：
#       ① 新增 `_sim3` 三级尺子（对称 Jaccard + BM25 + 结构编号）
#       ② 复述检测从 `_overlap_coef`(min 分母) 切到 `_sim3`
#       ③ 池内去重阈值从硬编码字面量改为可配（本版新键）
#       ④ covers 数字编号分支补语义校验（编号对但语义错必须报红）
#
#   一、为什么需要 `_sim3`
#     · `_overlap_coef(a,b) = |A∩B| / min(|A|,|B|)`。min 分母是**有意**引入的
#       （为了让「短句被长句整段包住」时接近 1，正是复述的形状），但它同时
#       让**两条 3 词短语共享 1 个名词就得 0.5** —— 误报面大于收益。
#       实测：`_overlap_coef("模型 部署", "模型 训练")` = **0.500**。
#     · `_sim3` 的分母换成**并集**（对称），并用 BM25 的 IDF 把罕见词的权重
#       补回来。同一对实测 = **0.333**（不再虚高），且 `sim3(a,b) == sim3(b,a)`。
#     · BM25 纯 Python（无新依赖），语料 = **本圈池内条目**，无需训练/外部服务。
#       语料少于 4 篇时 BM25 通道**自动关闭**（IDF 在小语料上不可靠），
#       退回纯 Jaccard —— 降级路径与主路径共用同一函数，读数可比。
#     · ★ `_overlap_coef` **不删**：它被 19 处调用，跨禁词/未追踪/线头等场景；
#       本版只把「复述检测」一处切到 `_sim3`，并保留 `_overlap_coef` 作
#       「包住形状」的保底判据（它在那处的几何含义是对的）。
#
#   二、`sim` 段两个键（本版新增）
#     · `dedup`      池内 amp / thread / probe 入池去重阈值（旧：硬编码 0.9）
#     · `dedup_susp` 悬置目标去重阈值          （旧：硬编码 0.85）
#     为什么必须提出来：「参数按层可覆盖」是本项目红线，而这两个值原先写在
#     `Pool.merge` 函数体里，**一处都改不了**。提为可配后，默认值与原字面量
#     逐位相同 ⇒ 不配置就与旧版行为一致（冒烟有判据守住这条）。
#
#   三、covers 修正
#     `probe_no_target_covered` 原本只在**非数字** covers 上做语义比较；
#     **数字编号**分支只要 `0 <= idx < len(untouched)` 就判「已覆盖」——
#     实测 covers 乱指 T1（编号在范围内、语义完全无关）**不报红**。
#     本版在该分支补语义校验（探针问题 vs 该未触及项，阈值 0.50）。
#
#   【怎么退回旧行为】用 v1.23.25 主文件；或保持 `sim.dedup` / `sim.dedup_susp`
#     为默认值（v1.23.26 的 sim3 / covers 修正**无开关**，如需完全回退请换主文件）。

"""
_anchor = "# 【v1.23.24 → v1.23.25】"
assert T.count(_anchor) == 1, T.count(_anchor)
T = T.replace(_anchor, _SEG + _anchor, 1)
print("  ok [新增升级段]")

# ---------------- ③ 新增 sim 段（插在 probe: 之前） ----------------
_SEG2 = """sim:
  # 【用途】池内去重阈值。两条 amp / thread / probe 的相似度达到它就不重复入池。
  # 【来源】v1.23.25 及以前是 `Pool.merge` 函数体里的**硬编码字面量 0.9**；
  #         v1.23.26 提为可配（默认值 = 原字面量 ⇒ 行为零变化）。
  # 【建议】
  #   默认 0.9
  #   池子膨胀、重复条目多 → 0.85 ~ 0.88
  #   池子偏小、怕误挡       → 0.92 ~ 0.95
  dedup: 0.9

  # 【用途】悬置目标的去重阈值（与新目标比对）。
  # 【来源】v1.23.25 及以前是 `Pool.merge` 里的**硬编码字面量 0.85**。
  # 【建议】
  #   默认 0.85
  #   悬置重复合并太狠 → 0.9
  dedup_susp: 0.85

"""
_anchor2 = "probe:\n"
assert T.count(_anchor2) == 1, T.count(_anchor2)
T = T.replace(_anchor2, _SEG2 + _anchor2, 1)
print("  ok [新增 sim 段]")

write_crlf(YAML, T)
print(f"  已写回 {YAML.name}")

# ---------------- ④ 验收 ----------------
sys.path.insert(0, str(HERE))
import importlib.util
spec = importlib.util.spec_from_file_location("dg26", str(HERE / "元DGTF-V1.23.26.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["dg26"] = mod
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


_cfg_new = mod.load_config(str(YAML))
_cfg_old = mod.load_config(str(HERE / "_bak_dgtf_config.pre_v12326.yaml"))
_fn, _fo = _flat(_cfg_new), _flat(_cfg_old)
_only_n = sorted(set(_fn) - set(_fo))
_only_o = sorted(set(_fo) - set(_fn))
_diffv = [(k, _fo[k], _fn[k]) for k in _fo if k in _fn and _fn[k] != _fo[k]]
print(f"  新 yaml 键 {len(_fn)} / 旧 yaml 键 {len(_fo)}")
print(f"  只在新：{_only_n}")
print(f"  只在旧：{_only_o}")
print(f"  值不同：{len(_diffv)} 项")
for k, a, b in _diffv[:10]:
    print(f"    {k}: 旧={a!r} 新={b!r}")

# ★ 验收口径（本版有新增键，但 load_config 会从 DEFAULT_CONFIG 补齐默认值，
#   所以**加载结果本来就该逐字相同**）：
#   ① 加载结果零差异（新增键在旧 yaml 下也补出了默认值 ⇒ 两版应当一致）
#   ② 但「出厂 yaml 文本必须显式列出这两个键」—— 冒烟判据就是这么查的
#      （它比对的是 yaml 文本里的键，不是 load_config 的结果）。
assert not _only_n, f"加载结果多出键：{_only_n}"
assert not _only_o, f"有键消失：{_only_o}"
assert not _diffv, f"有值被改动：{_diffv}"
for _k in ("dedup", "dedup_susp"):
    assert f"  {_k}: " in T, f"factory yaml 文本里没显式写 sim.{_k}"
    assert _fn[f"sim.{_k}"] == mod.DEFAULT_CONFIG["sim"][_k], \
        f"sim.{_k} 值 ≠ DEFAULT_CONFIG"
print("  ★ 验收：load_config 逐字差异 0 项 + 出厂 yaml 显式列出 sim.dedup/sim.dedup_susp ✓")
print("=" * 78)

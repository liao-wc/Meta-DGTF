# -*- coding: utf-8 -*-
"""v1.23.5 主补丁：清挂账（pending_fix #1 归一化收口 + #3 布尔兼容留痕）。

纪律：
  · 不覆盖源文件：从 v1.23.4 **复制**出 v1.23.5。
  · 主文件纯 CRLF：read_bytes → 断言 → 转 LF → 替换 → 转回 → write_bytes。
  · 每次替换前断言锚点出现次数 == 1。
  · 大块删除用**正则 + 行首锚定**：「21 空格的 _layer_ceil 行」是「25 空格
    那行」的子串，裸子串计数会撞车 —— 一律 `^ {n}` 锚定。
  · 幂等：每段带哨兵守卫（已改则跳过）。
"""
import ast
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.4.py"
DST = HERE / "元DGTF-V1.23.5.py"

assert SRC.exists(), "源文件不存在"
if not DST.exists():
    shutil.copyfile(SRC, DST)


def read_lf(p: Path) -> str:
    b = p.read_bytes()
    s = b.decode("utf-8")
    assert b.count(b"\r\r\n") == 0, "源文件已有 CRCRLF"
    assert s.count("\r\n") == s.count("\n"), "源文件非纯 CRLF"
    return s.replace("\r\n", "\n")


def write_crlf(p: Path, s: str) -> None:
    assert "\r" not in s, "写回前不得含裸 CR"
    b = s.replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0
    p.write_bytes(b)
    chk = p.read_bytes()
    assert chk.count(b"\r\n") == chk.count(b"\n"), "落盘非纯 CRLF"
    assert chk.count(b"\r\r\n") == 0, "落盘含 CRCRLF"


def rep1(s, old, new, tag):
    n = s.count(old)
    assert n == 1, "%s：锚点命中 %d 次（应为 1）" % (tag, n)
    return s.replace(old, new)


def resub1(s, pat, new, tag):
    """正则替换，断言恰好命中 1 次（DOTALL + 行首锚定的大块删除用）。"""
    n = len(re.findall(pat, s, re.S | re.M))
    assert n == 1, "%s：正则命中 %d 次（应为 1）" % (tag, n)
    return re.sub(pat, new, s, count=1, flags=re.S | re.M)


s = read_lf(DST)
n0 = s.count("\n")

# ================================================================ S0 版本
s = rep1(s, "元 DGTF · v1.23.4\n\nCHANGELOG",
         "元 DGTF · v1.23.5\n\nCHANGELOG", "S0 标题版本")
s = rep1(s, '__version__ = "1.23.4"', '__version__ = "1.23.5"', "S0 __version__")

# ================================================================ S1 changelog
CHANGELOG = """v1.23.5 相对 v1.23.4

【主题】清 `docs/机制审计-v122.md` 的挂账：把调度归一化从「三处各写一份」
  收口成唯一实现（pending_fix #1），并给布尔兼容路径加留痕（#3）。

【为什么现在做】那份审计文档停在 v1.22.2，落后 5 个版本，三条 pending_fix
  的真实状态**只能靠人工抽查** —— 抽查才发现文档写「两份实现」，实际是**三
  处**（模式白名单 3 / 圈数归一化 2 / conf 解析 3 / 低置信退 serial 3）。
  文档低估了重复面，这正是「登记表没有判据盯着」的直接后果。

【S1】调度归一化收口成三个唯一实现
  · 新增 `_plan_conf(data)` / `_normalize_plan_mode(data)` /
    `_normalize_plan_rounds(data, hard, route=None)`，放在 `_layer_floor`
    之后。三处调用点各留一行：
      - `MetaDGTF._decide_parallel_mode`（单目标决策，只定 mode）
      - `plan_resources`（两段式路径，要按 route 裁 rounds）
      - `auto_plan` 的单调用分支（`run()` 走的就是它，不裁 rounds）
  · 形态计数（抠掉模块 docstring 后）：`_up = mode.upper()` 3 → 1、
    `if rnd and len(rnd) < 4:` 2 → 1、`_layer_floor(k, hard, _floor)`
    2 → 1、`conf = float(data.get(` 3 → 0。剩下的那 1 处就是唯一实现本体。

  ★ **刻意不合并**的部分：「低置信退 serial」三处处置不同 ——
    单目标决策与单调用会**改写 reason 并提前 return**（「低置信(x)，退回
    serial：原 reason」），两段式只把 mode 改回 serial 后继续、reason
    **不动**。合并它就会改变返回值形状。这个差异由冒烟
    `check_v1235_pending_fix` 用三处对照钉住 —— 是**有意的差异**，不是
    「忘了合并」。

  ★ 顺带修掉一个潜在崩溃：单调用分支的 `conf = float(...)` 原来是**裸调**、
    不在 try 里 ⇒ 模型返回非数字 confidence 会抛 ValueError 逃出
    `auto_plan`；`_plan_conf` 统一兜成 0.0，且兜的方向是**保守**的
    （0.0 < 阈值 ⇒ 退 serial）。

  ★ 一条**日志**层面的差异（非返回值）：「漏层按中位数补齐」的 info 日志
    原来只在单调用分支打，收进唯一实现后两段式路径也会打一条。
    已 grep 确认没有判据读这条日志。

【S2】pending_fix #3：as_evidence 布尔兼容**留痕**
  · 原状：`_anchor_tier` 静默接受 `True/False`（True → evidence）。
    「还有没有人在用布尔写法」因此**永远没人知道**，这条待办也就永远清不掉。
  · 现在：走兼容路径就 `logger.warning` 一次，文案带原始值与迁移目标。
  · ★ **没有删兼容分支**。仓库内实测**零**布尔调用点（出厂 yaml 与主文件
    DEFAULT_CONFIG 两处都是字符串档），但「外部调用点」在本仓库之外；
    删了就是让外部配置**静默降级**（true → "true" 不在五档 → off，
    从「作证据」掉到「关闭」且无任何提示）—— 比留着更糟。
    正解是先让它**可观测**，等留痕确认没人走再删。

【行为变化】返回值层面**零变化**（改前/改后同一支探针逐行对表：16 组输入
  × 三处的 mode/rounds/conf/reason 全部逐字相同，低置信一组亦然）。
  唯一可观测变化是上面两条：一个潜在 ValueError 被兜住、一条 info 日志
  多了一个出口。

【未做】pending_fix #2（`_adjudicate_sub_tristate` 单票实现归档）本版
  **不动代码**：它是「等 tri_multi_vote 稳定若干批后评估」的等待型挂账。
  本版只给它配判据（可观测 + 可归档时立刻看得见）。

v1.23.4 相对 v1.23.3"""

s = rep1(s, "v1.23.4 相对 v1.23.3", CHANGELOG, "S1 changelog")

# ================================================================ S2 唯一实现
HELPERS = '''def _layer_floor(k: str, hard: int, floor: int) -> int:
    """某层的圈数下限。未单独配置的层用 floor（_MIN_LAYER_ROUNDS 钳过）。"""
    return max(floor, min(_MIN_ROUNDS_BY_LAYER.get(k, floor), hard))


# [v1.23.5] pending_fix #1 收口：调度归一化的**唯一实现**。
#   同一套规则原先在三处各写一份（_decide_parallel_mode / plan_resources /
#   auto_plan 的单调用分支），形态计数：模式白名单 3、conf 解析 3、
#   圈数归一化 2。三份同规则必然漂移 —— 本项目「同一条逻辑多条实现」
#   的第 N 次。现在规则只在这里，三处调用点各留一行。
#   ★ 刻意**不**合并「低置信退 serial」：三处处置不同（见 changelog），
#     合并就会改返回值形状。差异由冒烟 check_v1235_pending_fix 钉住。
def _plan_conf(data) -> float:
    """归一化 `confidence`：不可解析的输入一律记 0.0（= 最低置信 ⇒ 退 serial）。

    ★ 单调用分支原来是**裸** `float(...)`、不在 try 里 ⇒ 模型返回一个
      非数字字面量会抛 ValueError 逃出 auto_plan。这里统一兜住，兜的方向
      是保守的（0.0 < 阈值 ⇒ 退 serial）。
    """
    try:
        return float((data or {}).get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_plan_mode(data) -> str:
    """归一化 `mode`：只有 A~H 与 serial 两种结局，其余一律 serial。"""
    _up = str((data or {}).get("mode", "serial")).strip().upper()
    return _up if _up in ("A", "B", "C", "D", "E", "F", "G", "H") \\
        else "serial"


def _normalize_plan_rounds(data, hard: int, route=None) -> dict:
    """归一化 `rounds`：解析 → 漏层按中位数补 → 钳到每层 [floor, ceil]。

    `route` 给了就按 route 裁剪 —— 那是**调用方**的语义（两段式路径要裁，
    单调用路径没有 route 概念），不是规则本身，所以做成可选参数而不是
    写死在规则里。
    """
    rnd = {}
    raw_r = (data or {}).get("rounds") or {}
    _floor = min(_MIN_LAYER_ROUNDS, hard)
    if isinstance(raw_r, dict):
        for k in ("0", "1", "both", "all"):
            try:
                iv = int(raw_r.get(k))
            except (TypeError, ValueError):
                continue
            if 1 <= iv <= hard:
                rnd[k] = max(iv, _floor)
    # ★ 漏层必须补齐，不能交给配置兜底 —— 真跑实证：a61H 的调度只给了
    #   修行4/研究4，对撞和元漏了 → 那两层走 hard_max（12/13）→ 元层跑满
    #   13 圈、体力耗尽被截断，整轮 20.7min；给全四层的 a61F 只要 9.7min。
    #   hard_max 是「最坏情况预算」，拿它当默认值等于默认最贵。
    if rnd and len(rnd) < 4:
        _vals = sorted(rnd.values())
        _fill = _vals[len(_vals) // 2]
        for k in ("0", "1", "both", "all"):
            rnd.setdefault(k, _fill)
        logger.info("自动调度漏层，按中位数 %d 补齐：%s", _fill, rnd)
    # 补齐值同样要过钳制区（中位数可能落在区间外）
    for k in list(rnd):
        rnd[k] = min(max(rnd[k], _layer_floor(k, hard, _floor)),
                     _layer_ceil(k, hard, _floor))
    if route is not None:
        rnd = {k: v for k, v in rnd.items() if k in route}
    return rnd

_ROUTE_PRESETS = {'''

_FLOOR_OLD = '''def _layer_floor(k: str, hard: int, floor: int) -> int:
    """某层的圈数下限。未单独配置的层用 floor（_MIN_LAYER_ROUNDS 钳过）。"""
    return max(floor, min(_MIN_ROUNDS_BY_LAYER.get(k, floor), hard))

_ROUTE_PRESETS = {'''

if "def _plan_conf(data)" not in s:
    s = rep1(s, _FLOOR_OLD, HELPERS, "S2 插入三个唯一实现")
else:
    print("  [skip] S2 已插入")

# ================================================================ S3 调用点 1
S3_OLD = '''            mode = str(data.get("mode", "serial")).strip()
            _up = mode.upper()
            if _up in ("A", "B", "C", "D", "E", "F", "G", "H"):
                mode = _up
            else:
                mode = "serial"
            conf = float(data.get("confidence", 0.0) or 0.0)
            reason = str(data.get("reason", ""))[:200]'''
S3_NEW = '''            mode = _normalize_plan_mode(data)
            conf = _plan_conf(data)
            reason = str(data.get("reason", ""))[:200]'''

if S3_OLD in s:
    s = rep1(s, S3_OLD, S3_NEW, "S3 调用点1 _decide_parallel_mode")
else:
    print("  [skip] S3 已改")

# ================================================================ S4 调用点 2
S4A_OLD = '''    mode = str(data.get("mode", "serial")).strip()
    _up = mode.upper()
    mode = _up if _up in ("A", "B", "C", "D", "E", "F", "G", "H") \\
        else "serial"

    rnd = {}'''
S4A_NEW = '''    mode = _normalize_plan_mode(data)
    rnd = _normalize_plan_rounds(data, hard, route=route)
    _PLAN_OLD_ROUNDS_MARK = None'''

if S4A_OLD in s:
    s = rep1(s, S4A_OLD, S4A_NEW, "S4a 调用点2 头")
    # 删掉残留的旧 rounds 正文（含 median 补漏 + 钳制 + route 裁剪）
    s = resub1(s,
               r"^ {4}_PLAN_OLD_ROUNDS_MARK = None\n"
               r".*?"
               r"^ {4}rnd = \{k: v for k, v in rnd\.items\(\) if k in route\}\n",
               "\n", "S4b 删 plan_resources 旧 rounds 正文")
else:
    print("  [skip] S4a/b 已改")

S4C_OLD = '''    conf = 0.0
    try:
        conf = float(data.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    if mode != "serial" and conf < _PARALLEL_CONF_MIN:'''
S4C_NEW = '''    conf = _plan_conf(data)
    if mode != "serial" and conf < _PARALLEL_CONF_MIN:'''

if S4C_OLD in s:
    s = rep1(s, S4C_OLD, S4C_NEW, "S4c 调用点2 conf")
else:
    print("  [skip] S4c 已改")

# ================================================================ S5 调用点 3
S5A_OLD = '''        mode = str(data.get("mode", "serial")).strip()
        _up = mode.upper()
        mode = _up if _up in ("A", "B", "C", "D", "E", "F",
                              "G", "H") else "serial"
        conf = float(data.get("confidence", 0.0) or 0.0)
        reason = str(data.get("reason", ""))[:200]'''
S5A_NEW = '''        mode = _normalize_plan_mode(data)
        conf = _plan_conf(data)
        reason = str(data.get("reason", ""))[:200]'''

if S5A_OLD in s:
    s = rep1(s, S5A_OLD, S5A_NEW, "S5a 调用点3 mode+conf")
else:
    print("  [skip] S5a 已改")

if re.search(r"^ {8}# 圈数：逐层取", s, re.M):
    s = resub1(s,
               r"^ {8}# 圈数：逐层取 \[1, hard\].*?\n"
               r".*?"
               r"^ {25}_layer_ceil\(k, hard, _floor\)\)\n",
               "        rnd = _normalize_plan_rounds(data, hard)\n",
               "S5b 调用点3 rounds 块")
else:
    print("  [skip] S5b 已改")

# ================================================================ S6 #3 留痕
S6_OLD = '''    raw = (cfg or {}).get("as_evidence", "off")
    if isinstance(raw, bool):
        return "evidence" if raw else "off"'''
S6_NEW = '''    raw = (cfg or {}).get("as_evidence", "off")
    if isinstance(raw, bool):
        # [v1.23.5 pending_fix #3] 兼容路径**留痕**：原来静默接受，于是
        #   「还有没有人在用布尔写法」永远没人知道，这条待办也就永远清不掉。
        #   现在走一次报一次 —— 清挂账的前提是**看得见**。
        logger.warning(
            "external_anchor.as_evidence 用了 v1.21.75 的布尔写法 %r"
            " → %s（请迁到五档字符串 off/record/crosscheck/evidence/gate）",
            raw, "evidence" if raw else "off")
        return "evidence" if raw else "off"'''

if S6_OLD in s:
    s = rep1(s, S6_OLD, S6_NEW, "S6 as_evidence 布尔兼容留痕")
else:
    print("  [skip] S6 已改")

S6B_OLD = '''      非法值按 "off" 处理（调用点会把它渲染出来，不静默升级权限）。'''
S6B_NEW = '''      非法值按 "off" 处理（调用点会把它渲染出来，不静默升级权限）。
      [v1.23.5] 走布尔兼容会 logger.warning 留痕（可观测化，不再静默）。'''
if S6B_OLD in s:
    s = rep1(s, S6B_OLD, S6B_NEW, "S6b _anchor_tier docstring")
else:
    print("  [skip] S6b 已改")

# ================================================================ 落盘 + 自检
write_crlf(DST, s)

print()
print("S0~S6 完成 ->", DST.name)
print("  行数 %d -> %d（LF 计）" % (n0, s.count("\n")))

ast.parse(s)
print("  [自检] ast.parse 通过")

i = s.index('"""')
j = s.index('"""', i + 3)
body = s[j + 3:]
print("  [自检] 抠 docstring 后形态计数：")
for k, v in {
    "模式白名单 _up = mode.upper()": "_up = mode.upper()",
    "圈数补漏 if rnd and len(rnd) < 4:": "if rnd and len(rnd) < 4:",
    "圈数钳制 _layer_floor(k, hard, _floor)": "_layer_floor(k, hard, _floor)",
    "conf 解析 conf = float(data.get(": 'conf = float(data.get(',
    "低置信 conf < _PARALLEL_CONF_MIN": "conf < _PARALLEL_CONF_MIN",
    "_normalize_plan_mode( 总数": "_normalize_plan_mode(",
    "_normalize_plan_rounds( 总数": "_normalize_plan_rounds(",
    "_plan_conf( 总数": "_plan_conf(",
}.items():
    print("      %-40s %d" % (k, body.count(v)))

print("  [自检] changelog 段顺序：",
      [m.group(1) for m in re.finditer(r"^v(1\.23\.\d+) 相对", s, re.M)][:4])

# -*- coding: utf-8 -*-
"""[v1.23.4] 出厂 yaml 同步。

1. 头部版本 v1.23.3 -> v1.23.4，并加【v1.23.3 → v1.23.4】升级段；
2. 新增强 Top 层 `runtime:` 段（**按 DEFAULT_CONFIG 的默认值写**：
   web/thinking/effort 全 auto ⇒ 行为不动）；
3. 落位在 `cost_profile` 之后（两个都是「顶层总控」，放一起好找）。
"""
from pathlib import Path
import ast

HERE = Path(__file__).resolve().parent
Y = HERE / "dgtf_config.yaml"
b = Y.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "yaml 不是纯 CRLF"
s = b.decode("utf-8").replace("\r\n", "\n")
NL = chr(10)


def rep(old, new, tag):
    n = s.count(old)
    assert n == 1, "%s 锚点命中 %d 次（应 1）" % (tag, n)
    return s.replace(old, new, 1)


# ---- 1 头部版本 ----
s = rep("# 元 DGTF · v1.23.3 配置文件", "# 元 DGTF · v1.23.4 配置文件", "头部版本")

# ---- 2 升级段 ----
UP = NL.join([
    "# 【v1.23.3 → v1.23.4】新增**运行期三项总控**（联网 / 思考 / 强度）",
    "#   本版新增顶层 `runtime:` 段（就在下面 `cost_profile` 之后）。",
    "#   ★ 出厂三项全 `auto` = **不覆盖本文件任何既有键** ⇒ 升级后行为不变",
    "#     （与 `cost_profile` 一样是「顶层总控」，但它管的是**人的当场决定**：",
    "#      这一问要不要联网、要不要思考、思考多用力）。",
    "#   ★ 两种用法：",
    "#     ① 临时（推荐）：交互模式里每轮会问这三项；或命令行",
    "#        `--web on|off --thinking on|off --effort low|high|max`。",
    "#        两者都不改本文件、也不跨轮/跨次记忆。",
    "#     ② 长期：把下面的 `runtime:` 三项改成想要的值（下次加载即生效）。",
    "#   ★ 优先级：命令行 > 本文件 `runtime:` 段 > 本文件里各处的既有键。",
    "#   ★ on/off 会**改写** `web_search.enabled` 与 `api.thinking.default`",
    "#     **加整张 `api.thinking.stages` 表** —— 只改 default 会被 stage 表",
    "#     盖住（优先级：显式 thinking > stage > default），总开关就成了空话。",
    "#   ★ `effort` 取值只认 **low / high / max**（本文件 api.thinking 段的",
    "#     注释里记着 2026-10-02 的实测结论）；且**只在思考开启时**才随请求",
    "#     发出 —— 思考关着还设强度，引擎会当场提示「不生效」。",
    "#   ★ 要「真开思考」仍建议改 `api.thinking.stages` 里**具体环节**的值：",
    "#     总开关 `thinking: on` 会把**全部**环节打开（成本显著上升，",
    "#     思考 ⇒ 每次调用 max_tokens ≥ 32000）。",
    "#'\u0020",
    "",
])
s = rep("# 【v1.23.2 → v1.23.3】§十「仍未做 / 如实记账」五条全清",
        UP.replace("#'\u0020", "#") + "# 【v1.23.2 → v1.23.3】§十「仍未做 / 如实记账」五条全清",
        "升级段")

# ---- 3 runtime 段 ----
RT = NL.join([
    "",
    "# ------------------------------------------------------------",
    "# 运行期总控（三层里的**最外层**：命令行 / 交互 / 本段）",
    "# ------------------------------------------------------------",
    "# 三项都是「人的当场决定」，默认 auto = 不覆盖任何既有键（行为不变）。",
    "#   web      —— 联网总开关：auto / on / off",
    "#               on  仍受 `web_search.stages` 的环节授权与配额约束；",
    "#               off 一律不发起检索（也就不会有 W# 进引用表）。",
    "#   thinking —— 思考总开关：auto / on / off",
    "#               on  = **全部环节**开思考（成本显著上升，慎用）；",
    "#               off = 全部环节关思考（覆盖 stages 表里的每一个键）。",
    "#   effort   —— 思考强度：auto / low / high / max",
    "#               只在思考开启时生效；取自 2026-10-02 实测可用集。",
    "# ★ 「auto」的语义是「按本文件的既有键」，**不是**「跟上次一样」。",
    "runtime:",
    "  web: auto",
    "  thinking: auto",
    "  effort: auto",
    "",
])
s = rep("cost_profile: quality" + NL, "cost_profile: quality" + NL + RT, "runtime 段")

Y.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
print("yaml 已同步：头部版本 + 升级段 + runtime 段（%d 行）"
      % (s.count(NL) + 1))

# ---- 4 复核：解析 + 与 DEFAULT_CONFIG 对账 ----
import importlib.util
import sys
import yaml
spec = importlib.util.spec_from_file_location("m_ys", HERE / "元DGTF-V1.23.4.py")
m = importlib.util.module_from_spec(spec)
sys.modules["m_ys"] = m
spec.loader.exec_module(m)
user = yaml.safe_load(Y.read_text(encoding="utf-8")) or {}


def flat(d, pre=""):
    out = {}
    for k, v in (d or {}).items():
        key = ("%s.%s" % (pre, k)) if pre else str(k)
        if isinstance(v, dict):
            out.update(flat(v, key))
        else:
            out[key] = v
    return out


du, dd = flat(user), flat(m.DEFAULT_CONFIG)
miss = sorted(k for k in dd if k not in du)
print("yaml 缺 DEFAULT_CONFIG 的键（应 0）：", miss)
print("runtime 段：", user.get("runtime"))

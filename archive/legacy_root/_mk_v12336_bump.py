# -*- coding: utf-8 -*-
"""建 v1.23.36：复制主文件 + 四处版本同步 + AST 登记新符号。

★ 「四处」= docstring 标题 / `__version__` / 出厂 yaml 头部 / smoke SRC
  （判据 `_version_consistent` 查的就是这几处一致）。
★ 还要登记**新增符号**（审计 6.6 两向对账）。
"""
import ast
import io
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE / "元DGTF-V1.23.34.py"
NEW = HERE / "元DGTF-V1.23.36.py"
YAML = HERE / "dgtf_config.yaml"
SMOKE = HERE / "smoke_test.py"
MUT = HERE / "_mut_v12332.py"
REG = HERE / "_v122_ast_registry.json"

#: 本版新增符号（逐条写清「它干什么」）
REASONS = {
    "_trace_note": ("可追溯", "通用行为 trace 写入（模块级：调用点在两个无继承类上）"),
    "trace_decide": ("可追溯", "L1 决策：**必须带「考虑过的全部选项」**（decision.chain/DLF）"),
    "trace_outcome": ("可追溯", "L3 归因：动作前后读数对比（EML 唯一能依赖的学习信号）"),
    "ControlSurface": ("可控", "显式控制面：白名单+边界+必留痕；所有运行时调度调整的唯一收口"),
    "_llm_ctx_set": ("联网全接", "线程局部上下文写入（供 LLM 拿题面/层/圈/联网回调）"),
    "_llm_ctx_get": ("联网全接", "线程局部上下文读取"),
    "_infer_stage_from_stack": ("联网全接", "从调用栈推断环节名（30 环节各自一个开关）"),
    "_readings_bundle": ("读数显示", "一层全部读数的**单一真相源**（日志/产物共用）"),
    "_readings_line": ("读数显示", "运行中的每层读数**一行**（走 logger，不受 verbose 控制）"),
    "_readings_table": ("读数显示", "跨层读数总表（日志等宽版 / 产物 Markdown 版，同源）"),
    "_practice_term_calibration_prep": ("联网全接", "修行层术语校准：默认关；打开只进 pool+留痕"),
    "_stop_criteria_check": ("联网全接", "停止理由复核：默认关；打开只留痕、不改决策"),
}


def syms(p):
    return {n.name for n in ast.walk(ast.parse(Path(p).read_text(encoding="utf-8")))
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


def main():
    # ① 复制
    if not NEW.is_file():
        shutil.copyfile(OLD, NEW)
        print("已复制 → %s" % NEW.name)

    # ② 主文件两处版本
    raw = NEW.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    _a1 = "元 DGTF · v1.23.34"
    _a2 = '__version__ = "1.23.34"'
    if _a1 in s:
        assert s.count(_a1) == 1 and s.count(_a2) == 1
        s = s.replace(_a1, "元 DGTF · v1.23.36", 1)
        s = s.replace(_a2, '__version__ = "1.23.36"', 1)
        out = s.replace("\n", "\r\n").encode("utf-8")
        assert b"\r\r\n" not in out
        NEW.write_bytes(out)
        print("主文件版本 → 1.23.36")
    else:
        print("主文件已是新版（跳过）")

    # ③ yaml 头部 + 升级段
    yraw = YAML.read_bytes()
    assert yraw.count(b"\n") == yraw.count(b"\r\n")
    ys = yraw.decode("utf-8").replace("\r\n", "\n")
    if "# 元 DGTF · v1.23.34 配置文件" in ys:
        ys = ys.replace("# 元 DGTF · v1.23.34 配置文件",
                        "# 元 DGTF · v1.23.36 配置文件", 1)
        _anchor = "# 【v1.23.33 → v1.23.34】提示词优化"
        _seg = """# 【v1.23.34 → v1.23.36】联网全接 + 读数全量显示 + 可追溯 + 显式控制面
#   ★ 本版**新增 30 个联网环节开关**（`web_search.stages.*`，全部默认 false
#     ⇒ 默认行为逐字不变）；其余均是**加性**（新字段默认空、新分支在开关开后才动）。
#   ① **联网全接**：30 个环节（含 LLM 调用的函数）都能联网 —— 实现在 `LLM.call`
#      一处（所有环节必经）⇒ 一处改全覆盖；**每环节一个开关**（配置可控）。
#   ② **所有层都注入**（用户口径）：修行层的**硬豁免已取消**，保护改为
#      「30 个开关默认关」这种**配置式**保护。
#   ③ **读数全量显示**：运行中每层一行 + 结束时总表 + 产物 Markdown 表
#      （三处**同源**，走 logger 不受 verbose 控制）。
#   ④ **三层 trace**（决策含「被否选项」/ 动作 / 归因）+ **显式控制面**
#      `ControlSurface`（白名单 + 边界 + 必留痕；绝不写配置）。

# 【v1.23.33 → v1.23.34】提示词优化"""
        assert ys.count(_anchor) == 1, "yaml 升级段锚点命中 %d 次" % ys.count(_anchor)
        ys = ys.replace(_anchor, _seg, 1)
        yout = ys.replace("\n", "\r\n").encode("utf-8")
        assert b"\r\r\n" not in yout
        YAML.write_bytes(yout)
        print("yaml 版本与升级段已同步")
    else:
        print("yaml 已是新版（跳过）")

    # ④ SRC 两处
    for _p in (SMOKE, MUT):
        _s = _p.read_text(encoding="utf-8")
        if "元DGTF-V1.23.34.py" in _s:
            _s = _s.replace("元DGTF-V1.23.34.py", "元DGTF-V1.23.36.py", 1)
            _p.write_text(_s, encoding="utf-8")
            print("%s SRC → V1.23.36" % _p.name)

    # ⑤ AST 登记
    cur, prev = syms(NEW), syms(OLD)
    mine = sorted(cur - prev)
    d = json.loads(REG.read_text(encoding="utf-8"))
    add, miss = [], []
    for _n in mine:
        if _n in d["registry"]:
            continue
        _r = REASONS.get(_n)
        if _r is None:
            miss.append(_n)
            continue
        d["registry"][_n] = {"phase": _r[0], "reason": _r[1]}
        add.append(_n)
    if miss:
        raise SystemExit("新符号缺 reason（必须逐条写）：%r" % (miss,))
    d["current"] = NEW.name
    REG.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print("新增符号 %d 个，已全部登记；registry 共 %d"
          % (len(add), len(d["registry"])))


main()

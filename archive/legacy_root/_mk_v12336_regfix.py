# -*- coding: utf-8 -*-
"""收尾：① 登记 19 个新符号；② 更新 `_probe_v123_w34.py` 的联网调用点白名单。

## 为什么
· **6.6 两向对账**：本轮新增 19 个符号（trace / 控制面 / 联网全接 / 读数显示）
  **未登记** —— 我的 bump 脚本拿 V1.23.34 当基线 ⇒ 差集为空，漏了登记。
  ★ 教训：**bump 时的基线要用 `_baseline_v12177.py`**（审计用的就是它），
    不是「上一版」。
· **C4.b/C4.c**：判据断言「`self._web_search(` 调用点 = 6，且全在 5 个白名单方法里」
  —— 本轮新增 2 个真实调用点（`_practice_term_calibration_prep` /
  `_stop_criteria_check`）⇒ 判据**正确判红**（它在干活）。改法是**登记新调用点**，
  不是放宽：数量仍是**硬等式**（6 → 8）。
"""
import ast
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REG = HERE / "_v122_ast_registry.json"
PROBE = HERE / "_probe_v123_w34.py"

REASONS = {
    "ControlSurface": "显式控制面（白名单+边界+必留痕）：所有运行时调度调整的唯一收口",
    "_lookup": "控制面：白名单查找",
    "read": "控制面：读当前值（改过读数改后的）",
    "write": "控制面：写入（白名单外/缺why/缺trace_ref/越界 ⇒ 拒且留痕）",
    "snapshot": "控制面：快照（供产物对账）",
    "_check_bounds": "控制面：边界校验（只拒不夹取）",
    "_control": "控制面惰性访问器（覆盖所有路径，不动 __init__）",
    "_llm_ctx_set": "联网全接：线程局部上下文写入（题面/层/圈/联网回调）",
    "_llm_ctx_get": "联网全接：线程局部上下文读取",
    "_infer_stage_from_stack": "联网全接：从调用栈推断环节名（30 环节各自一个开关）",
    "_web_augment": "联网全接：统一增强层（所有层都注入；全部经 Gate；默认关零行为差）",
    "_trace_note": "可追溯：通用行为 trace 写入（模块级：调用点在两个无继承类上）",
    "trace_decide": "可追溯：L1 决策（必须带「考虑过的全部选项」）",
    "trace_outcome": "可追溯：L3 归因（动作前后读数对比）",
    "_readings_bundle": "读数显示：一层全部读数的单一真相源（日志/产物共用）",
    "_readings_line": "读数显示：运行中每层一行（走 logger，不受 verbose 控制）",
    "_readings_table": "读数显示：跨层总表（日志等宽版 / 产物 Markdown 版，同源）",
    "_practice_term_calibration_prep": "修行层术语校准（默认关；打开只进 pool+留痕、不注入）",
    "_stop_criteria_check": "停止理由复核（默认关；打开只留痕、不改决策）",
}

OLD_WHITE = '''# `self._web_search(` 调用点白名单：必须落在 6 个接入方法里
_WHITE = ("_research_web_prep", "_web_evidence_hook", "_web_duel_arbitration",
          "_web_meta_clean_check", "_adjudicate_sub_tristate_multi")
_calls = txt.count("self._web_search(")
ck("C4.b `self._web_search(` 调用点 = 6"
   "（W2 三处：decompose/precedent/evidence；W3 两处；W4 一处）",
   _calls == 6, repr(_calls))'''

NEW_WHITE = '''# `self._web_search(` 调用点白名单：必须落在**已登记**的接入方法里。
# ★ 新增调用点要**登记**（数量是硬等式，不是 >=）：
#   原先 6 处（W2 三处：decompose/precedent/evidence；W3 两处；W4 一处）；
#   本轮新增 2 处 —— `practice_term_calibration`（修行层术语校准，只留痕不注入）
#   与 `stop_criteria`（停止理由复核，不改决策）。两者都**默认关**（零行为差）。
_WHITE = ("_research_web_prep", "_web_evidence_hook", "_web_duel_arbitration",
          "_web_meta_clean_check", "_adjudicate_sub_tristate_multi",
          "_practice_term_calibration_prep", "_stop_criteria_check")
_calls = txt.count("self._web_search(")
ck("C4.b `self._web_search(` 调用点 = 8"
   "（W2 三处 + W3 两处 + W4 一处 + 修行层术语校准 + 停止判据复核）",
   _calls == 8, repr(_calls))'''


def main():
    # ① 登记
    d = json.loads(REG.read_text(encoding="utf-8"))
    reg = d["registry"]
    add = []
    for k, v in REASONS.items():
        if k not in reg:
            reg[k] = {"phase": "v1.23.36", "reason": v}
            add.append(k)
    d["current"] = "元DGTF-V1.23.36.py"
    REG.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print("已登记 %d 个新符号；registry 共 %d" % (len(add), len(reg)))
    _miss = [k for k in REASONS if k not in reg]
    assert not _miss, "还有没登记上的：%r" % (_miss,)

    # ② 白名单
    # ★ 先归一化换行：文件可能是 CRLF，而锚点是 LF 写的 ⇒ 不归一化必然 0 命中
    #   （本脚本第一版就是这么失败的）。
    raw = PROBE.read_bytes()
    crlf = raw.count(b"\r\n")
    assert raw.count(b"\n") == crlf, "换行不纯（LF %d / CRLF %d）" % (
        raw.count(b"\n"), crlf)
    s = raw.decode("utf-8").replace("\r\n", "\n")
    assert s.count(OLD_WHITE) == 1, "白名单锚点命中 %d 次" % s.count(OLD_WHITE)
    s = s.replace(OLD_WHITE, NEW_WHITE, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    PROBE.write_bytes(out)
    print("C4.b/C4.c 白名单已更新（6 → 8，仍为硬等式）")


main()

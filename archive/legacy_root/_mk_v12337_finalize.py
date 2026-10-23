# -*- coding: utf-8 -*-
"""**链后收尾**（第 1 部分）：V1.23.37 的 AST 登记 + yaml 版本/升级段 + CHANGELOG 段。

## 为什么整合成一个脚本
用户口径「自行思考选择最优路径、提高效率」⇒ 链跑完后要做的机械动作**一次做完**，
而不是十几个小回合。本脚本与 `_mk_v12337_deferred.py`（切 SRC + 判据 + 变异体）
合计覆盖「并入」所需的全部机械步骤；**报告与记忆由 agent 手写**（需要判断）。

## 门
`WB_SM=1` —— 与 deferred 同一道门（都要等验证跑完）。
"""
import io
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.37.py"
YAML = HERE / "dgtf_config.yaml"
CHG = HERE / "CHANGELOG.md"
REG = HERE / "_v122_ast_registry.json"

if os.environ.get("WB_SM") != "1":
    raise SystemExit("⏸ 链后执行：WB_SM=1 python %s" % Path(__file__).name)

#: 本版（v1.23.37）新增符号 + 理由
NEW_SYMS = {
    "parse_web_need":
        "联网按需协议：从产出里解析「我需要外部事实」声明（容错；解不出当没声明）",
    "_web_need_report":
        "联网按需协议：把声明逐条过 Gate ⇒ 检索 ⇒ 进池 + logger 留痕（本版不回喂）",
}


def main():
    # ── ① AST 登记 ──
    import ast
    def syms(p):
        return {n.name for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
                if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    _base = syms(HERE / "_baseline_v12177.py")
    _cur = syms(SRC)
    d = json.loads(REG.read_text(encoding="utf-8"))
    _add = []
    for _n in sorted(_cur - _base):
        if _n in d["registry"]:
            continue
        _r = NEW_SYMS.get(_n)
        if _r is None:
            raise SystemExit("新符号缺 reason（逐条写清）：%r" % (_n,))
        d["registry"][_n] = {"phase": "v1.23.37", "reason": _r}
        _add.append(_n)
    d["current"] = SRC.name
    REG.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print("① AST 登记：新增 %r；registry 共 %d" % (_add, len(d["registry"])))

    # ── ② yaml 头部 + 升级段 ──
    raw = YAML.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    ys = raw.decode("utf-8").replace("\r\n", "\n")
    if "# 元 DGTF · v1.23.36 配置文件" in ys:
        ys = ys.replace("# 元 DGTF · v1.23.36 配置文件",
                        "# 元 DGTF · v1.23.37 配置文件", 1)
        _a = "# 【v1.23.34 → v1.23.36】联网全接 + 读数全量显示 + 可追溯 + 显式控制面"
        _seg = """# 【v1.23.36 → v1.23.37】联网按需协议 + 圈级心跳（并入前一批的验证版）
#   ★ **无新增配置键**（本版全是行为侧改动，默认关/默认不动 ⇒ 零行为差）：
#   ① **联网按需协议**：环节可在产出末尾用 `===WEB-NEED===` 声明「我需要外部
#      事实」⇒ 引擎解析并**逐条过同一个 Gate**（授权/配额/降级）⇒ 检索 + 留痕。
#      不写就零变化；声明被采纳/被拒都留痕（`logger` 里有 `[WEB-NEED]` 行）。
#   ② **圈级心跳**：用「池增量」当上一圈产出的代理，在 `_before_round` 一处
#      记基线；上一圈零增量 ⇒ 放宽本圈对撞/探针类环节的联网（经控制面）。
#   ③ 并入 v1.23.36 的全部改动（联网全接 / 所有层注入 / 读数全量 / 三层 trace /
#      显式控制面 / 心跳 / EML 五分支「学了要做」/ 所有可配置行为纳入学习）。

# 【v1.23.34 → v1.23.36】联网全接 + 读数全量显示 + 可追溯 + 显式控制面"""
        assert ys.count(_a) == 1, "升级段锚点 %d 次" % ys.count(_a)
        ys = ys.replace(_a, _seg, 1)
        _out = ys.replace("\n", "\r\n").encode("utf-8")
        assert b"\r\r\n" not in _out
        YAML.write_bytes(_out)
        print("② yaml 版本 + 升级段已同步（**无新增配置键**）")
    else:
        print("② yaml 已是新版（跳过）")

    # ── ③ CHANGELOG 段 ──
    s = CHG.read_text(encoding="utf-8")
    _a2 = "---\n\nv1.23.36 相对 v1.23.34"
    if "v1.23.37 相对 v1.23.36" in s:
        print("③ CHANGELOG 已有 37 段（跳过）")
    else:
        assert s.count(_a2) == 1, "CHANGELOG 锚点 %d 次" % s.count(_a2)
        _new = """---

v1.23.37 相对 v1.23.36

【主题】**联网按需协议**（环节自己说要不要）+ **圈级心跳**（运行中逐圈调整）。
—— 补齐「联网全面化」与「运行中动态调整」的最后两环。

【① 联网按需协议】
  · 前一批做的是「**统一增强层**」（引擎在调用**前**主动挂参考，按环节开关）；
    那是「引擎猜需不需要」。**「按需」的"需"只有环节自己知道** ⇒ 本版补上：
      环节产出末尾可写 `===WEB-NEED===` + `{"queries": [...]}`
      ⇒ 引擎解析 ⇒ **逐条过同一个 Gate**（授权/三层配额/失败降级）⇒
        检索 ⇒ 进池（W#）+ `logger` 留痕（`[WEB-NEED]` 行）。
  · **可选协议**：不写就**零变化**；★ 本版**不"回喂"**（那要在同一环节再调一次，
    成本翻倍）—— 先把「**声明被听见并真的去查了**」做实。
  · 容错：`parse_web_need` 对畸形输入**一律不抛错**（只当没声明），
    并对一次声明**截量**（默认 3 条，防一个环节吃光配额）。

【② 圈级心跳】
  · 层级心跳只在**层收尾**能拿到 view；圈级要读「上一圈」，而 `view` 每圈新建。
    若去两个圈循环调用点各存一次 view，就落进本项目反复踩的
    「**同一条逻辑两处各写一份**」⇒ 迟早分叉。
  · **⇒ 改用「池增量」**：`_before_round` **每圈都调**，在它里记「本圈开始的
    池规模」；下一圈的增量 = **上一圈的产出**（新增 & 与线头）⇒ **只改一处**。
  · 触发：上一圈**零增量**（复述/停滞）⇒ 放宽本圈对撞/探针类环节联网
    （经 `ControlSurface`，可追溯 + 可控）。
  · **零行为差**：第一圈无基线 ⇒ 不动；增量为正 ⇒ 不动。

【③ 并入 v1.23.36】
  联网全接（30 环节）· 所有层注入 · 读数全量显示（日志+产物同源）·
  三层 trace · 显式控制面 · 心跳级调度 · EML 五分支「学了要做」·
  所有可配置行为纳入学习（`_action_on` 运行时覆盖 + `thinking_hint`/`action_hint`）·
  ★ 真跑逮到的 `yin_yang_divergence` 静默缺失（`merge_expand` 合并路径提前 return）。

【验收】（见 `v12337_报告.md`；本段在链后按实测回填）
"""
        s = s.replace(_a2, _new + "\n" + _a2, 1)
        CHG.write_text(s, encoding="utf-8")
        print("③ CHANGELOG 段已加")


main()

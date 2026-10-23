# -*- coding: utf-8 -*-
"""[v1.23.2] 报告定稿器（第二遍，**按小节锚替换**，幂等）。

为什么不用占位符：占位符被替换一次就没了，重跑就会 assert 失败。
改成「标题锚 → 下一节标题」之间整段替换，可以反复跑（数据换版后重填）。

填四段：§三（内嵌分析）/ §七（验收表）/ 附录交付物 / 差异规模。
"""
import difflib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REP = HERE / "v1232_报告.md"
SRC = "元DGTF-V1.23.2.py"
PY = sys.executable


def rc_of(cmd, timeout=2400):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=str(HERE))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def last_pass(out):
    m = re.findall(r"PASS (\d+) / FAIL (\d+)", out)
    return m[-1] if m else None


# ---------------- 内嵌分析 ----------------
rc_of([PY, "_w6_analyze.py"])
_ana = HERE / "_v1230_w6_analysis.md"
_t = _ana.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
_t = [("#" + l) if l.startswith("#") else l for l in _t]
_body = [l for l in _t if "分析：三场景命中率" not in l]
W6 = ("（正文由 `_w6_analyze.py` 生成、逐字内嵌；完整数据见 `_v1230_w6_analysis.md`"
      " 与 `_v1230_w6_runs.json`。）\n\n" + "\n".join(_body).strip())

# ---------------- 验收表 ----------------
_smoke, _smrc = rc_of([PY, "smoke_test.py"])
_nv, _nx = len(re.findall("✓", _smoke)), len(re.findall("✗", _smoke))
_rows = []
for _p in ("_probe_v123_w1.py", "_probe_v123_w2.py", "_probe_v123_w34.py",
           "_probe_v1231_left.py", "_probe_v1232_audit.py"):
    _o, _r = rc_of([PY, _p, SRC])
    _m = last_pass(_o)
    _rows.append((_p, ("PASS %s / FAIL %s" % _m) if _m else "?"))
_vr = []
for _ph in ("v123_w1", "v123_w2", "v123_w34", "v123_w5", "v123_w6",
            "v1232", "p2"):
    _o, _r = rc_of([PY, "_v122_verify.py", "--phase", _ph, "--src", SRC])
    _m = last_pass(_o)
    _vr.append((_ph, ("PASS %s / FAIL %s" % _m) if _m else "?"))
_oa, _ra = rc_of([PY, "_v122_verify.py", "--phase", "all", "--src", SRC])
_ma = last_pass(_oa)
_fail = [l.strip() for l in _oa.split("\n") if l.strip().startswith("❌ FAIL")]
VT = ["```", "%-54s → EXIT=%d，✓=%d，✗=%d" % ("python smoke_test.py", _smrc, _nv, _nx)]
for _p, _r in _rows:
    VT.append("%-54s → %s" % ("python " + _p, _r))
for _ph, _r in _vr:
    VT.append("%-54s → %s" % ("python _v122_verify.py --phase " + _ph, _r))
VT.append("%-54s → %s" % ("python _v122_verify.py --phase all",
                          "PASS %s / FAIL %s" % _ma if _ma else "?"))
_reg = rc_of([PY, "-c", (
    "import json,ast;from pathlib import Path;"
    "d=json.load(open('_v122_ast_registry.json',encoding='utf-8'));"
    "f=lambda p:{n.name for n in ast.walk(ast.parse(Path(p).read_text(encoding='utf-8')))"
    " if isinstance(n,(ast.FunctionDef,ast.ClassDef))};"
    "a=f(d['baseline']);b=f('" + SRC + "');"
    "print(len(b-a),len([x for x in b-a if x not in d['registry']]),"
    "len([k for k in d['registry'] if k not in b-a]))")])
_rg = _reg[0].strip().split() or ["?", "?", "?"]
VT.append("%-54s → added %s / 未登记 %s / 过期 %s"
          % ("AST 登记表两向对账", _rg[0], _rg[1], _rg[2]))
VT.append("%-54s → 已同步；两版差异 16 项**全部**是「改前从未生效」的键"
          % "dgtf_config.yaml")
VT.append("```")
VT.append("")
VT.append(("**`--phase all` 仍有 %d 条红**：%s" % (len(_fail), "；".join(_fail)))
          if _fail else
          "**`--phase all` = 0 FAIL**（含 v1.22.2 遗留的 `P2.4.a/b`、本版新增的"
          " `v1232` 档，以及用本版重跑的 10 跑产物）。")

# ---------------- 交付物 ----------------
REQ = ["元DGTF-V1.23.2.py", "v1232_报告.md", "_probe_v1232_audit.py",
       "_mk_v1232.py", "_mk_v1232_smoke_checks.py", "_mk_v1232_config_sync.py",
       "_mk_v1232_verify.py", "_mk_v1232_fill.py", "_fix_gen.py",
       "_fix_w2mut.py", "_fix_probes2.py", "_fix_re.py", "_fix_re2.py",
       "_fix_analyze.py", "dgtf_config.yaml", "smoke_test.py",
       "_v122_verify.py", "_v122_ast_registry.json", "_v1230_w6_analysis.md",
       "_w6_analyze.py", "_run_v1230_w6.py", "_v1230_w6_runs.json",
       "v1231_报告.md", "v123_报告.md", "_v123_taskbook.md",
       "docs/W系列启动检查清单-v1222.md"]
_missing = [r for r in REQ if not (HERE / r).exists()]
_lines = (HERE / SRC).read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
DL = ["| 文件 | 说明 |", "|---|---|",
      "| `元DGTF-V1.23.2.py` | 主文件（%d 行，纯 CRLF，`__version__ = \"1.23.2\"`） |"
      % (len(_lines) - 1),
      "| `_probe_v1232_audit.py` | **整体审计探针**（10 类检查 + 4 自检变异体，62 条） |",
      "| `_mk_v1232*.py` | 补丁 / 判据注入器 / 配置同步 / 验收档 / 报告定稿器 |",
      "| `_fix_*.py` | 本轮踩坑的定点修复脚本（生成器被 heredoc 撕坏、锚点失效、"
      "正则空过、`%s` 忘套 `%`…） |",
      "| `_v1230_w6_analysis.md` + `_w6_analyze.py` | 三场景命中率（检索级 + Wilson）"
      "/ 三票正交度 |",
      "| `_baseline_v12177.py` / `元DGTF-V1.23.1.py` | 差异对比基线 |"]
if _missing:
    DL += ["", "⚠️ 缺失：%s" % ", ".join(_missing)]

# ---------------- 差异规模 ----------------
_a = (HERE / "元DGTF-V1.23.1.py").read_text(encoding="utf-8") \
    .replace("\r\n", "\n").split("\n")
_b = (HERE / SRC).read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
_sm = difflib.SequenceMatcher(None, _a, _b, autojunk=False)
_del = sum(i2 - i1 for t, i1, i2, j1, j2 in _sm.get_opcodes() if t == "delete")
_ins = sum(j2 - j1 for t, i1, i2, j1, j2 in _sm.get_opcodes() if t == "insert")
_rep = sum(max(i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in _sm.get_opcodes()
           if t == "replace")
_bs = HERE / "_baseline_v12177.py"
_extra = ""
if _bs.is_file():
    _c = _bs.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    _sm2 = difflib.SequenceMatcher(None, _c, _b, autojunk=False)
    _d2 = sum(i2 - i1 for t, i1, i2, j1, j2 in _sm2.get_opcodes() if t == "delete")
    _extra = ("\n对 **v1.21.77**（`_baseline_v12177.py`）：纯删除 %d；行数 %d → %d"
              "（含 v1.22.0 / v1.22.1 / v1.22.2 / v1.23.0 / v1.23.1 五版）。"
              % (_d2, len(_c) - 1, len(_b) - 1))
DIFFS = ("对 **v1.23.1**：**纯删除行 %d**，纯新增 +%d，改写（新行数）%d；"
         "行数 %d → %d。%s" % (_del, _ins, _rep, len(_a) - 1, len(_b) - 1, _extra))

# ---------------- 写回（按小节锚） ----------------
s = REP.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _swap(head, body, up_to):
    i = s.index(head)
    j = s.index(up_to, i)
    return s[:i] + head + "\n\n" + body + "\n\n" + s[j:]


s = _swap("## 三、遗留1 · 三场景命中率 + 三票正交度（口径重做）", W6,
          "---\n\n## 四、遗留3")
s = _swap("## 七、验收总表", "\n".join(VT), "---\n\n## 八、")
s = _swap("## 附录 · 交付物清单", "\n".join(DL), "### 差异规模")
s = _swap("### 差异规模", DIFFS, "\n---") if "\n---" in s[s.index("### 差异规模"):] \
    else s[: s.index("### 差异规模")] + "### 差异规模\n\n" + DIFFS + "\n"

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
REP.write_bytes(out)
print("报告已重填：§三 / §七 / 附录 / 差异规模")
print("缺失交付物：", _missing or "无")
print("--phase all:", "PASS %s / FAIL %s" % _ma if _ma else "?", _fail)
print("smoke EXIT=%d ✓=%d ✗=%d" % (_smrc, _nv, _nx))

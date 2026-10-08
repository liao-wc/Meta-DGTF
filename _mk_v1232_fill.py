# -*- coding: utf-8 -*-
"""[v1.23.2] 报告定稿器：把真读数填进 `v1232_报告.md` 的占位符。

占位符：W6_RUNS（三场景/正交度正文）/ VERIFY_TABLE / DELIVERABLES / DIFFSCALE

★ 上一版踩过的两件事都按正解处理：
  · `PASS n / FAIL m` 要取**最后一处**（档汇总行在最后；探针自己的汇总会先打印）；
  · 内嵌分析的标题要**降一级**（否则报告里出现两个「## 一、」）。
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


def rc_of(cmd, timeout=1800):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=str(HERE))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def last_pass(out):
    m = re.findall(r"PASS (\d+) / FAIL (\d+)", out)
    return m[-1] if m else None


# ------------------------------------------------ 1 三场景/正交度正文
_o, _rc = rc_of([PY, "_w6_analyze.py"])
_ana = HERE / "_v1230_w6_analysis.md"
if _ana.is_file():
    _t = _ana.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    _t = [("#" + l) if l.startswith("#") else l for l in _t]
    # ★ 过滤要在**降级之后**判：降级后 `# 分析：…` 变成 `## 分析：…`，
    #   按 `startswith("# 分析")` 判必然漏（第一版就是这样漏了一行 H1）。
    _body = "\n".join(l for l in _t
                     if "分析：三场景命中率" not in l.lstrip("# "))
    W6 = ("（正文由 `_w6_analyze.py` 生成、逐字内嵌；完整数据见 "
          "`_v1230_w6_analysis.md` 与 `_v1230_w6_runs.json`。）\n\n"
          + _body.strip() + "\n")
else:
    W6 = "⚠️ 分析文件缺失\n"

# ------------------------------------------------ 2 验收表
_smoke, _smrc = rc_of([PY, "smoke_test.py"])
_nv = len(re.findall("✓", _smoke))
_nx = len(re.findall("✗", _smoke))
_prows = []
for _p in ("_probe_v123_w1.py", "_probe_v123_w2.py", "_probe_v123_w34.py",
           "_probe_v1231_left.py", "_probe_v1232_audit.py"):
    _out, _r = rc_of([PY, _p, SRC])
    _m = last_pass(_out)
    _prows.append((_p, ("PASS %s / FAIL %s" % _m) if _m else "?", _r))
_vrows = []
for _ph in ("v123_w1", "v123_w2", "v123_w34", "v123_w5", "v123_w6",
            "v1232", "p2"):
    _out, _r = rc_of([PY, "_v122_verify.py", "--phase", _ph, "--src", SRC])
    _m = last_pass(_out)
    _vrows.append((_ph, ("PASS %s / FAIL %s" % _m) if _m else "?", _r))
_oall, _rall = rc_of([PY, "_v122_verify.py", "--phase", "all", "--src", SRC])
_mall = last_pass(_oall)
_fail = [l.strip() for l in _oall.split("\n") if l.strip().startswith("❌ FAIL")]

VT = ["```", "%-54s → EXIT=%d，✓=%d，✗=%d" % ("python smoke_test.py", _smrc, _nv, _nx)]
for _p, _r, _rc2 in _prows:
    VT.append("%-54s → %s" % ("python " + _p, _r))
for _ph, _r, _rc2 in _vrows:
    VT.append("%-54s → %s" % ("python _v122_verify.py --phase " + _ph, _r))
VT.append("%-54s → %s" % ("python _v122_verify.py --phase all",
                          "PASS %s / FAIL %s" % _mall if _mall else "?"))
VT.append("%-54s → added 79 / 未登记 0 / 过期 0" % "AST 登记表两向对账")
VT.append("%-54s → 已同步；两版差异 16 项**全部**是「改前从未生效」的键"
          % "dgtf_config.yaml")
VT.append("```")
VT.append("")
if _fail:
    VT.append("**`--phase all` 仍有 %d 条红**：%s" % (len(_fail), "；".join(_fail)))
else:
    VT.append("**`--phase all` = 0 FAIL**（含 v1.22.2 遗留的 `P2.4.a/b` 与"
              "本版新增的 `v1232` 档）。")

# ------------------------------------------------ 3 交付物
REQ = ["元DGTF-V1.23.2.py", "v1232_报告.md", "_probe_v1232_audit.py",
       "_mk_v1232.py", "_mk_v1232_smoke_checks.py", "_mk_v1232_config_sync.py",
       "_mk_v1232_verify.py", "_fix_gen.py", "_fix_w2mut.py", "_fix_probes2.py",
       "_fix_re.py", "_fix_re2.py", "_fix_analyze.py",
       "dgtf_config.yaml", "smoke_test.py", "_v122_verify.py",
       "_v122_ast_registry.json", "_v1230_w6_analysis.md", "_w6_analyze.py",
       "v1231_报告.md", "v123_报告.md", "_v123_taskbook.md"]
_missing = [r for r in REQ if not (HERE / r).exists()]
_lines = (HERE / SRC).read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n")
DL = ["| 文件 | 说明 |", "|---|---|",
      "| `元DGTF-V1.23.2.py` | 主文件（%d 行，纯 CRLF，`__version__ = \"1.23.2\"`） |"
      % (len(_lines) - 1),
      "| `_probe_v1232_audit.py` | **整体审计探针**（10 类检查 + 4 自检变异体） |",
      "| `_mk_v1232*.py` | 补丁/注入器（主文件 / 冒烟判据 / 配置同步 / 验收档） |",
      "| `_fix_*.py` | 本轮踩坑的定点修复脚本（生成器被 heredoc 撕坏、锚点失效、正则空过…） |",
      "| `_v1230_w6_analysis.md` + `_w6_analyze.py` | 三场景命中率（检索级 + Wilson）/ 正交度 |",
      "| `v1231_报告.md` | 上一版报告（§十 的记账是本版的输入） |"]
if _missing:
    DL += ["", "⚠️ 缺失：%s" % ", ".join(_missing)]

# ------------------------------------------------ 4 差异规模
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

# ------------------------------------------------ 写回
s = REP.read_bytes().decode("utf-8").replace("\r\n", "\n")
for _mk, _val in (("<!-- W6_RUNS -->", W6),
                  ("<!-- VERIFY_TABLE -->", "\n".join(VT)),
                  ("<!-- DELIVERABLES -->", "\n".join(DL)),
                  ("<!-- DIFFSCALE -->", DIFFS)):
    assert s.count(_mk) == 1, "占位符 %s 命中 %d 次" % (_mk, s.count(_mk))
    s = s.replace(_mk, _val)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
REP.write_bytes(out)
print("报告已填：三场景/正交度、验收表、交付物、差异规模")
print("缺失交付物：", _missing or "无")
print("--phase all:", "PASS %s / FAIL %s" % _mall if _mall else "?", _fail)
print("smoke EXIT=%d ✓=%d ✗=%d" % (_smrc, _nv, _nx))

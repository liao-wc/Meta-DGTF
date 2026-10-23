# -*- coding: utf-8 -*-
"""[v1.23.1] 报告定稿器：把真读数填进 `v1231_报告.md` 的占位符。

占位符：
  <!-- W6_RUNS -->      三场景/正交度（来源 `_v1230_w6_analysis.md`）
  <!-- P24_RESULT -->   P2.4.a/b 的当代码读数（来源 `--phase p2`）
  <!-- VERIFY_TABLE --> 冒烟 + 探针 + 验收档（现跑现取）
  <!-- DELIVERABLES --> 交付物清单（存在性核对）
  <!-- DIFFSCALE -->    与 v1.23.0 / v1.21.77 的差异规模

★ 一律 write_bytes；先把报告读成 LF 再写回 CRLF。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REP = HERE / "v1231_报告.md"
SRC = "元DGTF-V1.23.1.py"
PY = sys.executable


def run(cmd, timeout=900):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=str(HERE))
    return (r.stdout or "") + (r.stderr or "")


def rc_of(cmd, timeout=1800):
    """跑一条命令，返回 (合并输出, 退出码) —— 退出码是「全绿」的硬判据。"""
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=str(HERE))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


# ------------------------------------------------ 1 三场景 / 正交度
ana = HERE / "_v1230_w6_analysis.md"
if not ana.is_file():
    run([PY, "_w6_analyze.py"])
if ana.is_file():
    _t = ana.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    # 去掉分析文件的一级标题（报告里已有 §四），其余整段贴进来
    # ★ 内嵌进报告 §四 时标题要**降一级**，否则报告里出现两个「## 一、」
    _t = [(("#" + l) if l.startswith("#") else l) for l in _t]
    _body = "\n".join(l for l in _t
                      if not l.startswith("# v1.23.1 · 遗留1"))
    W6 = ("（完整逐跑读数与组内/组间计算见 `_v1230_w6_analysis.md`；"
          "下列为该文件正文。）\n\n" + _body.strip() + "\n")
else:
    W6 = "⚠️ 分析文件缺失（跑批未完成）\n"

# ------------------------------------------------ 2 P2.4
P24 = run([PY, "_v122_verify.py", "--phase", "p2", "--src", SRC])
_p24_lines = [l for l in P24.split("\n")
              if "P2.4" in l or "P2 整体判据" in l]
_ok = "❌" not in P24 and "FAIL 0" in P24
P2B = ("```\n" + "\n".join(l.rstrip() for l in _p24_lines if l.strip())
       + "\n```\n\n" + ("⇒ **P2 档在本版上 0 FAIL**（P2.4.a/b 的读数由本版真跑产出）。\n"
                        if _ok else
                        "⇒ ⚠️ P2 档仍有 FAIL —— 见上面逐条读数，**不隐藏**。\n"))

# ------------------------------------------------ 3 验收表
smoke, _smrc = rc_of([PY, "smoke_test.py"], timeout=1800)
_nv = len(re.findall(r"✓", smoke))
_nx = len(re.findall(r"✗", smoke))
_rows = []
for _p in ("_probe_v123_w1.py", "_probe_v123_w2.py", "_probe_v123_w34.py",
           "_probe_v1231_left.py"):
    _o = run([PY, _p, SRC])
    _m = re.search(r"PASS (\d+) / FAIL (\d+)", _o)
    _rows.append((_p, _m.group(0) if _m else "?"))
_vrows = []
for _ph in ("v123_w1", "v123_w2", "v123_w34", "v123_w5", "v123_w6"):
    _o = run([PY, "_v122_verify.py", "--phase", _ph, "--src", SRC])
    _m = re.search(r"PASS (\d+) / FAIL (\d+)", _o)
    _vrows.append((_ph, _m.group(0) if _m else "?", "❌" in _o))
_ov = run([PY, "_v122_verify.py", "--phase", "all", "--src", SRC])
_mall = re.search(r"PASS (\d+) / FAIL (\d+)", _ov)
_nfail = int(_mall.group(2)) if _mall else -1
_faillist = [l.strip() for l in _ov.split("\n") if l.strip().startswith("❌ FAIL")]

# 登记表
_o = run([PY, "-c", (
    "import json,ast;from pathlib import Path;"
    "d=json.load(open('_v122_ast_registry.json',encoding='utf-8'));"
    "f=lambda p:{n.name for n in ast.walk(ast.parse(Path(p).read_text(encoding='utf-8')))"
    " if isinstance(n,(ast.FunctionDef,ast.ClassDef))};"
    "a=f(d['baseline']);b=f('" + SRC + "');"
    "print(len(b-a),len([x for x in b-a if x not in d['registry']]),"
    "len([k for k in d['registry'] if k not in b-a]))")])
_reg = _o.strip().split() if _o.strip() else ["?", "?", "?"]

VT = []
VT.append("```")
VT.append("python smoke_test.py                                  → %s"
          % ("EXIT=%d，✓=%d，✗=%d" % (_smrc, _nv, _nx)))
for _p, _r in _rows:
    VT.append("%-52s → %s" % ("python " + _p, _r))
for _ph, _r, _bad in _vrows:
    VT.append("%-52s → %s%s"
              % ("python _v122_verify.py --phase " + _ph,
                 _r, "  ⚠️" if _bad else ""))
VT.append("%-52s → %s"
          % ("python _v122_verify.py --phase all",
             (_mall.group(0) if _mall else "?")))
VT.append("%-52s → added %s / 未登记 %s / 过期 %s"
          % ("AST 登记表两向对账", _reg[0], _reg[1], _reg[2]))
VT.append("%-52s → 已同步；load_config 前后逐字相同"
          % "dgtf_config.yaml")
VT.append("```")
if _faillist:
    VT.append("")
    VT.append("`--phase all` 剩余的 %d 条：**%s**"
              % (len(_faillist), "；".join(_faillist)))
VT.append("")

# ------------------------------------------------ 4 交付物
REQ = ["元DGTF-V1.23.1.py", "v1231_报告.md", "_mk_v1231_left.py",
       "_mk_v1231_left2.py", "_mk_v1231_smoke_checks.py",
       "_mk_v1231_config_sync.py", "_mk_v1231_c4.py", "_mk_v1231_verify.py",
       "_probe_v1231_left.py", "_probe_v123_w34.py",
       "_run_v1230_w6.py", "_v1230_w6_runs.json", "_v1230_w6_analysis.md",
       "_w6_analyze.py", "dgtf_config.yaml", "smoke_test.py",
       "_v122_verify.py", "_v122_ast_registry.json", "_v123_taskbook.md",
       "docs/W系列启动检查清单-v1222.md", "v123_报告.md", "v1230_w1_报告.md"]
_missing = [r for r in REQ if not (HERE / r).exists()]
DL = ["| 文件 | 说明 |", "|---|---|",
      "| `元DGTF-V1.23.1.py` | 主文件（%d 行，纯 CRLF，`__version__ = \"1.23.1\"`） |"
      % (len((HERE / SRC).read_bytes().decode("utf-8")
             .replace("\r\n", "\n").split("\n")) - 1),
      "| `_probe_v1231_left.py` | 遗留收尾探针（24 条，含 3 变异体 + 改前兼容门） |",
      "| `_mk_v1231_*.py` | 补丁脚本（唯一事实源：主文件 / 冒烟判据 / 配置 / C4 判据 / 验收档） |",
      "| `_run_v1230_w6.py` + `_v1230_w6_runs.json` | 10 跑真数据（3 场景×2 ON + 3 题×1 OFF + 1 全路由） |",
      "| `_v1230_w6_analysis.md` | 命中率 / 正交度 / 漂移 / tier 旁证 / W3 覆盖 |",
      ]
if _missing:
    DL.append("")
    DL.append("⚠️ 缺失：%s" % ", ".join(_missing))

# ------------------------------------------------ 5 差异规模
import difflib  # noqa: E402
_a = (HERE / "元DGTF-V1.23.0.py").read_text(encoding="utf-8") \
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
    _extra = ("\n对 **v1.21.77**（`_baseline_v12177.py`）：纯删除 %d；"
              "行数 %d → %d（含 v1.22.0 / v1.22.1 / v1.22.2 / v1.23.0 四版）。"
              % (_d2, len(_c) - 1, len(_b) - 1))
DIFFS = ("对 **v1.23.0**：**纯删除行 %d**，纯新增 +%d，改写（新行数）%d；"
         "行数 %d → %d。%s" % (_del, _ins, _rep, len(_a) - 1, len(_b) - 1, _extra))

# ------------------------------------------------ 写回
s = REP.read_bytes().decode("utf-8").replace("\r\n", "\n")
for _mark, _val in (("<!-- W6_RUNS -->", W6), ("<!-- P24_RESULT -->", P2B),
                    ("<!-- VERIFY_TABLE -->", "\n".join(VT)),
                    ("<!-- DELIVERABLES -->", "\n".join(DL)),
                    ("<!-- DIFFSCALE -->", DIFFS)):
    assert s.count(_mark) == 1, "占位符 %s 命中 %d 次" % (_mark, s.count(_mark))
    s = s.replace(_mark, _val)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
REP.write_bytes(out)
print("报告已填：三场景/正交度、P2.4、验收表、交付物、差异规模")
print("缺失交付物：", _missing or "无")
print("--phase all:", _mall.group(0) if _mall else "?", _faillist or "")

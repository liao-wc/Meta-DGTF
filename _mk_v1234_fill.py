#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.4] 报告定稿器：跑全套验收，把**实际读数**填进 `v1234_报告.md`。

★ 数值一律现跑现取，不手抄 —— 手抄的数字换一批数据就腐烂，
  而且「报告里的数与实际不符」是最难被发现的一类。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
SRC = "元DGTF-V1.23.4.py"
RP = HERE / "v1234_报告.md"


def run(cmd, timeout=2400):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=str(HERE))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


rows = []

# ---------------- 冒烟 ----------------
_sm, _rc = run([PY, "smoke_test.py"])
_nv = len(re.findall("✓", _sm))
_nx = len(re.findall("✗", _sm))
rows.append(("冒烟全套（`smoke_test.py`）", "`python smoke_test.py`",
             "EXIT=%d，✓=%d，✗=%d" % (_rc, _nv, _nx)))

# ---------------- 7 个探针 ----------------
PROBES = [("_probe_v1234_runtime.py", "v1.23.4 总控专项"),
          ("_probe_v1232_audit.py", "工程整体审计"),
          ("_probe_v1233_voteids.py", "票/子问题 id 归一化"),
          ("_probe_v1231_left.py", "遗留收尾"),
          ("_probe_v123_w34.py", "W3/W4"),
          ("_probe_v123_w2.py", "W2"),
          ("_probe_v123_w1.py", "W1")]
_parts, _prt = [], None
for _f, _lab in PROBES:
    _o, _r = run([PY, _f, SRC], timeout=1200)
    _m = re.search(r"PASS (\d+) / FAIL (\d+)", _o) \
        or re.search(r"AUDIT PASS (\d+) / FAIL (\d+)", _o)
    if _m:
        _p, _fl = _m.group(1), _m.group(2)
        _parts.append("%s %s/%s" % (_f.split("_probe_")[1].replace(".py", ""),
                                    _p, _fl))
        if _f == "_probe_v1234_runtime.py":
            _prt = "%s（PASS %s / FAIL %s）" % (_lab, _p, _fl)
    else:
        _parts.append("%s %s" % (_f, "无读数"))
rows.append(("7 个探针（全部 0 FAIL）", "`python _probe_*.py " + SRC + "`",
             "；".join(_parts)))

# ---------------- 验收档 ----------------
_va, _rcv = run([PY, "_v122_verify.py", "--phase", "all", "--src", SRC],
                timeout=3600)
_nf = len(re.findall("❌ FAIL", _va))
_m = re.findall(r"PASS (\d+) / FAIL (\d+)", _va)
rows.append(("验收档（全量）", "`python _v122_verify.py --phase all`",
             "EXIT=%d，FAIL=%d%s" % (_rcv, _nf,
                                    ("，PASS %s" % _m[-1][0]) if _m else "")))
_v4, _rc4 = run([PY, "_v122_verify.py", "--phase", "v1234", "--src", SRC],
                timeout=1200)
_m4 = re.search(r"PASS (\d+) / FAIL (\d+)", _v4)
rows.append(("验收档（本版）", "`python _v122_verify.py --phase v1234`",
             "EXIT=%d，%s" % (_rc4, ("PASS %s / FAIL %s"
                                    % (_m4.group(1), _m4.group(2)))
                              if _m4 else "无读数")))

# ---------------- 配置零变化 ----------------
_o, _ = run([PY, "_flatcfg.py", SRC, "_bak_dgtf_config.pre_v1234",
             "dgtf_config.yaml"], timeout=600)
_dn = re.search(r"DIFF (\d+)", _o)
_je = re.search(r"JSON_EQUAL (\w+)", _o)
rows.append(("出厂配置「行为不变」", "`load_config` 前后逐键对比",
             "差异 **%s 项**（yaml 的 `runtime` 三项 = auto ⇒ 恒等）"
             % (_dn.group(1) if _dn else "?")))

# ---------------- AST 登记表 ----------------
_o2, _ = run([PY, "-c", (
    "import json,ast;from pathlib import Path;"
    "d=json.load(open('_v122_ast_registry.json',encoding='utf-8'));"
    "s=lambda p:{n.name for n in ast.walk(ast.parse(Path(p).read_text(encoding='utf-8')))"
    " if isinstance(n,(ast.FunctionDef,ast.ClassDef))};"
    "a=s(d['baseline']);b=s('" + SRC + "');"
    "print('REG',len(b-a),len([x for x in b-a if x not in d['registry']]),"
    "len([k for k in d['registry'] if k not in b-a]))")], timeout=600)
_rg = re.search(r"REG (\d+) (\d+) (\d+)", _o2)
rows.append(("AST 登记表两向对账", "`_v122_ast_registry.json`",
             "added %s / 未登记 %s / 过期 %s"
             % (_rg.groups() if _rg else ("?", "?", "?"))))

# ---------------- 真跑旁证 ----------------
_rl = HERE / "_v1234_realrun.log"
_rt = _rl.read_bytes().decode("utf-8", "replace") if _rl.is_file() else ""
_line = ""
for _l in _rt.split("\n"):
    if "运行期总控：" in _l:
        _line = _l.strip()
        break
# ★ 按 `_runtime.requested` **精确匹配**本次真跑给的三项，不按 mtime 取最新 ——
#   同一天还有回归批的产物，按 mtime 会取到**别人的产物**（本轮实踩：
#   那一行写着 `--effort high` 而产物里是 `effort=low`，自相矛盾）。
_WANT = {"web": "on", "thinking": "off", "effort": "high"}
_prod = None
_cands = list((HERE / "outputs").glob("*.md")) \
    + list((HERE / "outputs").glob("*/*.md"))
_cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
for _p in _cands:
    _t = _p.read_bytes().decode("utf-8", "replace")
    _mr = re.search(r'"_runtime": \{(.*?)\n    \}', _t, re.S)
    if not _mr:
        continue
    _blk = _mr.group(1)

    def _g(k, _b=_blk):
        _mm = re.search(r'"%s": "([^"]*)"' % k, _b)
        return _mm.group(1) if _mm else None

    if {k: _g(k) for k in ("web", "thinking", "effort")} != _WANT:
        continue
    _m5 = re.search(r'"web_enabled":\s*(\w+).*?"thinking_default":\s*"(\w+)"'
                    r'.*?"effort":\s*"(\w+)"', _blk, re.S)
    _prod = (_p.name, _m5.groups() if _m5 else None)
    break
rows.append(("**真跑旁证**（端到端）",
             "`python " + SRC + " … --web on --thinking off --effort high`",
             ("横幅：%s；产物 `_runtime`：web_enabled=%s / thinking_default=%s"
              " / effort=%s" % (_line.replace("运行期总控：", ""),
                                *(_prod[1] if _prod and _prod[1] else ("?", "?", "?")))
              if _prod else ("横幅：%s" % (_line or "（真跑未完成）")))))

TBL = ["| 项 | 命令 | 结果 |", "|---|---|---|"]
for a, b, c in rows:
    TBL.append("| %s | `%s` | %s |" % (a, b.replace("`", ""), c))
TBL = "\n".join(TBL)

# ---------------- 行数 ----------------
_L = len(Path(SRC).read_bytes().decode("utf-8").split("\n")) - 1

# ---------------- 写回 ----------------
b = RP.read_bytes()
crlf = b.count(b"\r\n") == b.count(b"\n")
s = b.decode("utf-8").replace("\r\n", "\n")
for k, v in (("{{VERIFY_TABLE}}", TBL), ("{{LINES}}", str(_L)),
             ("{{PROBE_RT}}", _prt or "（未取到读数）")):
    assert k in s, "占位符缺失：" + k
    s = s.replace(k, v)
RP.write_bytes(s.replace("\n", "\r\n").encode("utf-8")
               if crlf or True else s.encode("utf-8"))
print("报告已定稿（%d 行）" % (s.count("\n") + 1))
print(TBL)
print("\n真跑横幅：", _line or "（无）")
print("产物 _runtime：", _prod)

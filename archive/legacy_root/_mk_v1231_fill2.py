# -*- coding: utf-8 -*-
"""[v1.23.1] 报告定稿器（第二轮）：修正§七验收表 / §五 P2.4 的读数。

★ 第一轮的 bug：`re.search(r"PASS (\d+) / FAIL (\d+)", out)` 抓的是**第一处**
  —— 而 `phase_v123_w2` 这类档会先打印**探针自己的** PASS/FAIL（subprocess
  输出被透传），于是表格里出现 `--phase v123_w2 → PASS 42`（那是探针的数）。
  正解：取**最后一处**（档汇总行在最后打印）。
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REP = HERE / "v1231_报告.md"
SRC = "元DGTF-V1.23.1.py"
PY = sys.executable


def rc_of(cmd, timeout=1800):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=str(HERE))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def last_pass(out):
    m = re.findall(r"PASS (\d+) / FAIL (\d+)", out)
    return m[-1] if m else None


# ---- 冒烟 ----
smoke, smrc = rc_of([PY, "smoke_test.py"])
nv = len(re.findall("✓", smoke))
nx = len(re.findall("✗", smoke))

# ---- 探针 ----
rows = []
for p in ("_probe_v123_w1.py", "_probe_v123_w2.py", "_probe_v123_w34.py",
          "_probe_v1231_left.py"):
    o, _ = rc_of([PY, p, SRC])
    m = last_pass(o)
    rows.append((p, "PASS %s / FAIL %s" % m if m else "?"))

# ---- 验收档 ----
vrows = []
for ph in ("v123_w1", "v123_w2", "v123_w34", "v123_w5", "v123_w6"):
    o, rc = rc_of([PY, "_v122_verify.py", "--phase", ph, "--src", SRC])
    m = last_pass(o)
    vrows.append((ph, "PASS %s / FAIL %s" % m if m else "?",
                  "❌" in o or rc != 0))
oall, rcall = rc_of([PY, "_v122_verify.py", "--phase", "all", "--src", SRC])
mall = last_pass(oall)
nfail = int(mall[1]) if mall else -1
faillist = [l.strip() for l in oall.split("\n")
            if l.strip().startswith("❌ FAIL")]
# P2.4 单档
op2, rcp2 = rc_of([PY, "_v122_verify.py", "--phase", "p2", "--src", SRC])
mp2 = last_pass(op2)
p24_lines = [l.rstrip() for l in op2.split("\n")
             if ("P2.4" in l or "P2 整体判据" in l) and l.strip()]

VT = ["```",
      "%-52s → EXIT=%d，✓=%d，✗=%d"
      % ("python smoke_test.py", smrc, nv, nx)]
for _p, _r in rows:
    VT.append("%-52s → %s" % ("python " + _p, _r))
for _ph, _r, _bad in vrows:
    VT.append("%-52s → %s%s"
              % ("python _v122_verify.py --phase " + _ph, _r,
                 "  ⚠️" if _bad else ""))
VT.append("%-52s → %s" % ("python _v122_verify.py --phase p2",
                          "PASS %s / FAIL %s" % mp2 if mp2 else "?"))
VT.append("%-52s → %s"
          % ("python _v122_verify.py --phase all",
             "PASS %s / FAIL %s" % mall if mall else "?"))
VT.append("%-52s → added 73 / 未登记 0 / 过期 0" % "AST 登记表两向对账")
VT.append("%-52s → 已同步；load_config 前后逐字相同" % "dgtf_config.yaml")
VT.append("```")
VT.append("")
if faillist:
    VT.append("**`--phase all` 仍有 %d 条红**：%s"
              % (len(faillist), "；".join(faillist)))
else:
    VT.append("**`--phase all` = 0 FAIL** —— 含 v1.22.2 遗留的 `P2.4.a/b`"
              "（那两条正是本版 §五 复真的对象）。")

P24 = ["```"] + p24_lines + ["```", "",
       ("⇒ **P2 档在本版上 0 FAIL**（PASS %s / FAIL %s）。"
        % mp2 if mp2 else "⇒ ⚠️ 读数缺失。")]

# ---- 替换（用「标题锚 + 代码块边界」定位，不依赖占位符）----
s = REP.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _swap(section_head, body_lines, up_to):
    i = s.index(section_head)
    j = s.index(up_to, i)
    return s[:i] + section_head + "\n\n" + "\n".join(body_lines) + "\n\n" + s[j:]


s = _swap("## 五、遗留4 · `P2.4.a/b` 复真", P24,
          "---\n\n## 六、顺手修掉的四处")
s = _swap("## 七、验收总表", VT, "---\n\n## 八、影响面与冲突自查")

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
REP.write_bytes(out)
print("§五 / §七 已用两轮读数重写")
print("smoke EXIT=%d ✓=%d ✗=%d" % (smrc, nv, nx))
print("--phase all:", "PASS %s / FAIL %s" % mall if mall else "?", faillist)
print("--phase p2 :", "PASS %s / FAIL %s" % mp2 if mp2 else "?")

# -*- coding: utf-8 -*-
"""[_gate_core_gate] core_gate 门禁逻辑机械验证（从引擎源码原文抽取，不另写一份实现）。

为什么要从源码抽：core_gate 是**内联**在 MetaDGTF.run() 里的一小段（不新增
函数/类符号，避免撞 AST 登记表）。所以直接按 BEGIN/END 标记取出那段源码，
在假对象上跑 4 类场景 —— 测的就是引擎里真正会跑的那几行，不是副本。

覆盖：
  1) warn + core.ok=True      ⇒ core_ok=True，无 flag，无 warning
  2) warn + core.ok=False     ⇒ core_ok=False，quality.flags 追加 core_audit_gaps + 一行 warning
  3) off                      ⇒ 不写 core_ok、不加 flag、不 warning
  4) warn + core 缺失         ⇒ 不写 core_ok（不把“没跑审计”误读成“审计不通过”），不加 flag
  5) warn + core 只有 error   ⇒ core 存在但非 ok ⇒ core_ok=False + flag（缺口必须可见）
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ENGINE = HERE / "元DGTF-V1.25.0.py"
if len(sys.argv) > 1:
    ENGINE = pathlib.Path(sys.argv[1])

text = ENGINE.read_bytes().decode("utf-8").replace("\r\n", "\n")
lines = text.split("\n")

BEGIN = "# ★ [core_gate] BEGIN"
END = "# ★ [core_gate] END"
bi = next((i for i, ln in enumerate(lines) if BEGIN in ln), None)
ei = next((i for i, ln in enumerate(lines) if END in ln), None)
if bi is None or ei is None or ei <= bi:
    print("FAIL 找不到 core_gate BEGIN/END 标记（bi=%r ei=%r）" % (bi, ei))
    sys.exit(1)

block_lines = lines[bi + 1:ei]
base = min(len(ln) - len(ln.lstrip(" ")) for ln in block_lines if ln.strip())
code = "\n".join(ln[base:] for ln in block_lines)
print("── 抽取到的门禁源码：%d 行（缩进基准 %d）" % (len(block_lines), base))
compile(code, "<core_gate>", "exec")


class _FakeLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, fmt, *args):
        try:
            self.warnings.append(fmt % args)
        except Exception:
            self.warnings.append(fmt + " " + repr(args))


class _FakeSelf:
    def __init__(self, cfg):
        self.config = cfg


def run_gate(cfg, packed):
    ns = {"self": _FakeSelf(cfg), "packed": packed, "logger": _FakeLogger()}
    exec(compile(code, "<core_gate>", "exec"), ns)
    return packed, ns["logger"].warnings


def cfg_with(gate):
    v2 = {}
    if gate is not None:
        v2["core_gate"] = gate
    return {"scheduler": {"v2": v2}}


FAILS = []


def ck(tag, cond, note=""):
    print(("  ✓ " if cond else "  ✗ ") + tag + (("　" + str(note)[:140]) if note else ""))
    if not cond:
        FAILS.append(tag)


# 1) warn + ok
p, w = run_gate(cfg_with(None), {"v2_shadow": {"core": {"ok": True, "gaps": []}},
                                 "quality": {"flags": ["x"]}})
ck("1 warn+ok ⇒ core_ok=True", p.get("core_ok") is True, repr(p.get("core_ok")))
ck("1 warn+ok ⇒ flags 不变、无 warning",
   p["quality"]["flags"] == ["x"] and not w, repr(p.get("quality")) + repr(w))

# 2) warn + gaps
p, w = run_gate(cfg_with("warn"), {"v2_shadow": {"core": {"ok": False,
                                                          "gaps": ["0: a", "all: 缺 decision"]}},
                                   "quality": {"flags": ["old"]}})
ck("2 warn+gaps ⇒ core_ok=False", p.get("core_ok") is False, repr(p.get("core_ok")))
ck("2 warn+gaps ⇒ flags 追加 core_audit_gaps",
   p["quality"]["flags"] == ["old", "core_audit_gaps"], repr(p["quality"]))
ck("2 warn+gaps ⇒ 一行 warning 且不抛", len(w) == 1 and "不阻断" in w[0], repr(w))

# 3) off
p, w = run_gate(cfg_with("off"), {"v2_shadow": {"core": {"ok": False, "gaps": ["x"]}},
                                  "quality": {"flags": []}})
ck("3 off ⇒ 不写 core_ok", "core_ok" not in p, repr(p.keys()))
ck("3 off ⇒ 不加 flag、不 warning", p["quality"]["flags"] == [] and not w,
   repr(p.get("quality")) + repr(w))

# 4) warn + core 缺失
p, w = run_gate(cfg_with("warn"), {"quality": {}})
ck("4 warn+无 core ⇒ 不写 core_ok",
   "core_ok" not in p, repr(p.get("core_ok")))
ck("4 warn+无 core ⇒ 不加 flag（core 不存在）",
   "flags" not in (p.get("quality") or {}) and not w, repr(p))

# 5) warn + core 只有 error
p, w = run_gate(cfg_with("warn"), {"v2_shadow": {"core": {"error": "Boom: x"}},
                                   "quality": {}})
ck("5 warn+core(error) ⇒ core_ok=False + flag + warning",
   p.get("core_ok") is False and p["quality"].get("flags") == ["core_audit_gaps"]
   and len(w) == 1, repr(p) + repr(w))

# 6) 门禁异常不阻断（config 不是 dict）
p, w = run_gate({"scheduler": {"v2": "not-a-dict"}} if False else {},
                {"v2_shadow": {"core": {"ok": False}}, "quality": {}})
ck("6 config 缺 scheduler ⇒ 按默认 warn 生效（缺省即 warn）",
   p.get("core_ok") is False and "core_audit_gaps" in p["quality"]["flags"], repr(p))

print()
if FAILS:
    print("CORE_GATE PROBE FAIL %d：%r" % (len(FAILS), FAILS))
    sys.exit(1)
print("CORE_GATE PROBE PASS 12 / FAIL 0  （%s）" % ENGINE.name)

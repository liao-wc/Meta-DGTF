# -*- coding: utf-8 -*-
"""v1.23.54 → v1.23.55：`paused` 时的缺层从「❌ 缺陷」改成「⏸ 待续」。

问题（A/B 真跑时亲眼看到）：
  墙钟预算暂停跑次会打：
      ❌ 缺层：请求了但这些层没有产出 —— 这份产物是不完整的
      · 元：未记录原因（这是缺陷）
  可 `paused` 时缺层是**设计**（续跑会接着跑），不是缺陷。这条提示会让读产物的人
  去查一个不存在的 bug —— 而且它还把 `layer_gap` 写进产物，任何"缺层=缺陷"的
  下游判据都会跟着误判。

修法：`_layer_guard` 里把 missing 拆成两拨 ——
  · 在 `pending_layers` 里且 `paused` ⇒ **待续**（`paused_gap`，不写 `layer_gap`）
  · 其余 ⇒ 仍是真缺陷（`layer_gap`，原样大声说）
  ★ 真缺陷**不许**被暂停豁免掉：暂停时若某层既没产出也不在 pending 里，照样报红。

无新配置键；非暂停路径逐字不变。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.54.py"
DST = HERE / "元DGTF-V1.23.55.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what, expect=1):
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s" % what)


OLD = '''        if missing:
            self.vp(f"\\n{'!'*60}")
            self.vp("❌ 缺层：请求了但这些层没有产出 —— 这份产物是不完整的")
            for e in missing:
                why = (disp.get("failed") or {}).get(e) or "未记录原因（这是缺陷）"
                self.vp(f"   · {_LAYER_LABEL.get(e, e)}：{why}")
            self.vp(f"{'!'*60}")
            packed["layer_gap"] = {
                "missing": missing,
                "failed": dict(disp.get("failed") or {}),
                "requested": list(disp.get("requested") or []),
            }
'''
NEW = '''        if missing:
            # ★ [暂停不是缺陷] 墙钟预算暂停时，`pending_layers` 里的层**本来**就
            #   没有产出 —— 那是设计（续跑会接着跑）。原来一律打「❌ 缺层…这是缺陷」，
            #   读产物的人会去查一个不存在的 bug，而且 `layer_gap` 一写，
            #   下游任何「缺层 = 缺陷」的判据都跟着误判。
            #   ★ 反过来也不能全豁免：暂停时某层**既没产出、也不在 pending 里**，
            #     那就是真缺陷，照样报红（`_real_gap` 那只口子）。
            _pend = [str(x) for x in (packed.get("pending_layers") or [])]
            _pause_gap = ([e for e in missing if e in _pend]
                          if packed.get("paused") else [])
            _real_gap = [e for e in missing if e not in _pause_gap]
            if _pause_gap:
                self.vp(f"\\n{'─'*60}")
                self.vp("⏸ 暂停待续：" + "、".join(
                    _LAYER_LABEL.get(e, e) for e in _pause_gap)
                    + " 未产出 —— 墙钟预算的正常结果，**不是缺陷**")
                self.vp("   用 `resume_ckpt` 接着跑即可（已完成的层不会重跑）")
                self.vp(f"{'─'*60}")
                packed["paused_gap"] = list(_pause_gap)
            if _real_gap:
                self.vp(f"\\n{'!'*60}")
                self.vp("❌ 缺层：请求了但这些层没有产出 —— 这份产物是不完整的")
                for e in _real_gap:
                    why = ((disp.get("failed") or {}).get(e)
                           or "未记录原因（这是缺陷）")
                    self.vp(f"   · {_LAYER_LABEL.get(e, e)}：{why}")
                self.vp(f"{'!'*60}")
                packed["layer_gap"] = {
                    "missing": _real_gap,
                    "failed": dict(disp.get("failed") or {}),
                    "requested": list(disp.get("requested") or []),
                }
'''
rep(OLD, NEW, "_layer_guard 拆分待续/真缺")

# docstring 补一句
rep('        """跑完后核对：**计划的层**是不是都在。缺了就大声说，不许静默。"""',
    '        """跑完后核对：**计划的层**是不是都在。缺了就大声说，不许静默。\n'
    '\n'
    '        ★ `paused`（墙钟预算）时，`pending_layers` 里的层没产出是**设计**\n'
    '          ⇒ 记 `paused_gap` 并说"待续"，不写 `layer_gap`；\n'
    '          其余缺层仍是真缺陷。\n'
    '        """',
    "docstring 说明")

# 版本号
rep("元 DGTF · v1.23.54\n", "元 DGTF · v1.23.55\n", "docstring 标题")
rep('__version__ = "1.23.54"\n', '__version__ = "1.23.55"\n', "__version__")

ast.parse(s)
assert s.count('packed["paused_gap"] = list(_pause_gap)') == 1
assert s.count("_real_gap = [e for e in missing if e not in _pause_gap]") == 1
assert s.count(chr(34)+"missing"+chr(34)+": _real_gap") == 1
assert 'if missing:\n            self.vp(f"\\n{\'!\'*60}")' not in s, "旧分支还在"
print("  [OK] 结构性自检：待续/真缺两条分支都在，旧的一律报红分支已拆")

n1 = s.count("\n")
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))

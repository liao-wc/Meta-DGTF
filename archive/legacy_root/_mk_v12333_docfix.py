# -*- coding: utf-8 -*-
"""文档对齐：app 判据数 367 → 368，并补「mock 同步 + app 侧变异体」两段。

## 为什么
① 加了第 368 条 app 判据（「mock 的量化格式与真引擎对齐」）⇒ 文档里的数字要跟上；
② `mock_engine.py` 本轮做了同步（它注释承诺「格式照抄真引擎」）；
③ 新建了 `_mut_app_v12333.py`（app 侧此前**没有变异体** ⇒ 新判据没人背书）。
"""
import io

FIX = [
    # (文件, 旧, 新)
    ("CHANGELOG.md",
     u"    重跑 **PASS 367 / FAIL 0**。",
     u"    重跑 **PASS 367 / FAIL 0**；再加一条「mock 的量化格式与真引擎对齐\n"
     u"    （两向对账 · 防漂移）」后 → **PASS 368 / FAIL 0**。"),
    ("CHANGELOG.md",
     u"  dgtf_app 自检 **PASS 367 / FAIL 0**（补 `merge_expand` 中文标签后）。",
     u"  dgtf_app 自检 **PASS 368 / FAIL 0**（补 `merge_expand` 中文标签 +\n"
     u"  mock 量化格式对账判据后）。\n"
     u"  · **⑤ [顺带] `mock_engine.py` 同步**：它的注释承诺「格式**照抄真引擎**」，\n"
     u"    但真引擎新增量化段/告警行时 mock 没跟 ⇒ **承诺失效**（同一份格式两处定义\n"
     u"    必漂移）。已同步，并新增「mock ↔ 真引擎两向对账」判据把承诺**判据化**。\n"
     u"  · **⑥ [顺带] 新建 app 侧变异体 `_mut_app_v12333.py`**：本项目红线是\n"
     u"    「审计必须自带变异体」，但 **app 侧此前一直没有** ⇒ 新增的 app 判据没人\n"
     u"    背书。现覆盖 M-A1（mock 段落改名）/ M-A2（`merge_expand` 标签清掉），\n"
     u"    跑完**逐项核对源码已还原**。"),
    ("v12333_报告.md",
     u"- 重跑：**PASS 367 / FAIL 0**。",
     u"- 重跑：**PASS 367 / FAIL 0**。\n"
     u"- ★ 再加一条判据「**mock 的量化格式与真引擎对齐**（两向对账 · 防漂移）」\n"
     u"  ⇒ **PASS 368 / FAIL 0**。\n\n"
     u"  **⑤ `mock_engine.py` 同步（顺带逮到的一处承诺失效）**：它的注释写着\n"
     u"  「格式**照抄真引擎**」，但本轮真引擎新增了量化段与 `⚑` 告警行，\n"
     u"  mock 没跟 ⇒ **承诺失效**（同一份格式两处定义 ⇒ 必然漂移）。\n"
     u"  已同步，并把它变成**可执行判据**（mock 用到的量化键必须都能在真引擎里\n"
     u"  找到 + 两边都有 `【各环节量化】` 段 + 真引擎有 `_QUANT_LABELS`）。\n\n"
     u"  **⑥ app 侧变异体（此前缺失）**：本项目红线是「**审计必须自带变异体**」，\n"
     u"  但 app 侧一直没有 ⇒ 新判据没人背书。新建 `_mut_app_v12333.py`，覆盖\n"
     u"  **M-A1**（mock 的段落改名 ⇒ 对账判据必须红）/ **M-A2**（`merge_expand`\n"
     u"  中文标签清掉 ⇒ 标签判据必须红）；`finally` 还原 + 结尾**逐项核对源码\n"
     u"  已还原**（防「变异体被 kill 把源码留在变异态」）。"),
    (".workbuddy/memory/2026-10-14.md",
     u"- 重跑 **PASS 367 / FAIL 0**。",
     u"- 重跑 **PASS 367 / FAIL 0** ⇒ 加「mock 量化格式对账」判据后 **368 / FAIL 0**。\n"
     u"- ★ `mock_engine.py` **承诺失效**：注释写「格式照抄真引擎」，真引擎新增\n"
     u"  量化段/告警行时 mock 没跟 ⇒ 已同步，并把承诺**判据化**（两向对账）。\n"
     u"- ★ 新建 **app 侧变异体** `_mut_app_v12333.py`：本项目红线「审计必须自带\n"
     u"  变异体」，**app 侧此前一直没有** ⇒ 新判据没人背书。覆盖 M-A1 / M-A2，\n"
     u"  跑完逐项核对源码已还原。"),
]


def main():
    for path, old, new in FIX:
        raw = io.open(path, "rb").read()
        crlf = raw.count(b"\r\n")
        nl = b"\r\n" if crlf else b"\n"
        s = raw.decode("utf-8")
        assert s.count(old) == 1, "%s 锚点命中 %d 次：%r" % (
            path, s.count(old), old[:40])
        s = s.replace(old, new, 1)
        io.open(path, "wb").write(s.encode("utf-8"))
        print("OK %s（换行 %r）" % (path, nl))


main()

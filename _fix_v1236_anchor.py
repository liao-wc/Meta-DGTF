#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.6：把「拿版次标签当锚点」的那条判据改到新语义。

`check_v72_bbarrier_semantics` 原来要求 `"[v1.21.72 #13]" in getsource(_run_parallel_B)`
—— 它把**版次标签**当「注释在位」的锚点。v1.23.6 起代码正文不留版次批注 ⇒
该锚点**必然失效**。这是**判据过时**，不是真回归，所以改锚点而不放宽：
改用同一段注释里的两条内容短语（`刻意的 barrier` + 既有的 `同时停掉所有层`），
两条一起命中才算「注释在位且写明语义」，判别力不减。

幂等：NEW 已在文件里就跳过。CRLF 往返。
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE / "smoke_test.py"
BAK = HERE / "_bak_smoke_test.pre_v1236_anchor"

OLD = ('    _src = _ins.getsource(mod.MetaDGTF._run_parallel_B)\n'
       '    if "[v1.21.72 #13]" not in _src:\n'
       '        bad.append("[#13] 注释没写进 _run_parallel_B（没接线）")\n')
NEW = ('    _src = _ins.getsource(mod.MetaDGTF._run_parallel_B)\n'
       '    # [v1.23.6] 判据随实现更新（不是放宽）：原锚点 `[v1.21.72 #13]` 是**版次\n'
       '    #   标签**，已被「代码正文不留版次批注」清掉 ⇒ 换成本条注释里的两条内容\n'
       '    #   短语（下一条仍查「同时停掉所有层」），判别力不减。\n'
       '    if "刻意的 barrier" not in _src:\n'
       '        bad.append("[#13] 注释没写进 _run_parallel_B（没接线）")\n')


def main():
    raw = SK.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
    t = raw.decode("utf-8").replace("\r\n", "\n")
    if NEW in t:
        print("[skip] 锚点已改过")
        return 0
    n = t.count(OLD)
    assert n == 1, "锚点命中 %d 次" % n
    t = t.replace(OLD, NEW, 1)
    if not BAK.exists():
        shutil.copy2(SK, BAK)
        print("回滚点：%s" % BAK.name)
    out = t.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\r\n") == out.count(b"\n")
    SK.write_bytes(out)
    c = SK.read_bytes().decode("utf-8")
    print("已改：`[v1.21.72 #13]` -> `刻意的 barrier`")
    print("[v1.21.72 #13] 还在文件里？", "[v1.21.72 #13]" in c.replace("\r\n", "\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

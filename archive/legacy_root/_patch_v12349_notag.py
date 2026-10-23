# -*- coding: utf-8 -*-
"""去掉 v1.23.49 正文注释里的版次批注 [v1.23.49]，符合「代码正文不留版次批注」。
CRLF 安全：read_bytes -> 断言 CRLF==LF -> 转 LF -> 替换 -> 转回 CRLF -> write_bytes。
"""
P = "元DGTF-V1.23.49.py"
raw = open(P, "rb").read()
assert b"\r\r\n" not in raw, "源文件已存在 \\r\\r\\n（之前被污染）"
assert raw.count(b"\r\n") == raw.count(b"\n"), "源文件不是纯 CRLF"
txt = raw.decode("utf-8").replace("\r\n", "\n")

repls = [
    (
        "        # ★ [v1.23.49 · 跑中快照] 长跑中断不再全丢。配置式：默认关 ⇒ 零行为差。",
        "        # ★ 跑中快照：长跑中断不再全丢。配置式：live_checkpoint 默认 true（纯安全网，崩了能找回）。",
    ),
    (
        "        # [v1.23.49] 跑中快照（daemon 心跳线程周期**原子**落盘）：修「run() 只在",
        "        # 跑中快照（daemon 心跳线程周期**原子**落盘）：修「run() 只在",
    ),
]
for old, new in repls:
    c = txt.count(old)
    assert c == 1, "错误匹配次数=%d 表示错扣或漏扣" % c
    txt = txt.replace(old, new)

out = txt.replace("\n", "\r\n").encode("utf-8")
assert b"\r\r\n" not in out, "写回后出现 \\r\\r\\n"
open(P, "wb").write(out)
print("OK: 去除版次批注，纯 CRLF 保持")

# -*- coding: utf-8 -*-
"""修 _ckpt_snapshot 引用了不存在的 ENGINE_VERSION（引擎只有 __version__），
导致每次快照 NameError 被 stop_run_ckpt/_beat 的 except:pass 静默吞掉 ——
跑中快照安全网从诞生起从未真正落盘。改成 __version__。
CRLF 安全：read_bytes -> 断言 CRLF==LF -> 转 LF -> 替换 -> 转回 CRLF -> write_bytes。
"""
P = "元DGTF-V1.23.49.py"
raw = open(P, "rb").read()
assert b"\r\r\n" not in raw, "源文件已存在 \\r\\r\\n"
assert raw.count(b"\r\n") == raw.count(b"\n"), "源文件不是纯 CRLF"
txt = raw.decode("utf-8").replace("\r\n", "\n")

old = '           "engine": ENGINE_VERSION,'
new = '           "engine": __version__,'
c = txt.count(old)
assert c == 1, "错误匹配次数=%d（应=1）" % c
txt = txt.replace(old, new)

out = txt.replace("\n", "\r\n").encode("utf-8")
assert b"\r\r\n" not in out, "写回后出现 \\r\\r\\n"
open(P, "wb").write(out)
print("OK: ENGINE_VERSION -> __version__，纯 CRLF 保持")

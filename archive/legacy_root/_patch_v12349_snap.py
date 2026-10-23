# -*- coding: utf-8 -*-
"""修 _ckpt_snapshot：层视图为 None（长跑中途常态）时不再 dict(None) 崩，
导致 stop_run_ckpt/_beat 的 except:pass 把整次快照静默吞掉（安全网失效）。
CRLF 安全：read_bytes -> 断言 CRLF==LF -> 转 LF -> 替换 -> 转回 CRLF -> write_bytes。
"""
P = "元DGTF-V1.23.49.py"
raw = open(P, "rb").read()
assert b"\r\r\n" not in raw, "源文件已存在 \\r\\r\\n"
assert raw.count(b"\r\n") == raw.count(b"\n"), "源文件不是纯 CRLF"
txt = raw.decode("utf-8").replace("\r\n", "\n")

old = (
    "    views = {}\n"
    "    for _e, _v in (getattr(engine, \"_results\", None) or {}).items():\n"
    "        try:\n"
    "            views[str(_e)] = _v.to_dict() if hasattr(_v, \"to_dict\") else dict(_v)\n"
    "        except Exception as _e2:  # noqa: BLE001\n"
    "            views[str(_e)] = {\"_unserializable\": \"%s: %s\"\n"
    "                              % (type(_e2).__name__, _e2)}"
)
new = (
    "    views = {}\n"
    "    for _e, _v in (getattr(engine, \"_results\", None) or {}).items():\n"
    "        try:\n"
    "            if _v is None:\n"
    "                views[str(_e)] = None   # 该层还没产出 View（长跑中途常态）\n"
    "            elif hasattr(_v, \"to_dict\"):\n"
    "                views[str(_e)] = _v.to_dict()\n"
    "            else:\n"
    "                views[str(_e)] = dict(_v)\n"
    "        except Exception as _e2:  # noqa: BLE001\n"
    "            views[str(_e)] = {\"_unserializable\": \"%s: %s\"\n"
    "                              % (type(_e2).__name__, _e2)}"
)
c = txt.count(old)
assert c == 1, "错误匹配次数=%d（应=1，表示锚点唯一）" % c
txt = txt.replace(old, new)

out = txt.replace("\n", "\r\n").encode("utf-8")
assert b"\r\r\n" not in out, "写回后出现 \\r\\r\\n"
open(P, "wb").write(out)
print("OK: _ckpt_snapshot 抗 None 视图，纯 CRLF 保持")

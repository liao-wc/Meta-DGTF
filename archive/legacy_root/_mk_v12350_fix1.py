# -*- coding: utf-8 -*-
"""v1.23.50 补丁修正 1：`View.from_dict` 别把留痕写进**内容字段** `meta`。

问题（开发期验证抓到）：原实现把「忽略了非字段键」这条**内部留痕**追加进
`v.meta` —— 而 `meta` 是**内容字段**（下游读数/产物会读它）⇒ 续跑出来的层
比原跑多一条不是引擎产出的行（实测差异就是这个键）。

修法：留痕只走 `logger.warning`（给人看）+ `_from_dict_dropped`（给机器查，
**非 dataclass 字段** ⇒ 不进 `asdict`/产物）。
CRLF 安全。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.50.py"
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
t = b.decode("utf-8").replace("\r\n", "\n")

old = (
    '        if _extra:\n'
    '            logger.warning("View.from_dict：忽略非字段键 %r", _extra[:8])\n'
    '            v.meta = list(v.meta or []) + [\n'
    '                "[from_dict] 忽略非字段键：%s" % ",".join(_extra[:8])]\n'
    '        return v\n'
)
new = (
    '        if _extra:\n'
    '            # \u2605 \u7559\u75d5\u53ea\u8d70 logger + \u4e00\u4e2a**\u975e\u5b57\u6bb5\u5c5e\u6027**\uff1a\n'
    '            #   \u5207\u8bb0\u5199\u8fdb `meta`\uff08\u5185\u5bb9\u5b57\u6bb5\uff0c\u4e0b\u6e38\u8bfb\u6570\u4f1a\u8bfb\uff09\u21d2 \u7eed\u8dd1\u51fa\u6765\u7684\u5c42\u4f1a\u591a\u4e00\u6761\n'
    '            #   **\u4e0d\u662f\u5f15\u64ce\u4ea7\u51fa\u7684\u884c**\uff08\u5f00\u53d1\u671f\u9a8c\u8bc1\u5b9e\u6d4b\u5230\u7684\u5dee\u5f02\u5c31\u662f\u8fd9\u4e2a\uff09\u3002\n'
    '            logger.warning("View.from_dict\uff1a\u5ffd\u7565\u975e\u5b57\u6bb5\u952e %r"\n'
    '                           "\uff08\u591a\u534a\u662f to_dict \u8865\u7684 property\uff09", _extra[:8])\n'
    '            try:\n'
    '                v._from_dict_dropped = list(_extra)\n'
    '            except Exception:  # noqa: BLE001\n'
    '                pass\n'
    '        return v\n'
)
c = t.count(old)
print("锚点命中", c)
assert c == 1
t = t.replace(old, new, 1)
assert "v.meta = list(v.meta or []) + [" not in t
out = t.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
b2 = P.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n") and b2.count(b"\r\r\n") == 0
print("OK：from_dict 不再污染 meta")

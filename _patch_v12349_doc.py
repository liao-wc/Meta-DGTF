# -*- coding: utf-8 -*-
"""v1.23.49 冒烟补丁 4：判据 docstring 的过时描述（默认 False → 默认 true）。

`check_v12349_run_ckpt` 的 docstring 还写着「⑦ 配置键 + 接线在源码，且**默认
False**（零行为差）」—— 用户拍板后默认是 **true**（本项目惯例的唯一例外）。
判据行为不受影响（已全绿），此处只把**文档描述**改正，避免留下
「文档说 false、代码是 true」的假信息。
另补三段（⑥ 起停闭环 / ⑦ 端到端真落盘）到判据清单里，与实际一致。

CRLF 安全。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF，先停"
assert b.count(b"\r\r\n") == 0, "已有 \\r\\r\\n 污染，先停"
t = b.decode("utf-8").replace("\r\n", "\n")

old = (
    '    \u2605 \u5224\u636e\uff1a\u2460 \u5199-\u8bfb\u56de\u73af\uff08\u542b View \u7684 `to_dict` \u5f62\u72b6\uff09\uff1b\u2461 **\u539f\u5b50**\uff08\u4e0d\u7559 `.tmp` \u6b8b\u9ab8\uff09\uff1b\n'
    '      \u2462 \u5b64\u513f\u56de\u6536\uff1a\u8fc7\u671f\u7684 `running` \u21d2 `interrupted` + why\uff1b\u2463 **\u8d1f\u5bf9\u7167**\uff1a\u8fd8\u6ca1\u8fc7\u671f\n'
    '        \u7684 \u21d2 \u4e0d\u52a8\uff1b\u2464 \u5e42\u7b49\uff08\u7b2c\u4e8c\u6b21\u4e0d\u518d\u6539\uff09\uff1b\u2465 `interval<=0` / \u65e0 run_id \u21d2 \u4e0d\u8d77\u7ebf\u7a0b\uff1b\n'
    '      \u2466 \u914d\u7f6e\u952e + \u63a5\u7ebf\u5728\u6e90\u7801\uff0c\u4e14**\u9ed8\u8ba4 False**\uff08\u96f6\u884c\u4e3a\u5dee\uff09\u3002\n'
)
new = (
    '    \u2605 \u5224\u636e\uff1a\u2460 \u5199-\u8bfb\u56de\u73af\uff08\u542b View \u7684 `to_dict` \u5f62\u72b6\uff09\uff1b\u2461 **\u539f\u5b50**\uff08\u4e0d\u7559 `.tmp` \u6b8b\u9ab8\uff09\uff1b\n'
    '      \u2462 \u5b64\u513f\u56de\u6536\uff1a\u8fc7\u671f\u7684 `running` \u21d2 `interrupted` + why\uff1b\u2463 **\u8d1f\u5bf9\u7167**\uff1a\u8fd8\u6ca1\u8fc7\u671f\n'
    '        \u7684 \u21d2 \u4e0d\u52a8\uff1b\u2464 \u5e42\u7b49\uff08\u7b2c\u4e8c\u6b21\u4e0d\u518d\u6539\uff09\uff1b\u2465 `interval<=0` / \u65e0 run_id \u21d2 \u4e0d\u8d77\u7ebf\u7a0b\uff1b\n'
    '      \u2466 \u8d77-\u505c\u95ed\u73af\uff08\u771f\u7ebf\u7a0b\uff09\u21d2 \u843d\u6700\u540e\u4e00\u4efd `done`\uff1b\u2467 **\u6784\u9020\u6027\u8bc1\u660e**\uff1a\u51fa\u5382\u9ed8\u8ba4\n'
    '        \u914d\u7f6e\uff08`live_checkpoint=true`\uff0c\u672c\u9879\u76ee\u300c\u65b0\u952e\u9ed8\u8ba4\u5173\u300d\u60ef\u4f8b\u7684**\u552f\u4e00\u4f8b\u5916**\uff09\u4e0b\u771f\u8dd1\n'
    '        \u21d2 \u5feb\u7167\u771f\u843d\u76d8\u3001\u72b6\u6001 `done`\uff1b\u914d\u7f6e\u952e + \u63a5\u7ebf\u4e5f\u5728\u6e90\u7801\u91cc\u5bf9\u8d26\u3002\n'
)

n = t.count(old)
print("锚点命中：%d" % n)
assert n == 1, "锚点不唯一/不存在"
t = t.replace(old, new, 1)
assert "**默认 False**" not in t, "还有残留的默认 False 描述"

out = t.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
P.write_bytes(out)
b2 = P.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n") and b2.count(b"\r\r\n") == 0
print("OK：docstring 已改正，纯 CRLF 保持。")

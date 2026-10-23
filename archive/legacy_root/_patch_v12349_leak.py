# -*- coding: utf-8 -*-
"""v1.23.49 冒烟补丁：修 check_v12349_run_ckpt ⑦ 段 LLM.call 桩**泄漏**。

症状：单独跑 auto_plan 判据通过，整套冒烟跑到「自动规划」却报
      `AssertionError: mode：serial`。
根因：⑦ 端到端段把全局 `mod.LLM.call` 换成占位桩，finally 只还原了
      `run_ckpt_dir` ⇒ 漏还原 `LLM.call` ⇒ 同进程后续检查（auto_plan 等）
      全拿到非 JSON 文本 ⇒ 静默退 serial。
修法：替换前存 `_orig_call`，finally 一并还原。

CRLF 安全：read_bytes → 断言 → 替换 → write_bytes；跑完自检。
"""
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"
b = P.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n"), "非纯 CRLF，先停"
assert b.count(b"\r\r\n") == 0, "已有 \\r\\r\\n 污染，先停"
t = b.decode("utf-8").replace("\r\n", "\n")

old1 = (
    '    _base2 = Path(tempfile.mkdtemp(prefix="ckpt_e2e_"))\n'
    '    _orig_dir = mod.run_ckpt_dir\n'
    '    mod.run_ckpt_dir = lambda base=None: _base2\n'
    '    try:\n'
)
new1 = (
    '    _base2 = Path(tempfile.mkdtemp(prefix="ckpt_e2e_"))\n'
    '    _orig_dir = mod.run_ckpt_dir\n'
    '    # \u2605 \u6869\u5fc5\u987b**\u8fd8\u539f**\uff1a\u4e0b\u9762\u628a\u5168\u5c40 LLM.call \u6362\u6210\u4e86\u5360\u4f4d\u6869\uff0c\u82e5\u6f0f\u8fd8\u539f\uff0c\n'
    '    #   \u540c\u8fdb\u7a0b\u540e\u7eed\u68c0\u67e5\uff08auto_plan \u7b49\uff09\u5168\u62ff\u5230\u975e JSON \u6587\u672c\n'
    '    #   \u21d2 \u9759\u9ed8\u9000 serial\uff08\u672c\u8f6e\u5b9e\u6d4b\u8e29\u8fc7\uff09\u3002\n'
    '    _orig_call = mod.LLM.call\n'
    '    mod.run_ckpt_dir = lambda base=None: _base2\n'
    '    try:\n'
)
old2 = (
    '    except Exception as _e:  # noqa: BLE001\n'
    '        bad.append("[CK-\u7aef\u5230\u7aef] \u9a71\u52a8 run() \u629b\u9519\uff1a%r" % (_e,))\n'
    '    finally:\n'
    '        mod.run_ckpt_dir = _orig_dir\n'
)
new2 = (
    '    except Exception as _e:  # noqa: BLE001\n'
    '        bad.append("[CK-\u7aef\u5230\u7aef] \u9a71\u52a8 run() \u629b\u9519\uff1a%r" % (_e,))\n'
    '    finally:\n'
    '        mod.run_ckpt_dir = _orig_dir\n'
    '        mod.LLM.call = _orig_call\n'
)

n1 = t.count(old1)
n2 = t.count(old2)
print("锚点命中：old1=%d old2=%d" % (n1, n2))
assert n1 == 1, "old1 锚点不唯一/不存在"
assert n2 == 1, "old2 锚点不唯一/不存在"

t = t.replace(old1, new1, 1).replace(old2, new2, 1)

# 替换后校验
assert t.count("_orig_call = mod.LLM.call") == 2, "存量 1 + 新增 1 应为 2"
assert t.count("mod.LLM.call = _orig_call") == 2, "存量 1 + 新增 1 应为 2"

out = t.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0, "写前自检失败"
P.write_bytes(out)

# 回读自检
b2 = P.read_bytes()
assert b2.count(b"\r\n") == b2.count(b"\n"), "写后非纯 CRLF"
assert b2.count(b"\r\r\n") == 0, "写后 CRCRLF 污染"
t2 = b2.decode("utf-8")
assert "_orig_call = mod.LLM.call\n" in t2.replace("\r\n", "\n")
assert "mod.LLM.call = _orig_call\n" in t2.replace("\r\n", "\n")
print("OK：桩泄漏已修（存/还原各 1 处新增），纯 CRLF 保持。")

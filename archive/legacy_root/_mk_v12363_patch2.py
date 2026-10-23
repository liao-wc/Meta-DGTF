# -*- coding: utf-8 -*-
"""v1.23.63 补丁 2：`api.max_retries: 0` 不该等于「一次都不尝试」。

实测（开发期验证时撞出来的）：`LLM.call` 的重试循环写的是
    `for attempt in range(1, self.max_retries + 1)`
⇒ `max_retries=0` 时 `range(1,1)` 是**空循环** ⇒ 直接抛
    `RuntimeError: LLM 连续 0 次失败: None`
也就是说：把 `max_retries` 配成 0（本意"不重试"）会让**所有调用必失败**，
而且报错信息里 `last_err=None`，看不出根因。

对照：同文件的 `WebSearchGate` 用的是 `range(self.max_retries + 1)`（至少尝试一次），
两处语义不一致。

修法（**保持默认行为不变**）：
    `_tries = max(1, int(self.max_retries or 0))`
    `for attempt in range(1, _tries + 1):`
· `max_retries=3`（出厂）⇒ 3 次尝试 —— **与现在完全一样**；
· `max_retries=0` ⇒ 1 次尝试（修好脚枪），不再必然失败。
★ 不改"3 次 = 1 次首试 + 2 次重试"这个既成事实（改它会影响成本与时延，
  属于另一件事，不在本次范围内）。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "元DGTF-V1.23.63.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

OLD = """        last_err = None
        for attempt in range(1, self.max_retries + 1):
"""
NEW = """        last_err = None
        # ★ [脚枪] 原来是 `range(1, self.max_retries + 1)`：配 `max_retries=0`
        #   等于**一次都不尝试**（空循环 ⇒ 直接抛 "连续 0 次失败: None"），
        #   而报错里 last_err 还是 None，看不出根因。
        #   至少尝试一次；默认 3 仍然 = 3 次尝试（与改前完全一样）。
        _tries = max(1, int(self.max_retries or 0))
        for attempt in range(1, _tries + 1):
"""
assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)

# 消息里也报真实尝试次数，便于排障
OLD2 = '''        raise RuntimeError(
            f"LLM 连续 {self.max_retries} 次失败: {last_err}")'''
NEW2 = '''        raise RuntimeError(
            f"LLM 连续 {_tries} 次失败: {last_err}")'''
assert s.count(OLD2) == 1, "抛错文案锚点命中 %d 次" % s.count(OLD2)
s = s.replace(OLD2, NEW2)

ast.parse(s)
out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("已修：max_retries=0 现在至少尝试 1 次；默认 3 次行为不变")

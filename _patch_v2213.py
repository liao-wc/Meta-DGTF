# -*- coding: utf-8 -*-
"""V2.2.12 -> V2.2.13：LLM 调用显式携带 stage（本地链路协调性）。

实测缺陷（本轮两臂实验暴露）
----------------------------
shim 的 `pick_stage` 只认 `model=local:<stage>` 或文本关键词（双判/自省/…），
**兜底 self_check**。引擎的请求既不带显式 stage，system 文本也不含那些关键词
⇒ 本地跑里**全部主生成 stage（expand_pair_merged / manifest / re_anchor /
phase_probe …）都被路由到 self_check LoRA**：
  · 用「自省微调」的适配器干主生成/清单/重锚定的活 —— 题不对文；
  · 长度也被压到 self_check 的 64 token ⇒ JSON 截断（一跑 bad_json=5 全靠修复，
    amps 抽不出 ⇒ aspect_units=0 ⇒ 修行层读数「存量为 0」）；
  · 引擎侧 `llm_by_stage` 记的是**引擎以为的 stage**，与服务实际执行的 stage
    从未对账 —— 「读的是同一个东西」问题的又一个形态。

修法（三层全通）
----------------
  1. 引擎（本补丁）：`LLM.call()` 把 `cost_stage or stage` 写进请求
     `extra_body.stage`（OpenAI SDK 会摊到请求体顶层）。云端忽略未知字段，
     零影响；json_repair 的独立调用点也带上 `"json_repair"`。
  2. shim：`pick_stage` 增加 `explicit` 参数（清洗后优先），并统计
     explicit 命中数 / 避免的错路由数（/health 可见），响应带 requested_stage。
  3. service：无需改 —— 未知 stage 的 `resolve_adapter` 返回 None ⇒ **base
     model**（多面手），正是主生成该用的。
"""
from __future__ import annotations

from pathlib import Path

SRC = Path(r"D:\Meta-DGTF-道生三阶模型\dgtf_engine\dgtf_v2\engine\Meta-DGTF-V2.2.12.py")
DST = Path(r"D:\Meta-DGTF-道生三阶模型\dgtf_engine\dgtf_v2\engine\Meta-DGTF-V2.2.13.py")

data = SRC.read_bytes()
crlf, lf = data.count(b"\r\n"), data.count(b"\n")
assert crlf == lf, "源文件不是纯 CRLF：crlf=%d lf=%d" % (crlf, lf)
src = data.decode("utf-8").replace("\r\n", "\n")
print("read: %s | lines=%d" % (SRC.name, src.count("\n") + 1))

edits = []

# ---- 1. 版本号 ----
edits.append(("Meta-DGTF-道生三阶模型 · V2.2.12",
              "Meta-DGTF-道生三阶模型 · V2.2.13", 1))
edits.append(('__version__ = "2.2.12"', '__version__ = "2.2.13"', 1))

# ---- 2. docstring 补丁段 ----
a = "★ V2.2.12 补丁（四层目标读数的「结构性读不出」）：实测 213 包里修行层"
b = (
    "★ V2.2.13 补丁（LLM 调用显式携带 stage）：shim 此前按文本关键词猜 stage、\n"
    "     兜底 self_check ⇒ 本地跑里全部主生成 stage 都被路由到**自省 LoRA** +\n"
    "     64 token（题不对文：JSON 截断、amps 抽不出、修行层读数「存量为 0」）。\n"
    "     现在 `LLM.call()` 把 `cost_stage or stage` 写进请求 extra_body.stage：\n"
    "     本地 shim 读它选对适配器（无 LoRA 的 stage 用 base model），云端忽略\n"
    "     未知字段零影响。引擎记账的 stage 与服务执行的 stage 终于同源。\n"
    "★ V2.2.12 补丁（四层目标读数的「结构性读不出」）：实测 213 包里修行层"
)
edits.append((a, b, 1))

# ---- 3. call()：extra_body 带 stage ----
a = '''        # ★ OpenAI SDK 的顶层 reasoning_effort= 会被吞掉，必须走 extra_body
        if th:
            body: Dict[str, Any] = {"type": str(th)}
            if is_thinking and self.thinking_effort:
                body["effort"] = str(self.thinking_effort)
            kwargs["extra_body"] = {"thinking": body}'''
b = '''        # ★ OpenAI SDK 的顶层 reasoning_effort= 会被吞掉，必须走 extra_body
        if th:
            body: Dict[str, Any] = {"type": str(th)}
            if is_thinking and self.thinking_effort:
                body["effort"] = str(self.thinking_effort)
            kwargs["extra_body"] = {"thinking": body}
        # ★ [V2.2.13 · stage 显式透传] 本地链路的协调性：shim 此前按文本
        #   关键词猜 stage、兜底 self_check ⇒ 主生成/清单/重锚定全被路由到
        #   自省 LoRA + 64 token（题不对文）。显式带上 stage：本地 shim 读它
        #   选对适配器（无 LoRA 的 stage 用 base model），云端忽略未知字段。
        #   与成本归因同源（cost_stage or stage）⇒ 记账与执行不再两套口径。
        _stage_tx = str(cost_stage or stage or "").strip()
        if _stage_tx:
            _eb = dict(kwargs.get("extra_body") or {})
            _eb["stage"] = _stage_tx
            kwargs["extra_body"] = _eb'''
edits.append((a, b, 1))

# ---- 4. json_repair 独立调用点也带 stage ----
a = '''                extra_body={"thinking": {"type": "disabled"}},
            )
            content = (resp.choices[0].message.content or "").strip()'''
b = '''                extra_body={"thinking": {"type": "disabled"},
                            "stage": "json_repair"},
            )
            content = (resp.choices[0].message.content or "").strip()'''
edits.append((a, b, 1))

for old, new, want in edits:
    got = src.count(old)
    assert got == want, "锚点命中 %d 次（期望 %d）：%r" % (got, want, old[:60])
    src = src.replace(old, new)
    print("  ok: %s" % old[:46].replace("\n", "\\n"))

out = src.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
assert out.count(b"\r\n") == out.count(b"\n"), "输出不是纯 CRLF"
DST.write_bytes(out)
print("written: %s | lines=%d | CRLF=%d"
      % (DST.name, out.count(b"\n") + 1, out.count(b"\r\n")))
print("PATCH OK")

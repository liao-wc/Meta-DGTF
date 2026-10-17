# -*- coding: utf-8 -*-
"""v1.23.51 → v1.23.52：`paused` 跑次**不写 EML 库**（半程样本不是证据）。

背景：v1.23.51 保证「不重复调用就不多写」，但墙钟预算暂停的跑次仍会写一条
**半程样本**；续跑跑完后同一个 `run_id` 又写一条完整样本（读数不同 ⇒ 幂等守卫
按设计放行）⇒ 一个跑次**两条证据**，`used_outcomes` 记两笔、weight 罚两遍。
清账脚本 `_fix_eml_dup_20261016.py` 收拾的正是这一类。

本次四处改动：
  1) `_eml_finish` 头部：`off` 判完就判 `paused`，命中即返回（不建目录、不拿锁）
  2) `_eml_finish` docstring：写明「暂停不写库」
  3) 模块 docstring 标题：v1.23.51 → v1.23.52
  4) `__version__`：1.23.51 → 1.23.52

铁律：read_bytes → 断言 CRLF==LF → 转 LF → 替换 → 转回 CRLF → write_bytes。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.51.py"
DST = HERE / "元DGTF-V1.23.52.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n"), "源文件不是纯 CRLF"
assert raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what, expect=1):
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s（%d 处）" % (what, c))


# ── 1) 暂停不写库 ────────────────────────────────────────────────────
OLD = (
    '        if _mode == "off":\n'
    '            return _blk\n'
    '        _lk = None\n'
)
NEW = (
    '        if _mode == "off":\n'
    '            return _blk\n'
    '        # ★ [暂停不学] 墙钟预算暂停的跑次**不进库**：它只是同一跑次的**半程\n'
    '        #   样本**，续跑跑完后会再收尾一次 ⇒ 两个都写就成了「一个跑次两条\n'
    '        #   证据」（`used_outcomes` 记两笔、weight 罚两遍）。判据取产物里的\n'
    '        #   `paused` / `pending_layers` —— `run()` 在调本方法**之前**就已写好，\n'
    '        #   所以不依赖调用方传参，任何入口口径一致。\n'
    '        #   ★ 成本不会因此丢失：`llm_calls` / `llm_tokens` 仍在产物与快照里，\n'
    '        #     被杀/暂停的跑次照样能结算。\n'
    '        if isinstance(result, dict) and (result.get("paused")\n'
    '                                         or result.get("pending_layers")):\n'
    '            _blk["skipped_paused"] = True\n'
    '            _blk["pending_layers"] = list(result.get("pending_layers") or [])\n'
    '            return _blk\n'
    '        _lk = None\n'
)
rep(OLD, NEW, "暂停不写库守卫")

# ── 2) docstring ────────────────────────────────────────────────────
OLD2 = (
    '        ★ **同一跑次只学一次**：同一个 `run_id` 且读数逐字相同的重复调用\n'
    '          直接返回（`dup_skipped`），不重复写 episode / 不重复罚 weight。\n'
)
NEW2 = (
    '        ★ **同一跑次只学一次**：同一个 `run_id` 且读数逐字相同的重复调用\n'
    '          直接返回（`dup_skipped`），不重复写 episode / 不重复罚 weight。\n'
    '\n'
    '        ★ **暂停不写库**：`paused`（墙钟预算到点 / 还有 `pending_layers`）的\n'
    '          产物直接返回（`skipped_paused`），等续跑跑完再收尾 —— 半程样本\n'
    '          不是证据。\n'
)
rep(OLD2, NEW2, "docstring 说明")

# ── 3) 版本号两处 ───────────────────────────────────────────────────
rep("元 DGTF · v1.23.51\n", "元 DGTF · v1.23.52\n", "docstring 标题")
rep('__version__ = "1.23.51"\n', '__version__ = "1.23.52"\n', "__version__")

# ── 结构性自检 ──────────────────────────────────────────────────────
ast.parse(s)
_i_off = s.index('        if _mode == "off":')
_i_pz = s.index('_blk["skipped_paused"] = True')
_i_lk = s.index("        _lk = None")
_i_lock = s.index("_lk = eml_lock(dirpath=_dir)")
assert _i_off < _i_pz < _i_lk < _i_lock, "顺序应为 off → paused → 取锁"
assert s.count('_blk["skipped_paused"] = True') == 1
# 守卫必须在 `_eml_finish` 里，不在别的方法里
_i_fn = s.index("    def _eml_finish(self, result: dict) -> dict:")
_i_next = s.index("    def run(self, question: str,", _i_fn)
assert _i_fn < _i_pz < _i_next, "守卫不在 _eml_finish 内"
print("  [OK] 结构性自检：off → paused → 取锁，且都在 _eml_finish 内")

n1 = s.count("\n")
assert n1 > n0
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))

# -*- coding: utf-8 -*-
"""v1.23.50 → v1.23.51：`_eml_finish` 加「同一跑次只学一次」的幂等守卫。

背景（真跑逮到的脏数据）：
  `run()` 内部已调 `_eml_finish`，A/B 脚本又调了一次 ⇒ 每个跑次写两条 episode、
  `used_outcomes` 与 weight 罚两遍。只修脚本防不住**同类**（任何调用方都可能重调），
  所以在引擎侧加守卫。零新配置键，单次调用的行为**逐字不变**。

本次四处改动：
  1) `_eml_finish` 方法体：拿到跨进程锁之后、写 episode 之前插幂等守卫
  2) `_eml_finish` docstring：写明「同一跑次只学一次」
  3) 模块 docstring 标题：v1.23.50 → v1.23.51
  4) `__version__`：1.23.50 → 1.23.51

铁律：read_bytes → 断言 CRLF==LF → 转 LF → 替换 → 转回 CRLF → write_bytes。
"""
import ast
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.50.py"
DST = HERE / "元DGTF-V1.23.51.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n"), "源文件不是纯 CRLF"
assert raw.count(b"\r\r\n") == 0, "源文件有 CRCRLF"
s = raw.decode("utf-8").replace("\r\n", "\n")

n0_lines = s.count("\n")


def rep(old, new, what, expect=1):
    """整段替换；命中次数必须恰好 expect。"""
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s（%d 处）" % (what, c))


# ── 1) 幂等守卫 ──────────────────────────────────────────────────────
OLD = (
    '            _lk = eml_lock(dirpath=_dir)\n'
    '            _lk.__enter__()\n'
    '            eml_append_jsonl(_dir / _EML_EPISODES, _ep)\n'
)
NEW = (
    '            _lk = eml_lock(dirpath=_dir)\n'
    '            _lk.__enter__()\n'
    '            # ★ [学一次] **同一跑次只学一次**：`_eml_finish` 会被调用方习惯性\n'
    '            #   地再调一次（本项目的 A/B 脚本就这么干过），第二次调用会把 episode\n'
    '            #   写成两条、把 `used_outcomes` 与 weight 罚两遍 —— 而一个跑次只该是\n'
    '            #   **一条证据**（`t_used` 按 run_id 去重，这里漏掉的是其余字段）。\n'
    '            #   判据用「同 run_id 且除 t 外**逐字相同**」，不是只看 run_id：墙钟\n'
    '            #   预算暂停的跑次也会写一条半程样本，续跑完成时它的读数不同，\n'
    '            #   不能被挡掉（否则完整样本永远进不了库）。\n'
    '            try:\n'
    '                _old_eps = eml_read_jsonl(_dir / _EML_EPISODES) or []\n'
    '            except Exception:\n'
    '                _old_eps = []\n'
    '            _sig_new = json.dumps(\n'
    '                {k: v for k, v in _ep.items() if k != "t"},\n'
    '                ensure_ascii=False, sort_keys=True)\n'
    '            for _oe in _old_eps:\n'
    '                if str((_oe or {}).get("run_id") or "") != str(\n'
    '                        _ep.get("run_id") or ""):\n'
    '                    continue\n'
    '                _sig_old = json.dumps(\n'
    '                    {k: v for k, v in (_oe or {}).items() if k != "t"},\n'
    '                    ensure_ascii=False, sort_keys=True)\n'
    '                if _sig_old == _sig_new:\n'
    '                    _blk["dup_skipped"] = True\n'
    '                    try:\n'
    '                        _blk["n_playbook"] = len(\n'
    '                            eml_read_jsonl(_dir / _EML_PLAYBOOK) or [])\n'
    '                    except Exception:\n'
    '                        pass\n'
    '                    return _blk\n'
    '            eml_append_jsonl(_dir / _EML_EPISODES, _ep)\n'
)
rep(OLD, NEW, "幂等守卫插入")

# ── 2) docstring 补一句 ─────────────────────────────────────────────
OLD2 = (
    '        """**跑后**：micro 反思 → 质量闸 → 合并（只增）→ meso 升级 → 遗忘 → 摘要。\n'
)
NEW2 = (
    '        """**跑后**：micro 反思 → 质量闸 → 合并（只增）→ meso 升级 → 遗忘 → 摘要。\n'
    '\n'
    '        ★ **同一跑次只学一次**：同一个 `run_id` 且读数逐字相同的重复调用\n'
    '          直接返回（`dup_skipped`），不重复写 episode / 不重复罚 weight。\n'
)
rep(OLD2, NEW2, "docstring 说明")

# ── 3) 版本号两处 ───────────────────────────────────────────────────
rep("元 DGTF · v1.23.50\n", "元 DGTF · v1.23.51\n", "docstring 标题")
rep('__version__ = "1.23.50"\n', '__version__ = "1.23.51"\n', "__version__")

# ── 结构性自检（写完才发现坏 = 已晚）────────────────────────────────
ast.parse(s)
_gi = s.index('_blk["dup_skipped"] = True')
_ap = s.index('eml_append_jsonl(_dir / _EML_EPISODES, _ep)')
assert _gi < _ap, "守卫必须在写 episode **之前**"
_lk = s.index("_lk.__enter__()")
assert _lk < _gi, "守卫必须在**拿到锁之后**（否则并发下两边都读到还没写）"
assert s.count('return _blk\n            eml_append_jsonl') == 1, "守卫出口形态异常"
assert "dup_skipped" in s
print("  [OK] 结构性自检：锁 < 守卫 < 写 episode，AST 通过")

# 行数只应增加
n1_lines = s.count("\n")
assert n1_lines > n0_lines, "行数没涨，说明没插进去"
print("  [OK] 行数 %d → %d（+%d）" % (n0_lines, n1_lines, n1_lines - n0_lines))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))

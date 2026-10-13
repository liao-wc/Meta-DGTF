#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.26 打补丁 Step4：池内去重阈值统一走配置（默认值 = 原字面量）。

改动点：
  1) 新增模块级常量 `_DEDUP_SIM`（0.9）/ `_DEDUP_SUSP_SIM`（0.85），
     文档写明它们是**旧的硬编码字面量**，现在有了名字。
  2) `Pool.merge` 增加 `thr=None / susp_thr=None` 参数，None 时取默认；
     四个字面量换成参数。
  3) 调用点（L8870）从 self.config 读 `sim.dedup` / `sim.dedup_susp`
     并传进去。
  4) `DEFAULT_CONFIG` 新增 `"sim"` 段（值 = 原字面量 ⇒ 行为零变化）。

铁律：read_bytes -> 断言 CRLF==LF -> 转 LF -> 替换（断言各命中 1 次）
-> 转回 CRLF -> 断言 -> write_bytes。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.26.py"

b = SRC.read_bytes()
assert b.count(b"\r\n") == b.count(b"\n")
assert b.count(b"\r\r\n") == 0
txt = b.decode("utf-8").replace("\r\n", "\n")

# ---------- 1) 新增模块级常量（接在 _MERGE_SIM 之后） ----------
OLD_CONST = '''_MERGE_SIM = 0.70      # 合并可判定性通道：结构条目去重
'''
NEW_CONST = '''_MERGE_SIM = 0.70      # 合并可判定性通道：结构条目去重

# 池内去重阈值。**这两个值等价于 v1.23.25 里 Pool.merge 内的硬编码
# 字面量**（0.9 / 0.85），提取出来只是为了让「参数按层可覆盖」这条红线
# 在池内也成立 —— 原来是 4 处字面量、一处都改不了。默认值与旧行为
# 逐位相同，改它才会变行为。
_DEDUP_SIM = 0.90        # amp / thread / probe 入池去重
_DEDUP_SUSP_SIM = 0.85   # 悬置目标去重
'''
assert txt.count(OLD_CONST) == 1
txt = txt.replace(OLD_CONST, NEW_CONST, 1)

# ---------- 2) Pool.merge 签名 + 体内 4 处字面量 ----------
OLD_MERGE = '''    def merge(self, amps, threads, meta, probes=None, suspensions=None):
        for a in amps:
            if not any(_similar(a.get("desc", ""), x.get("desc", ""), 0.9)
                       for x in self.amps):
                self.amps.append(a)
        for t in threads:
            if not any(_similar(t.get("desc", ""), x.get("desc", ""), 0.9)
                       for x in self.threads):
                self.threads.append(t)
        for p in (probes or []):
            q = str(p.get("question", "")).strip()
            if q and not any(_similar(q, x.get("question", ""), 0.9)
                             for x in self.probes):
                self.probes.append(p)
        for m in meta:
            if m and m not in self.meta:
                self.meta.append(m)
        for s in (suspensions or []):
            t = str(s.get("target", "")).strip()
            if not t:
                continue
            if any(_similar(t, x.get("target", ""), 0.85)
                   and x.get("status") in ("active", "stable")
                   for x in self.suspensions):
                continue
            self.suspensions.append(s)
'''

NEW_MERGE = '''    def merge(self, amps, threads, meta, probes=None, suspensions=None,
              thr=None, susp_thr=None):
        """把一圈产物并进池子。去重阈值走参数，None 时用模块默认。

        ★ 阈值以前是**四个硬编码字面量**（0.9 ×3 + 0.85 ×1），
          「参数按层可覆盖」这条红线在池内形同虚设。现在可配，
          默认值与原字面量逐位相同 ⇒ 不传参时行为零变化。
        """
        _t = _DEDUP_SIM if thr is None else float(thr)
        _st = _DEDUP_SUSP_SIM if susp_thr is None else float(susp_thr)
        for a in amps:
            if not any(_similar(a.get("desc", ""), x.get("desc", ""), _t)
                       for x in self.amps):
                self.amps.append(a)
        for t in threads:
            if not any(_similar(t.get("desc", ""), x.get("desc", ""), _t)
                       for x in self.threads):
                self.threads.append(t)
        for p in (probes or []):
            q = str(p.get("question", "")).strip()
            if q and not any(_similar(q, x.get("question", ""), _t)
                             for x in self.probes):
                self.probes.append(p)
        for m in meta:
            if m and m not in self.meta:
                self.meta.append(m)
        for s in (suspensions or []):
            t = str(s.get("target", "")).strip()
            if not t:
                continue
            if any(_similar(t, x.get("target", ""), _st)
                   and x.get("status") in ("active", "stable")
                   for x in self.suspensions):
                continue
            self.suspensions.append(s)
'''

assert txt.count(OLD_MERGE) == 1, f"Pool.merge 命中 {txt.count(OLD_MERGE)} 次"
txt = txt.replace(OLD_MERGE, NEW_MERGE, 1)

# ---------- 3) 调用点传配置 ----------
OLD_CALL = '''        pool.merge(view.amps, view.threads, view.meta, view.probes)
'''
NEW_CALL = '''        _sim_cfg = (self.config.get("sim") or {})
        pool.merge(view.amps, view.threads, view.meta, view.probes,
                   thr=_sim_cfg.get("dedup", _DEDUP_SIM),
                   susp_thr=_sim_cfg.get("dedup_susp", _DEDUP_SUSP_SIM))
'''
assert txt.count(OLD_CALL) == 1, f"merge 调用点命中 {txt.count(OLD_CALL)} 次"
txt = txt.replace(OLD_CALL, NEW_CALL, 1)

# 确认调用点在 self.config 可用作用域内
_i = txt.find("def _apply_view_to_pool_locked(self, view: View, pool: Pool, entry: str,")
assert _i > 0, "未找到 _apply_view_to_pool_locked"

# ---------- 4) DEFAULT_CONFIG 新增 sim 段（插在 probe 段之前） ----------
OLD_CFG = '''    "probe": {
        "min_gain": 0.3,
        "select_n": 3,
    },
'''
NEW_CFG = '''    "sim": {
        # 池内去重阈值（v1.23.25 及以前是 Pool.merge 里的硬编码字面量）。
        # 默认值与原字面量逐位相同 ⇒ 不改这里就与旧版行为一致。
        "dedup": 0.9,
        "dedup_susp": 0.85,
    },

    "probe": {
        "min_gain": 0.3,
        "select_n": 3,
    },
'''
assert txt.count(OLD_CFG) == 1, f"probe 配置段命中 {txt.count(OLD_CFG)} 次"
txt = txt.replace(OLD_CFG, NEW_CFG, 1)

# ---------- 断言 ----------
assert "def merge(self, amps, threads, meta, probes=None, suspensions=None," in txt
assert txt.count("_DEDUP_SIM") >= 3
assert txt.count("_DEDUP_SUSP_SIM") >= 3
assert '"sim": {' in txt
assert 'thr=_sim_cfg.get("dedup", _DEDUP_SIM)' in txt
# 旧字面量应已消失于 merge 体内
_i = txt.find("    def merge(self, amps, threads, meta, probes=None, suspensions=None,")
_j = txt.find("\n    def ", _i + 10)
_merge_body = txt[_i:_j]
assert ", 0.9)" not in _merge_body, "merge 体内仍有 0.9 字面量"
assert ", 0.85)" not in _merge_body, "merge 体内仍有 0.85 字面量"

out = txt.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n")
assert out.count(b"\r") == out.count(b"\r\n")
assert out.count(b"\r\r\n") == 0
SRC.write_bytes(out)

print("OK Step4: merge 阈值读配置 + DEFAULT_CONFIG.sim 段")
print("lines =", out.count(b"\n"), "bytes =", len(out))

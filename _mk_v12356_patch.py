# -*- coding: utf-8 -*-
"""v1.23.55 → v1.23.56：快照记账改成**跨窗口累计**。

问题（A/B 真跑暴露的）：
  快照里的 `llm_calls` / `llm_tokens` 取自 `self.llm.total_calls` —— 那是**按实例**
  的计数器。续跑会新建实例 ⇒ 计数器归零 ⇒ 第二个窗口的快照写 `calls=97`，而这条
  run_id **实际已经花了 230**。

  这直接打穿 v1.23.50 立命的那句话：**「被杀跑次也能结算成本」**——按窗口记的数
  只能结算**最后一个窗口**，前面的钱在快照里查不到（我这次只能另建外部账本兜）。

修法：
  · `load_resume_snapshot` 把快照里的 `llm_calls` / `llm_tokens` 一起返回；
  · `run()` 拿到续跑快照时把它记进 `self._ck_base`（跨窗口基线）；
  · `_ckpt_snapshot` 落盘时写 **累计 = 基线 + 本实例**，并**另存** `window_*`
    保留本窗口读数（两者都要：累计用于结算，窗口用于看这一窗干了多少）。

无新配置键；不传 `resume_ckpt` ⇒ 基线为 0 ⇒ 数值与旧版**逐字相同**。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.55.py"
DST = HERE / "元DGTF-V1.23.56.py"

raw = SRC.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")
n0 = s.count("\n")


def rep(old, new, what, expect=1):
    global s
    c = s.count(old)
    assert c == expect, "%s：命中 %d 次（要求 %d）" % (what, c, expect)
    s = s.replace(old, new)
    print("  [OK] %s" % what)


# ── 1) 快照写累计 ──────────────────────────────────────────────────
rep('''    _acct = {}
    try:
        _llm = getattr(engine, "llm", None)
        _acct = {"llm_calls": int(getattr(_llm, "total_calls", 0) or 0),
                 "llm_tokens": int(getattr(_llm, "total_tokens", 0) or 0),''',
    '''    _acct = {}
    try:
        _llm = getattr(engine, "llm", None)
        # ★ [跨窗口累计] `total_calls` 是**按实例**的（续跑新建实例就归零）
        #   ⇒ 只写它，第二个窗口的快照会把前面的钱抹掉（实测：实际 230，快照写 97）。
        #   v1.23.50 立命的「被杀跑次也能结算成本」要求**按 run_id 累计**。
        #   `window_*` 两个字段保留本窗口读数（结算看累计，分析看窗口）。
        _base = getattr(engine, "_ck_base", None) or {}
        _w_calls = int(getattr(_llm, "total_calls", 0) or 0)
        _w_tokens = int(getattr(_llm, "total_tokens", 0) or 0)
        _acct = {"llm_calls": int(_base.get("calls") or 0) + _w_calls,
                 "llm_tokens": int(_base.get("tokens") or 0) + _w_tokens,
                 "window_calls": _w_calls,
                 "window_tokens": _w_tokens,''',
    "快照记账改累计（+window_*）")

# ── 2) load_resume_snapshot 带回计数 ───────────────────────────────
rep('    _out = {"ok": False, "why": "", "views": {}, "pools": {}}\n',
    '    _out = {"ok": False, "why": "", "views": {}, "pools": {},\n'
    '            "llm_calls": 0, "llm_tokens": 0}\n',
    "load_resume_snapshot 返回计数字段")

rep('    _out["ok"] = True\n    if _bad:\n',
    '    # ★ 把快照里的**累计**记账带回去：续跑时作为新窗口的基线（见 `_ckpt_snapshot`）。\n'
    '    try:\n'
    '        _out["llm_calls"] = int(_d.get("llm_calls") or 0)\n'
    '        _out["llm_tokens"] = int(_d.get("llm_tokens") or 0)\n'
    '    except Exception:\n'
    '        pass\n'
    '    _out["ok"] = True\n    if _bad:\n',
    "load_resume_snapshot 回填计数")

# ── 3) run() 里设基线 ──────────────────────────────────────────────
rep('        self._resume = {"views": {}, "pools": {}}\n',
    '        self._resume = {"views": {}, "pools": {}}\n'
    '        # ★ [跨窗口累计] 续跑时的记账基线；不续跑就是 0（数值与旧版逐字相同）。\n'
    '        self._ck_base = {"calls": 0, "tokens": 0}\n',
    "run() 初始化 _ck_base")

rep('''            if _rs.get("ok"):
                self._resume = {"views": _rs.get("views") or {},
                                "pools": _rs.get("pools") or {}}''',
    '''            if _rs.get("ok"):
                self._resume = {"views": _rs.get("views") or {},
                                "pools": _rs.get("pools") or {}}
                # ★ 基线 = 快照里已有的累计；本次窗口的读数会加在它上面。
                self._ck_base = {"calls": int(_rs.get("llm_calls") or 0),
                                 "tokens": int(_rs.get("llm_tokens") or 0)}
                if self._ck_base["calls"] or self._ck_base["tokens"]:
                    self.vp("   💰 续跑记账基线：已花 %d calls / %d tokens"
                            % (self._ck_base["calls"], self._ck_base["tokens"]))''',
    "run() 从快照设基线")

# ── 4) 版本号 ──────────────────────────────────────────────────────
rep("元 DGTF · v1.23.55\n", "元 DGTF · v1.23.56\n", "docstring 标题")
rep('__version__ = "1.23.55"\n', '__version__ = "1.23.56"\n', "__version__")

ast.parse(s)
assert s.count('"window_calls": _w_calls,') == 1
assert s.count('_base.get("calls") or 0') == 1
assert sum(1 for _ln in s.split(chr(10)) if "self._ck_base" in _ln) == 4
assert s.count('_out["llm_calls"] = int(_d.get("llm_calls") or 0)') == 1
print("  [OK] 结构性自检：写侧累计+窗口 · 读侧带计数 · run() 设基线")

n1 = s.count("\n")
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))

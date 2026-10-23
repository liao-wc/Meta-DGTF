# -*- coding: utf-8 -*-
"""v1.23.52 → v1.23.53：记忆库目录**一处解析**（bandit 不再偷偷写回仓库）。

问题（挂账 #2「目录两处解析未收敛」）：
  · episode / playbook 走 `playbook.dir`（`_eml_cfg["dir"] or eml_dir()`）
  · bandit 走 `cfg["dir"] or eml_dir()` —— **只看 `auto.bandit.dir`**，不吃 `playbook.dir`
  ⇒ 只要调用方设了 `playbook.dir`（冒烟、A/B 脚本、任何想隔离库的人），bandit 仍然
    往**仓库 `dgtf_memory/`** 写。冒烟隔离因此要三个旋钮
    （`output.save_dir` + `playbook.dir` + `auto.bandit.dir`），漏一个就污染生产库。

修法：新增模块级 `eml_store_dir(cfg)` 作为**唯一**解析，三处都走它：
    `auto.bandit.dir`（显式，仍优先） ＞ `playbook.dir` ＞ 仓库根 `dgtf_memory/`

★ 为什么是**模块级函数**而不是 `self._eml_store_dir()`：
  bandit 的**载入**发生在 `self._eml_cfg` 赋值**之前**（14099→14119），用实例状态
  会静默回落到 `eml_dir()` —— 那正是要修的 bug 本身。读 `self.config` 没有这个顺序问题。

无新配置键；生产默认（`playbook.dir` 为空）解析结果与旧版**逐字相同**。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.52.py"
DST = HERE / "元DGTF-V1.23.53.py"

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
    print("  [OK] %s" % what)


# ── 1) 唯一解析函数 ─────────────────────────────────────────────────
OLD = (
    '    _b = Path(base) if base else Path(__file__).resolve().parent\n'
    '    return _b / _EML_DIRNAME\n'
    '\n'
    '\n'
    '@contextlib.contextmanager\n'
)
NEW = (
    '    _b = Path(base) if base else Path(__file__).resolve().parent\n'
    '    return _b / _EML_DIRNAME\n'
    '\n'
    '\n'
    'def eml_store_dir(cfg=None) -> Path:\n'
    '    """记忆库**存储目录**的唯一解析：`playbook.dir` 优先，空则仓库根 `dgtf_memory/`。\n'
    '\n'
    '    ★ 以前是两处解析：episode/playbook 走 `playbook.dir`，bandit 走\n'
    '      `cfg["dir"] or eml_dir()` —— 于是只要调用方设了 `playbook.dir`，bandit\n'
    '      仍往**仓库**写，冒烟隔离要三个旋钮（漏一个就污染生产库）。现在三处都走这里。\n'
    '    ★ 优先级：`auto.bandit.dir`（显式） ＞ `playbook.dir` ＞ `eml_dir()`。\n'
    '    ★ 为什么是**模块级**而不是实例方法：bandit 的**载入**发生在实例属性\n'
    '      `_eml_cfg` 赋值之前，用实例状态会静默回落到 `eml_dir()`。\n'
    '    """\n'
    '    try:\n'
    '        _p = ((cfg or {}).get("playbook") or {}).get("dir")\n'
    '    except Exception:\n'
    '        _p = None\n'
    '    return Path(str(_p or eml_dir()))\n'
    '\n'
    '\n'
    '@contextlib.contextmanager\n'
)
rep(OLD, NEW, "新增 eml_store_dir（唯一解析）")

# ── 2) bandit 两个函数的落点参数 ────────────────────────────────────
rep('def _load_bandit(cfg) -> "BudgetBandit":',
    'def _load_bandit(cfg, fallback=None) -> "BudgetBandit":',
    "_load_bandit 签名")
rep('        _d = Path(str((cfg or {}).get("dir") or eml_dir()))\n'
    '        _f = _d / _BANDIT_FILE\n',
    '        # ★ `fallback` = 调用方给的记忆库目录（`eml_store_dir(cfg)`）。\n'
    '        #   显式的 `auto.bandit.dir` 仍然优先；都没有才回落到 `eml_dir()`。\n'
    '        _d = Path(str((cfg or {}).get("dir") or fallback or eml_dir()))\n'
    '        _f = _d / _BANDIT_FILE\n',
    "_load_bandit 目录解析")
rep('def _save_bandit(bb, cfg) -> bool:',
    'def _save_bandit(bb, cfg, fallback=None) -> bool:',
    "_save_bandit 签名")
rep('        _d = Path(str((cfg or {}).get("dir") or eml_dir()))\n'
    '        _d.mkdir(parents=True, exist_ok=True)\n',
    '        # ★ 同上：`fallback` 让 bandit 跟着 `playbook.dir` 走（隔离不再靠第三个旋钮）。\n'
    '        _d = Path(str((cfg or {}).get("dir") or fallback or eml_dir()))\n'
    '        _d.mkdir(parents=True, exist_ok=True)\n',
    "_save_bandit 目录解析")

# ── 3) 两处调用点 + `_eml_finish` 也走同一函数 ──────────────────────
rep("                self._bandit = _load_bandit(_bd)",
    "                self._bandit = _load_bandit(_bd, eml_store_dir(self.config))",
    "调用点：载入")
rep("                _save_bandit(self._bandit, self._bandit_cfg)",
    "                _save_bandit(self._bandit, self._bandit_cfg,\n"
    "                             eml_store_dir(self.config))",
    "调用点：落盘")
rep('            _dir = Path(str(_c.get("dir") or eml_dir()))\n',
    '            _dir = eml_store_dir(self.config)\n',
    "_eml_finish 走同一解析")

# ── 4) 版本号两处 ───────────────────────────────────────────────────
rep("元 DGTF · v1.23.52\n", "元 DGTF · v1.23.53\n", "docstring 标题")
rep('__version__ = "1.23.52"\n', '__version__ = "1.23.53"\n', "__version__")

# ── 结构性自检 ──────────────────────────────────────────────────────
ast.parse(s)
assert s.count("def eml_store_dir(cfg=None) -> Path:") == 1
assert s.count("eml_store_dir(self.config)") == 3, s.count("eml_store_dir(self.config)")
# bandit 的两处不能再直接摸 eml_dir()
assert 'cfg or {}).get("dir") or eml_dir()' not in s, "还有地方直接回落 eml_dir()"
assert 'cfg or {}).get("dir") or fallback or eml_dir()' in s
# 载入点必须早于 _eml_cfg（说明为什么用模块级函数）—— 这只是注释性断言
_i_load = s.index("_load_bandit(_bd, eml_store_dir(self.config))")
_i_emlcfg = s.index("self._eml_cfg = _pl")
assert _i_load < _i_emlcfg, "载入点竟在 _eml_cfg 之后（注释里的理由需要更新）"
print("  [OK] 结构性自检：3 处走同一解析 · 无残留 eml_dir() 回落 · 载入早于 _eml_cfg")

n1 = s.count("\n")
assert n1 > n0
print("  [OK] 行数 %d → %d（+%d）" % (n0, n1, n1 - n0))

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
DST.write_bytes(out)
print("\n写出 %s（%d 字节 / %d 行 / 纯 CRLF）"
      % (DST.name, len(out), out.count(b"\r\n")))

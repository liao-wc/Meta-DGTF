# -*- coding: utf-8 -*-
"""[v1.23.27 Step3] A1 · 方面单元（AspectUnit）结构化 + 双写。

设计（`_设计_五机制算法重构_v12326.md` §3.1 A1）：
  AspectUnit = {id, text, polarity, ground, ref}，
  其中 `text` 与旧键 `desc` **同值** ⇒ 全部读取点零改动。

本步只做四件事：
  1. 新增两个模块级常量：
     · `_ASPECT_GROUNDS` = ("anchor","pool","upstream","judge","expand")
     · `_ASPECT_POLARITIES` = ("阴","阳")
     并新增模块级纯函数 `make_aspect_unit(...)` —— **单一构造点**，
     所有落库都走它，避免「同一条逻辑两条实现」。
  2. `View` 新增 `aspect_units: List[dict]` 字段（**只加不删**）。
  3. `View.shape_of` 渲染时把 id 前缀带上（`A1. 文本`）—— 这是
     **可观测性**，也让 covers 的靶子看得见。
  4. 四个落库点改为「构造 unit + 同时写旧键与 aspect_units」：
     · L4793-4796 锚点两半（ground="anchor"）
     · L4839     judge 侧未触及（ground="judge"）

★ 双写后 `aspect_units` 里每个 dict 都**同时含** `desc` 与 `text`，
  且 `text == desc` ⇒ 老的 `.get("desc")` 读取点全部兼容（零改动）。
★ id 只在本圈内稳定：`A{n}` 按 `aspect_units` 的追加顺序编号。

写文件铁律：read_bytes → 断言 CRLF==LF → 转 LF → 替换 → 转回 CRLF
→ write_bytes。★ 用 write_bytes 不用 write_text。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"

raw = SRC.read_bytes()
txt = raw.decode("utf-8")

# ── 铁律第 1 条：改动前后必须是纯 CRLF ──────────────────────────────
n_crlf = txt.count("\r\n")
n_lf = txt.count("\n")
assert n_crlf == n_lf, "源文件不是纯 CRLF：CRLF=%d LF=%d" % (n_crlf, n_lf)
assert "\r\r\n" not in txt, "源文件已有 \\r\\r\\n 污染"

lf = txt.replace("\r\n", "\n")
orig_lf = lf

HITS = []


def sub(anchor, new, tag, count=1):
    """整块替换；断言命中 == count（默认 1）。"""
    global lf
    n = lf.count(anchor)
    assert n == count, "%s：锚点命中 %d 次（要求 %d）\n---\n%s" % (
        tag, n, count, anchor[:200])
    lf = lf.replace(anchor, new)
    HITS.append((tag, n))


# ══════════════════════════════════════════════════════════════════
# 1. 模块级常量 + 单一构造点 make_aspect_unit
# ══════════════════════════════════════════════════════════════════
_ANC = "SUSPENSION_STATUS = ("
_i = lf.find(_ANC)
assert _i > 0, "找不到 SUSPENSION_STATUS 定义块"
_j = lf.find("\n", lf.find(")", _i))
assert _j > _i, "找不到 SUSPENSION_STATUS 行尾"
_anchor_const = lf[_i:_j]

NEW_CONST = _anchor_const + '''

# ── [v1.23.27 A1] 方面单元（AspectUnit）的封闭枚举与**单一构造点** ──
#  ★ 为什么要有常量：`ground` / `polarity` 会被判据逐字比对，
#    散在各处写字面量 = 迟早出现「同一件事两种写法」。
#  ★ `text` 与旧键 `desc` **同值**：AspectUnit 是「旧 dict 加几个键」，
#    不是新类型 ⇒ 全部 `.get("desc")` 读取点零改动。
_ASPECT_GROUNDS = ("anchor", "pool", "upstream", "judge", "expand")
_ASPECT_POLARITIES = ("阴", "阳")


def make_aspect_unit(desc, source="anchor", polarity="阴",
                     ground="anchor", ref="", unit_id=""):
    """构造一个 AspectUnit（dict）—— **全工程唯一构造点**。

    ★ 双写：返回的 dict 同时带 `desc`（旧键）与 `text`（新键），两者恒等。
      这样 `_target_text` / `shape_of` / `_quality_check` 等既有读取点
      （都取 `.get("desc")`）**一个字都不用改**。
    ★ `ground` 不在 `_ASPECT_GROUNDS` 里时**归一化到 "anchor"**（不抛错）：
      这是留痕场景，不该因为一个枚举越界就丢掉整条方面。
    ★ id 为空时**不自动编号**（编号由 View 侧按追加顺序给，才稳定）。
    """
    s = str(desc).strip()
    if not s:
        return {}
    g = str(ground).strip()
    if g not in _ASPECT_GROUNDS:
        g = "anchor"
    p = str(polarity).strip()
    if p not in _ASPECT_POLARITIES:
        p = "阴"
    return {
        "id": str(unit_id or ""),
        "desc": s,          # ← 旧键，读取点全部依赖它
        "text": s,          # ← 新键，与 desc 恒等
        "polarity": p,
        "ground": g,
        "ref": str(ref or ""),
        "source": str(source or g),
    }
'''
sub(_anchor_const, NEW_CONST, "const+make_aspect_unit")

# ══════════════════════════════════════════════════════════════════
# 2. View 新增 aspect_units 字段（只加不删）
# ══════════════════════════════════════════════════════════════════
sub(
    "    anchor_touched: List[dict] = field(default_factory=list)\n"
    "    ing_structured: dict = field(default_factory=dict)\n",
    "    anchor_touched: List[dict] = field(default_factory=list)\n"
    "    ing_structured: dict = field(default_factory=dict)\n"
    "    # [v1.23.27 A1] 方面单元：锚点两半 + judge 侧未触及的**统一登记**。\n"
    "    # ★ 与 untouched / anchor_touched **双写**，不是替换：\n"
    "    #   旧键是历史 packed 的口径，删了会让下游读数从「作证据」\n"
    "    #   静默降级成「读不到」。\n"
    "    aspect_units: List[dict] = field(default_factory=list)\n",
    "View.aspect_units")

# ══════════════════════════════════════════════════════════════════
# 2b. View 加登记方法（唯一入口，自动编号）
# ══════════════════════════════════════════════════════════════════
sub(
    "    @staticmethod\n"
    "    def shape_of(v: \"View\") -> str:\n",
    "    def add_aspect_unit(self, desc, source=\"anchor\", polarity=\"阴\",\n"
    "                        ground=\"anchor\", ref=\"\"):\n"
    "        \"\"\"[v1.23.27 A1] 登记一个方面单元，返回 unit（空 desc 返回 {}）。\n"
    "\n"
    "        ★ 编号 `A{n}` 由**追加顺序**决定 ⇒ 同一条描述重复登记时\n"
    "          返回**已存在**的那条（不新建、不换号）。幂等是硬要求：\n"
    "          调用点在循环里，重复登记会污染 covers 的靶子集合。\n"
    "        \"\"\"\n"
    "        s = str(desc).strip()\n"
    "        if not s:\n"
    "            return {}\n"
    "        for _u in self.aspect_units:\n"
    "            if _u.get(\"desc\") == s:\n"
    "                return _u\n"
    "        _uid = \"A%d\" % (len(self.aspect_units) + 1)\n"
    "        _u = make_aspect_unit(s, source=source, polarity=polarity,\n"
    "                              ground=ground, ref=ref, unit_id=_uid)\n"
    "        if _u:\n"
    "            self.aspect_units.append(_u)\n"
    "        return _u\n"
    "\n"
    "    @staticmethod\n"
    "    def shape_of(v: \"View\") -> str:\n",
    "View.add_aspect_unit")

# ══════════════════════════════════════════════════════════════════
# 3. shape_of 渲染带 id（可观测性：covers 的靶子看得见）
# ══════════════════════════════════════════════════════════════════
sub(
    "        if v.untouched:\n"
    "            lines.append(\"尚未触及的方面：\")\n"
    "            for u in v.untouched:\n"
    "                lines.append(f\"  - {u.get('desc', '')}\")\n",
    "        if v.untouched:\n"
    "            lines.append(\"尚未触及的方面：\")\n"
    "            for u in v.untouched:\n"
    "                # [v1.23.27 A1] 带 id 前缀：渲染里看得见编号，\n"
    "                #   才可能在下一圈被 covers 按符号引用。\n"
    "                _aid = str(u.get(\"id\", \"\") or \"\")\n"
    "                _pfx = (_aid + \". \") if _aid else \"\"\n"
    "                lines.append(f\"  - {_pfx}{u.get('desc', '')}\")\n",
    "shape_of 带 id")

# ══════════════════════════════════════════════════════════════════
# 4a. 落库点：锚点两半（L4793-4796）
# ══════════════════════════════════════════════════════════════════
sub(
    "        for t in _anchor_touched:\n"
    "            view.anchor_touched.append({\"desc\": t, \"source\": \"anchor\"})\n"
    "        for u in anchor_untouched:\n"
    "            view.untouched.append({\"desc\": u, \"source\": \"anchor\"})\n",
    "        # [v1.23.27 A1] 双写：旧键照旧 + aspect_units 统一登记（带 id）。\n"
    "        # ★ 触及侧 polarity=\"阳\"（已显形）/ 未触及侧 polarity=\"阴\"（未显形）\n"
    "        #   —— 与阴阳展开臂的语义对齐（§3.1 A1）。\n"
    "        for t in _anchor_touched:\n"
    "            view.anchor_touched.append({\"desc\": t, \"source\": \"anchor\"})\n"
    "            view.add_aspect_unit(t, source=\"anchor\", polarity=\"阳\",\n"
    "                                 ground=\"anchor\")\n"
    "        for u in anchor_untouched:\n"
    "            view.untouched.append({\"desc\": u, \"source\": \"anchor\"})\n"
    "            view.add_aspect_unit(u, source=\"anchor\", polarity=\"阴\",\n"
    "                                 ground=\"anchor\")\n",
    "落库·锚点两半")

# ══════════════════════════════════════════════════════════════════
# 4b. 落库点：judge 侧未触及（L4839）
# ══════════════════════════════════════════════════════════════════
sub(
    "        for c in candidates:\n"
    "            if c.position == \"0\" and c.desc.strip():\n"
    "                if not any(_similar(c.desc, x.get(\"desc\", \"\"), 0.85)\n"
    "                           for x in view.untouched):\n"
    "                    view.untouched.append({\"desc\": c.desc, \"source\": \"judge\"})\n",
    "        for c in candidates:\n"
    "            if c.position == \"0\" and c.desc.strip():\n"
    "                if not any(_similar(c.desc, x.get(\"desc\", \"\"), 0.85)\n"
    "                           for x in view.untouched):\n"
    "                    view.untouched.append({\"desc\": c.desc, \"source\": \"judge\"})\n"
    "                    view.add_aspect_unit(c.desc, source=\"judge\",\n"
    "                                         polarity=\"阴\", ground=\"judge\")\n",
    "落库·judge 侧")

out_lf = lf
assert out_lf != orig_lf, "没有任何改动"

# ── 铁律第 2 条：转回 CRLF 并 write_bytes ──────────────────────────
out = out_lf.replace("\n", "\r\n")
assert "\r\r\n" not in out, "产出含 \\r\\r\\n"
SRC.write_bytes(out.encode("utf-8"))

chk = SRC.read_bytes().decode("utf-8")
assert chk.count("\r\n") == chk.count("\n"), "写回后不是纯 CRLF"
assert "\r\r\n" not in chk, "写回后含 \\r\\r\\n"

print("STEP3 OK  —— %d 处替换" % len(HITS))
for _t, _n in HITS:
    print("  · %-28s x%d" % (_t, _n))
print("  size %d -> %d bytes" % (len(raw), len(chk.encode('utf-8'))))

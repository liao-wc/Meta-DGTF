# -*- coding: utf-8 -*-
"""[打补丁] 元DGTF-V1.21.73.py  →  元DGTF-V1.21.74.py

只改一件事：外判拿到的外部锚点引用，不许在合并时被丢掉。

★ 为什么值得单独开一版：v1.21.73 已经把锚点送进了 `_assess_decidability`，
  它也确实返回了 anchor_refs（本轮探针实测 8/12 条被引用），
  但 `_merge_decidability` 里 `merged = dict(pool_res)` 只搬池判那一路，
  外判的引用到不了 packed、到不了产物 md。结果是：
  「外判有没有真的引用外部事实」这件事**从产物上永远查不出来**。
  看不见 = 审不了，这与本项目「失败留痕 / 文中 alcanzable」的底线冲突。

★ 加性红线照旧：锚点**关闭**时一个键都不许多。
  所以合并处只在「确实给了锚点」时才挂键（_anchors_given 非 0 或 refs 非空），
  关闭时 ext_res 两条都空 → 不挂键 → packed 键集合与 v1.21.72 逐字相同。

铁律（照 MEMORY.md）：
  1. 不覆盖源文件，复制出下一版；
  2. 版本号改两处：docstring 标题 + __version__；
  3. CRLF 往返：read_bytes → 断言纯 CRLF → 转 LF → 替换 → 转回 → 断言换行数；
  4. 每处替换断言锚点**恰好出现 1 次**（重复插入是真实事故）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE / "元DGTF-V1.21.73.py"
NEW = HERE / "元DGTF-V1.21.74.py"

OLD_VER, NEW_VER = "1.21.73", "1.21.74"


def main() -> int:
    raw = OLD.read_bytes()
    text = raw.decode("utf-8")
    n_lf = raw.count(b"\n")
    n_crlf = raw.count(b"\r\n")
    n_cr = raw.count(b"\r")
    assert n_lf == n_crlf == n_cr, (
        f"源文件不是纯 CRLF：LF={n_lf} CRLF={n_crlf} CR={n_cr}")
    src = text.replace("\r\n", "\n")
    print(f"读入 {OLD.name}：{len(src)} 字符，纯 CRLF ✓")

    # ── 1) 版本号两处 ────────────────────────────────────────────
    a = '元 DGTF · v' + OLD_VER
    b = '元 DGTF · v' + NEW_VER
    assert src.count(a) == 1, f"docstring 标题命中 {src.count(a)} 次"
    src = src.replace(a, b)

    a2 = '__version__ = "' + OLD_VER + '"'
    b2 = '__version__ = "' + NEW_VER + '"'
    assert src.count(a2) == 1, f"__version__ 命中 {src.count(a2)} 次"
    src = src.replace(a2, b2)
    print("版本号两处已改 ✓")

    # ── 2) changelog 插段（插到 v1.21.73 那段之前）────────────────
    anchor = "  v1.21.73 是本轮「接外部锚点」版。"
    lines = src.split("\n")
    hits = [i for i, l in enumerate(lines) if l.startswith(anchor)]
    assert len(hits) == 1, f"changelog 锚点命中 {len(hits)} 次"
    at = hits[0]

    block = [
        "  v1.21.74 是本轮「让外部锚点可被审计」版。只改一处：`_merge_decidability`",
        "  原先 `merged = dict(pool_res)` 只继承池判，`_assess_decidability` 算好的",
        "  `anchor_refs` / `_anchors_given` 在合并时被丢掉 —— 因此 v1.21.73 的 ON 臂",
        "  产物里 `anchor_refs` 是 None，**看不出外判到底有没有引用外部事实**。",
        "  探针 `_probe_v73_refs.py` 实测（同一题、同一份锚点、直接调 assess）：",
        "    带锚点   anchor_refs = [a1,a2,a3,a5,a6,a7,a8,a9]（8/12）_anchors_given=12",
        "    不带锚点 anchor_refs = []                        _anchors_given=0",
        "  即引用是真的算出来了、真的被合并丢掉了。本版在合并时把它带上，",
        "  ★ 只在「确实给了锚点」时挂键（refs 非空或 _anchors_given 非 0）——",
        "    锚点关闭时两条都空、一个键都不加，packed 键集合与 v1.21.72 逐字相同。",
        "  未采纳：给对照条目加「来源标签」（view / pool）用于自动诊断层次错配。",
        "    理由：本轮靠读 claims 原文 30 秒就定位了错配，收益不足以抵消它带来的",
        "    冒烟耦合面（`_anchor_claims` 返回值形状变更，冒烟里 3 处直接调用）。",
    ]
    assert not any("\n" in l for l in block)
    lines[at:at] = block
    src = "\n".join(lines)
    print(f"changelog 已插 {len(block)} 行（原第 {at + 1} 行前）✓")

    # ── 3) _merge_decidability 带上外判的锚点引用 ─────────────────
    anchor2 = '        merged["undecidable_aspects"] = und_aspects[:8]'
    assert src.count(anchor2) == 1, f"合并锚点命中 {src.count(anchor2)} 次"

    carry = '\n'.join([
        anchor2,
        "        # [v1.21.74] 外判的锚点引用必须跟着外判一起进终审视图。",
        "        #   改前 `merged = dict(pool_res)` 只继承池判那一路，这一次合并",
        "        #   把 `anchor_refs` 直接丢掉 —— 于是「外判有没有真的引用外部",
        "        #   事实」从 packed / 产物上永远查不出来（v1.21.73 ON 臂实测：",
        "        #   日志里外判理由明写了「利用率红线」「LCIA」这两个**只存在于",
        "        #   锚点文件**的词，packed 里 anchor_refs 却是 None）。",
        "        #   ★ 条件挂键：只在确实给了锚点时加，锚点关闭时不加 ——",
        "        #     保证 OFF 态 packed 键集合仍与 v1.21.72 逐字相同。",
        '        _ext_refs = [str(x)[:20] for x in',
        '                     (ext_res.get("anchor_refs") or [])[:12]]',
        '        _ext_given = int(ext_res.get("_anchors_given") or 0)',
        "        if _ext_refs or _ext_given:",
        '            merged["anchor_refs"] = _ext_refs',
        '            merged["_anchors_given"] = _ext_given',
    ])
    src = src.replace(anchor2, carry, 1)
    assert src.count('_ext_refs = [str(x)[:20] for x in') == 1, "携带块插入次数异常"
    print("_merge_decidability 携带块已插入 ✓")

    # ── 4) CRLF 往返 ─────────────────────────────────────────────
    assert "\r" not in src, "正文里混进了 CR"
    out = src.replace("\n", "\r\n")
    b = out.encode("utf-8")
    assert b.count(b"\n") == b.count(b"\r\n"), "回写文件不是纯 CRLF"
    assert b.count(b"\n") == src.count("\n"), "换行数变了"
    NEW.write_bytes(b)
    print(f"已写出 {NEW.name}：{len(b)} 字符（旧 {len(raw)}），纯 CRLF ✓")

    # ── 5) 自检：形态计数 ────────────────────────────────────────
    chk = out.replace("\r\n", "\n")
    for form, n in (('        if _ext_refs or _ext_given:', 1),
                    ('merged["anchor_refs"] = _ext_refs', 1),
                    ('  v1.21.74 是本轮', 1),
                    ('元 DGTF · v1.21.74', 1),
                    ('__version__ = "1.21.74"', 1)):
        got = chk.count(form)
        print(f"  形态 {form!r:<45} = {got}"
              + ("  ✓" if got == n else f"  ✗ 期望 {n}"))
        assert got == n, form
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

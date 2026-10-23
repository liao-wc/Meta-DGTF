# -*- coding: utf-8 -*-
"""[打补丁] smoke_test.py：SRC 指向 v1.21.74 + 新增 check_v74_anchor_refs。

判据必须**双向**：
  · 关闭态：一个 anchor_* 键都不许出现（加性红线）
  · 开启有引用：必须原样带过来
  · 开启零引用：也必须带过来 —— 「给了 12 条却一条没引」正是要审计的信号，
    不许为了让数字好看而抹掉它
  · ext 为 None：退回池判，不许报错也不许加键

★ 判别力由 `_probe_v74_mutants.py` 单独验（删掉携带块本判据必须报错）。
  结构不变式在现版必然通过，「通过」本身不构成证据。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"

FUNC = '''

def check_v74_anchor_refs():
    """[v1.21.74] 外判的锚点引用不许在合并时被丢掉 —— 双向判据。

    ★ 这条是 v1.21.73 真跑抓出来的：`_merge_decidability` 里
      `merged = dict(pool_res)` 只继承池判，`_assess_decidability` 已经算好的
      `anchor_refs` 到不了 packed。`_probe_v73_refs.py` 实测同一题直接调
      assess 得 8 条引用，跑完 packed 里却是 None —— 也就是「外判有没有引用
      外部事实」在产品上不可审。看不见 = 审不了。
    ★ 代价／红线：**关闭态必须一个键都不多**，否则 OFF 臂与 v1.21.72 不再
      逐字同构，加性改动就破了。所以判据里把关闭态放在第一条。
    """
    print("\\n[v1.21.74] 外部锚点引用在合并后的留存")
    _src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    bad = []

    # [0] 形态：携带块必须真的在源码里（防止"改了文案没改代码"）
    if "merged[\\"anchor_refs\\"] = _ext_refs" not in _src:
        bad.append("[形态] _merge_decidability 里找不到 anchor_refs 携带语句")

    mt = object.__new__(mod.MetaDGTF)
    pool = {"decidability": "decidable", "reason": "", "features": [],
            "decidable_aspects": ["现金流第一约束"], "undecidable_aspects": [],
            "_und_untraced": [], "_evidence_full": []}
    ext = {"decidability": "decidable", "reason": "可用回本与利用率红线",
           "features": [], "decidable_aspects": ["回本测算"],
           "undecidable_aspects": []}

    # [A] 关闭态：一个锚点键都不许有（加性红线）
    r_off = mt._merge_decidability(dict(pool), dict(ext))
    leaked = sorted(k for k in r_off
                    if k.startswith("anchor") or k.startswith("_anchors"))
    if leaked:
        bad.append(f"[A] 关闭态泄漏锚点键 {leaked} —— OFF 臂不再与旧版同构")
    else:
        print("  ✓ [A] 关闭态无任何 anchor_* 键（加性红线守住）")

    # [B] 开启且有引用：必须原样带过来
    r_on = mt._merge_decidability(
        dict(pool), dict(ext, anchor_refs=["a1", "a5", "a9"],
                         _anchors_given=12))
    if r_on.get("anchor_refs") != ["a1", "a5", "a9"]:
        bad.append(f"[B] 引用被吞：实得 {r_on.get('anchor_refs')!r}")
    elif r_on.get("_anchors_given") != 12:
        bad.append(f"[B] _anchors_given 丢了：实得 {r_on.get('_anchors_given')!r}")
    else:
        print("  ✓ [B] 开启有引用：3 条编号 + given=12 原样留存")

    # [C] 开启但零引用：也必须留存 —— 这正是要审计的信号
    r_zero = mt._merge_decidability(
        dict(pool), dict(ext, anchor_refs=[], _anchors_given=12))
    if r_zero.get("anchor_refs") != [] or r_zero.get("_anchors_given") != 12:
        bad.append(f"[C] 「给了 12 条却 0 引用」被抹掉了："
                   f"refs={r_zero.get('anchor_refs')!r} "
                   f"given={r_zero.get('_anchors_given')!r}")
    else:
        print("  ✓ [C] 开启零引用：如实留存（没为了好看抹掉）")

    # [D] ext 为 None（单边池判）：不许报错，也不许加键
    try:
        r_none = mt._merge_decidability(dict(pool), None)
    except Exception as exc:
        bad.append(f"[D] ext=None 直接抛异常：{type(exc).__name__}: {exc}")
        r_none = {}
    if not any(k.startswith("anchor") for k in r_none):
        print("  ✓ [D] ext=None 退回池判，无异常无锚点键")
    else:
        bad.append("[D] ext=None 却带上了锚点键")

    if bad:
        print("  ✗ 未通过：")
        for b in bad:
            print("    -", b)
        return False
    print("  ✓ A/B/C/D 四路全部符合")
    return True
'''


def main() -> int:
    raw = SMOKE.read_bytes()
    text = raw.decode("utf-8")
    n_lf, n_crlf, n_cr = (raw.count(b"\n"), raw.count(b"\r\n"),
                          raw.count(b"\r"))
    assert n_lf == n_crlf == n_cr, f"smoke_test 不是纯 CRLF: {n_lf}/{n_crlf}/{n_cr}"
    src = text.replace("\r\n", "\n")
    print(f"读入 smoke_test.py：{len(src)} 字符，纯 CRLF ✓")

    # 1) SRC → v1.21.74
    a = 'SRC = HERE / "元DGTF-V1.21.73.py"'
    b = 'SRC = HERE / "元DGTF-V1.21.74.py"'
    assert src.count(a) == 1, f"SRC 行命中 {src.count(a)} 次"
    src = src.replace(a, b)
    print("SRC → v1.21.74 ✓")

    # 2) 在 check_config_parses 之前插入新判据函数
    lines = src.split("\n")
    hits = [i for i, l in enumerate(lines) if l.startswith("def check_config_parses(")]
    assert len(hits) == 1, f"check_config_parses 命中 {len(hits)} 次"
    at = hits[0]
    block = FUNC.strip("\n").split("\n")
    assert not any("\n" in l for l in block)
    lines[at:at] = block + ["", ""]
    src = "\n".join(lines)
    print(f"check_v74_anchor_refs 已插入 {len(block)} 行 ✓")

    # 3) main 里接上
    a3 = "    if not check_v73_anchor():\n        return 1"
    b3 = ("    if not check_v73_anchor():\n        return 1\n"
          "    if not check_v74_anchor_refs():\n        return 1")
    assert src.count(a3) == 1, f"main 接入口命中 {src.count(a3)} 次"
    src = src.replace(a3, b3)
    print("main 已接上 check_v74_anchor_refs ✓")

    out = src.replace("\n", "\r\n")
    bb = out.encode("utf-8")
    assert bb.count(b"\n") == bb.count(b"\r\n"), "回写后不是纯 CRLF"
    assert bb.count(b"\n") == src.count("\n"), "换行数与正文不一致"
    SMOKE.write_bytes(bb)
    print(f"已写回 smoke_test.py：{len(bb)} 字节 ✓")

    chk = out.replace("\r\n", "\n")
    for form, n in (('SRC = HERE / "元DGTF-V1.21.74.py"', 1),
                    ("def check_v74_anchor_refs():", 1),
                    ("    if not check_v74_anchor_refs():", 1)):
        got = chk.count(form)
        print(f"  形态 {form!r:<45} = {got}"
              + ("  ✓" if got == n else f"  ✗ 期望 {n}"))
        assert got == n, form
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

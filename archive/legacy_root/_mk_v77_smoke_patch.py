# -*- coding: utf-8 -*-
"""给 smoke_test.py 加 v1.21.77 的 2 条判据（M1' 顺序 + S2 无条件渲染）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"

FUNC = '''

def check_v77_claim_order():
    """[v1.21.77 M1'] `_anchor_claims` 取 candidates 时**层 0 必须排最前**。

    ★ v1.21.76 写的是 (1,0,both,all) —— 层 1（研究层的操作性论断）占满 12 条
      配额，层 0 的领域事实层论断一条都进不来，真跑「印证 0 / 用到锚点 0」。
      改成 (0,1,both,all) 后，同一份 packed、同一把尺 →「印证 4 / 用到锚点 3」。
      **顺序是这条链的成败点**，所以单独做判据锁住。
    """
    print("\\n[v1.21.77 M1'] claims 取值的层顺序")
    import re as _re
    body = _v76_body("_anchor_claims")
    bad = []
    if not body:
        bad.append("[M1'] 找不到 `_anchor_claims`")
    else:
        ms = _re.findall(r"for k in \\(([^)]+)\\):", body)
        if not ms:
            bad.append("[M1'] 函数体里没有 `for k in (...)` 层循环")
        else:
            first = ms[0]
            layers = [x.strip().strip('"').strip("'") for x in first.split(",")]
            if not layers or layers[0] != "0":
                bad.append(f"[M1'] candidates 循环的第一层是 "
                           f"{layers[0] if layers else '?'!r}，期望 '0'"
                           f"（修行层的领域论断必须优先占配额）")
            if "1" not in layers:
                bad.append("[M1'] 层 1 不在循环里（会被整个丢掉）")
            if len(ms) < 2:
                bad.append("[M1'] 只剩一个层循环 —— 成品答案那条被误删了")
        if '"candidates"' not in body and "'candidates'" not in body:
            bad.append("[M1'] `candidates` 来源丢了")
    # 负对照：老顺序必须能被这个判据抓到
    if not bad and "(\\"1\\", \\"0\\"" in body:
        bad.append("[M1'] 仍是旧的 (1,0,...) 顺序（负对照触发）")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 candidates 循环层顺序 = 0 优先；两处来源仍在")
    return True


def check_v77_input_sanity_render():
    """[v1.21.77 S2] `input_sanity` 必须**无条件**渲染（三态可辨）。

    ★ 原先 `if san.get("issues"):` 是条件渲染 —— 检查跑了、没发现问题的产物
      里看不出它跑过。项目纪律：自检字段必须无条件写。
    """
    print("\\n[v1.21.77 S2] 输入自检无条件渲染")
    code = _v76_strip(_v76_src())
    bad = []
    for frag in ('san = result.get("input_sanity")',
                 "if san is None:",
                 "未启用",
                 "已检查，未发现问题"):
        if frag not in code:
            bad.append(f"[S2] 渲染代码里找不到 {frag!r}")
    # 三态里的「有问题」分支也要在
    if "issues" not in code:
        bad.append("[S2] 丢了 `issues` 分支")
    # 负对照：条件渲染的旧写法（`san = ... or {}` + 直接 if issues）必须能被抓到
    if 'san = result.get("input_sanity") or {}' in code and \\
            "if san is None:" not in code:
        bad.append("[S2] 仍是 `or {}` 的条件渲染写法（负对照触发）")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 三态齐备：未启用 / 已检查未发现问题 / 发现问题（列条目）")
    return True
'''

CALLS = (
    "    if not check_v77_claim_order():\n        return 1\n"
    "    if not check_v77_input_sanity_render():\n        return 1\n"
)


def main() -> None:
    b = SMOKE.read_bytes()
    t = b.decode("utf-8").replace("\r\r\n", "\n").replace("\r\n", "\n")
    t = t.replace("\r", "\n")
    lines = t.split("\n")
    # 插在 check_v76_input_sanity_shape 之后
    i76 = next(i for i, l in enumerate(lines)
               if l.startswith("def check_v76_input_sanity_shape("))
    j = i76 + 1
    while j < len(lines) and not lines[j].startswith("def "):
        j += 1
    lines[j:j] = FUNC.split("\n")
    t = "\n".join(lines)
    print(f"  [2 条判据] 插在第 {j+1} 行前")

    old_call = "    if not check_v76_input_sanity_shape():\n        return 1\n"
    assert t.count(old_call) == 1, t.count(old_call)
    t = t.replace(old_call, old_call + CALLS)
    print("  [main 接线] 2 条")

    # SRC -> v1.21.77
    assert t.count("元DGTF-V1.21.76.py") == 1, t.count("元DGTF-V1.21.76.py")
    t = t.replace("元DGTF-V1.21.76.py", "元DGTF-V1.21.77.py")
    print("  [SRC] -> v1.21.77")

    out = t.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\n") == out.count(b"\n")
    SMOKE.write_bytes(out)
    print(f"已更新 {SMOKE.name}（{len(out)} 字节，纯 CRLF）")


if __name__ == "__main__":
    main()

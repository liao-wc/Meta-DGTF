import py_compile, re
from pathlib import Path

E = Path("dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.17.py")
et = E.read_bytes().decode("utf-8").replace("\r\n", "\n")

start = et.index("def diet_local_prompt(")
end = et.index("class LLM:", start)
NEW = '''def diet_local_prompt(text: str, cap: int = _LPD_CAP,
                      tail: int = _LPD_TAIL) -> tuple:
    """本地端点专用 prompt 瘦身；返回 (new_text, stats)。

    规则（保守，宁少瘦不多删）：
      R1 行级**完全去重**：strip 后相同的非空行只留第一次出现（顺序不变）；
      R2 噪声块：以上述噪声头开头的块只留第一份，超过 cap 字符截断；
      R3 尾部保护：末尾约 tail 字符（按**整行对齐**切）原样保留，
         不参与 R1/R2 —— 0.5B 场景下尾部 JSON schema / 最终指令比重复记忆重要。
    空文本 / 瘦身后为空 / 变长 ⇒ 原样返回（绝不把 prompt 弄坏）。
    ★ tail=0 表示全文参与瘦身（A6/A7 的纯噪声块用例）。
    ★ 尾部必须按整行切：旧实现按字符硬切，head 末尾会出现**半行**，若半行恰好
      等于某个完整行（如 "行-1" 与 "行-17" 的边界）会被误删 ⇒ 文本被切坏。
      第一版实测 lines_removed=1 且 chars 少 4，即此 bug。
    """
    if not text:
        return text, {"lines_removed": 0, "blocks_truncated": 0,
                      "chars_before": 0, "chars_after": 0}
    n_cap = max(0, int(cap or 0))
    n_tail = max(0, int(tail or 0))
    lines = str(text).split("\\n")
    if n_tail > 0 and len(text) > n_tail:
        # 从尾部往前累计字符，切在**行首**（保证 head/keep 都是完整行）
        acc = 0
        cut = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            acc += len(lines[i]) + 1
            if acc >= n_tail:
                cut = i
                break
        head_lines, keep_lines = lines[:cut], lines[cut:]
    else:
        head_lines, keep_lines = lines, []
    seen = set()
    kept = []
    removed = 0
    for ln in head_lines:
        k = ln.strip()
        if k and k in seen:
            removed += 1
            continue
        if k:
            seen.add(k)
        kept.append(ln)
    head2 = "\\n".join(kept)
    out, seen_noise, trunc = [], set(), 0
    for b in _lpd_blocks(head2):
        s = b.lstrip()
        nk = next((h for h in _LPD_NOISE_HEADS if s.startswith(h)), None)
        if nk is not None:
            if nk in seen_noise:
                trunc += 1
                continue
            seen_noise.add(nk)
            if len(b) > n_cap:
                out.append(b[:n_cap])
                trunc += 1
                continue
        out.append(b)
    new_head = "\\n".join(out)
    new = new_head + (("\\n" + "\\n".join(keep_lines)) if keep_lines else "")
    if not new.strip() or len(new) > len(text):
        return text, {"lines_removed": 0, "blocks_truncated": 0,
                      "chars_before": len(text), "chars_after": len(text)}
    return new, {"lines_removed": removed, "blocks_truncated": trunc,
                 "chars_before": len(text), "chars_after": len(new)}


'''
et = et[:start] + NEW + et[end:]
out = et.replace("\n", "\r\n").encode("utf-8")
E.write_bytes(out)
chk = E.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(E), doraise=True)
print("OK diet_local_prompt v2（行对齐尾部 + tail=0 全量）")

# -*- coding: utf-8 -*-
"""v1.23.11 补丁：把「如实记账」里剩下的两条做完。

  R1 后半  自省诊断 → 动作回写：新增 `_append_self_check_writeback`，
           把 `views.*.self_check.unsaid_is_escape` 与 `quality_flags` 里的
           高置信诊断提升为落地层里的一条**可执行动作**。
  R10 后半 事实题默认接入外部校验：新增 `_web_auto_for_facts`，
           `--web auto` 时事实型询问自动视同 `on`。

主文件必须保持纯 CRLF。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.11.py"

raw = SRC.read_bytes()
txt = raw.decode("utf-8")
assert txt.count("\r\n") == txt.count("\n") and txt.count("\r") == txt.count("\r\n")
text = txt.replace("\r\n", "\n")
lines = text.split("\n")
N0 = len(lines)


def find_row(pred, tag):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    assert len(hits) == 1, f"[{tag}] 整行锚点命中 {len(hits)} 行（要求 1）"
    return hits[0]


# ── A 版本号 ────────────────────────────────────────────────────
lines[find_row(lambda l: l == "元 DGTF · v1.23.10", "docstring 标题")] = \
    "元 DGTF · v1.23.11"
lines[find_row(lambda l: l == '__version__ = "1.23.10"', "__version__")] = \
    '__version__ = "1.23.11"'

# ── B 新增两个纯函数（插在 render_landing 之前）─────────────────
NEW_FUNCS = '''def _append_self_check_writeback(res: dict, body: str) -> str:
    """把自省的**高置信诊断**回写成落地层里的一条可执行动作。

    ★ 为什么要有：自省结论原先只落在逐层明细（`views.*.self_check`），
      读落地层的人看不到 —— 诊断与动作之间是断的。这里把两类高置信信号
      提到落地层：
        · `unsaid_is_escape=True` —— 自省判「用『未生』收尾 = 逃避」；
        · `quality_flags` 里的 `xxx_overused(n)` / `action_incomplete` /
          `not_do_missing`。
    ★ 没有高置信信号时**原样返回**（不渲染、不制造动作）。
    """
    _items = []
    _views = res.get("views") or {}
    for _k in ("0", "1", "both", "all"):
        _v = _views.get(_k) or {}
        if not isinstance(_v, dict):
            continue
        _sc = _v.get("self_check") or {}
        if isinstance(_sc, dict) and _sc.get("unsaid_is_escape"):
            _w = str(_sc.get("unsaid_where") or "")[:120]
            _items.append(
                f"- [{_k}] ⚠ **判为逃避**：{_w}\\n"
                "  ⇒ 动作：回到该层「撞不动的地方」继续推，别用「未生」收尾。")
        for _fl in (_v.get("quality_flags") or []):
            _s = str(_fl)
            if ("_overused" in _s or _s.startswith("action_incomplete")
                    or _s.startswith("not_do_missing")):
                _items.append(
                    f"- [{_k}] ⚠ **质量线索 `{_s}`**\\n"
                    "  ⇒ 动作：先核这条线索对应的机制是否真跑到，"
                    "再决定采不采信结论。")
    if not _items:
        return body
    _blk = (f"\\n> **自省回写**（诊断 → 动作）：本次 {len(_items)} 条高置信诊断"
            "被提升为动作 ——\\n" + "\\n".join(_items) + "\\n")
    _i = body.find("> 模板里的分节")
    if _i >= 0:
        _j = body.find("\\n\\n", _i)
        if _j >= 0:
            return body[:_j] + "\\n" + _blk + body[_j:]
    _nl = body.find("\\n")
    if _nl < 0:
        return body + _blk
    return body[:_nl] + "\\n" + _blk + body[_nl:]


def _web_auto_for_facts(question: str) -> bool:
    """`--web auto` 下，事实型询问是否自动接入外部校验。

    ★ 判据同 `_has_decision_context`：无决策语境 = 事实型 ⇒ 自动接入。
    ★ 为什么默认接入：真跑实证 —— 事实型询问的史实结论完全靠池内材料一致性
      撑着，产物里却只写一句「这是设计边界，不是缺陷」。把「没校验」变成
      一次**默认会做的动作**，比一句免责声明有用。
    ★ 要关掉：`--web off`。
    """
    return not _has_decision_context(question)


'''
i = find_row(lambda l: l == "def render_landing(res: dict) -> str:", "render_landing")
lines[i:i] = NEW_FUNCS.split("\n")[:-1]

# ── C render_landing：改成「先算 _body，再统一后处理」────────────
i = find_row(lambda l: l == "def render_landing(res: dict) -> str:", "分流壳")
j0 = i + 1
while 'cfg = res.get("_config") or {}' not in lines[j0]:
    j0 += 1
    assert j0 < i + 40, "找不到分流壳函数体起点"
j = j0
while "return _with_form_declaration(" not in lines[j]:
    j += 1
    assert j < i + 50, "找不到分流壳首个 return"
while lines[j].strip() != '("取向 %s" % orientation)':
    j += 1
    assert j < i + 60, "找不到分流壳倒数第二行"
_k = j
while not lines[_k].strip().startswith('+ ("：题面含决策语境"'):
    _k += 1
    assert _k < i + 65, "找不到分流壳末行"
assert lines[_k].strip().endswith("))"), f"收尾行不符：{lines[_k]!r}"
NEW_BODY = [
    '    cfg = res.get("_config") or {}',
    '    orientation = str(res.get("orientation") or "auto").strip().lower()',
    '    if orientation == "boundary" or not _action_on(cfg, "landing_decision"):',
    '        _why = ("取向显式指定 boundary" if orientation == "boundary"',
    '                else "落地决策模板已关闭")',
    "        _body = _with_form_declaration(",
    '            res, _render_landing_boundary(res), "boundary", _why)',
    '    elif orientation == "auto" and not _has_decision_context(',
    '            str(res.get("question") or "")):',
    "        _body = _with_form_declaration(",
    '            res, _render_landing_boundary(res), "boundary",',
    '            "auto：题面无决策语境（单点事实询问）")',
    "    else:",
    "        _body = _with_form_declaration(",
    '            res, _render_landing_decision(res), "decision",',
    '            ("取向 %s" % orientation)',
    '            + ("：题面含决策语境" if orientation == "auto" else ""))',
    "    return _append_self_check_writeback(res, _body)",
]
lines[j0:_k + 1] = NEW_BODY

# ── D main：--web auto + 事实题 → on ────────────────────────────
i = find_row(lambda l: l == "    cfg, _rt_notes = _apply_runtime(cfg, {", "runtime 调用")
assert lines[i + 1].strip() == '"web": args.web, "thinking": args.thinking,', \
    f"runtime 参数行不符：{lines[i + 1]!r}"
lines[i:i] = [
    '    _web = args.web',
    '    if _web == "auto" and _web_auto_for_facts(" ".join(args.question)):',
    '        _web = "on"',
    '        print("   · 事实型询问 + --web auto ⇒ 自动接入外部校验（要关：--web off）")',
]
lines[i + 4] = lines[i + 4].replace('"web": args.web', '"web": _web')

out = "\n".join(lines)
out_b = out.replace("\n", "\r\n").encode("utf-8")
assert out_b.count(b"\r\n") == out_b.count(b"\n") and out_b.count(b"\r\r\n") == 0
SRC.write_bytes(out_b)

chk = SRC.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\r\n") == chk.count(b"\n")
import ast  # noqa: E402
ast.parse(chk.decode("utf-8"))
_c = chk.decode("utf-8")
print(f"OK 行数 {N0} → {_c.count(chr(10)) + 1}")
for _n in ("_append_self_check_writeback", "_web_auto_for_facts"):
    print(f"  新函数 {_n}: {'def %s(' % _n in _c}")
print('  main 接线:', '"web": _web' in _c)
print('  v1.23.10 残留:', "v1.23.10" in _c.replace("元 DGTF · v1.23.11", "")
      .replace('"1.23.11"', ""))

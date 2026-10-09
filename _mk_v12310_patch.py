# -*- coding: utf-8 -*-
"""v1.23.10 补丁：剩余四项一次做完（全部落在渲染 / 落盘层）。

  R1  形态声明     ：落地层标题后插一行「本次用哪套模板 + 依据」
  R8  附录外置     ：默认把内联全量 JSON 搬到旁挂 `*.packed.json`（`--appendix inline` 回退）
  R9  成本档自动路由：`--profile auto` 按题面规则选档（纯函数，不调 LLM）
  R10 事实题未校验留痕：事实型询问在产物里显式写明「本次未接入外部校验 + 怎么接」

主文件必须保持纯 CRLF。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.10.py"

raw = SRC.read_bytes()
txt = raw.decode("utf-8")
assert txt.count("\r\n") == txt.count("\n"), "不是纯 CRLF"
assert txt.count("\r") == txt.count("\r\n"), "有游离 CR"
text = txt.replace("\r\n", "\n")
lines = text.split("\n")
N0 = len(lines)


def find_row(pred, tag):
    hits = [i for i, l in enumerate(lines) if pred(l)]
    assert len(hits) == 1, f"[{tag}] 整行锚点命中 {len(hits)} 行（要求 1）"
    return hits[0]


# ── A 版本号 ────────────────────────────────────────────────────
lines[find_row(lambda l: l == "元 DGTF · v1.23.9", "docstring 标题")] = \
    "元 DGTF · v1.23.10"
lines[find_row(lambda l: l == '__version__ = "1.23.9"', "__version__")] = \
    '__version__ = "1.23.10"'

# ── B 新增三个纯函数（插在 render_landing 之前）──────────────────
NEW_FUNCS = '''def _with_form_declaration(res: dict, body: str, template: str,
                           why: str) -> str:
    """把「形态声明」插到落地层标题之后，返回新正文。

    ★ 为什么不能插在标题之前：md 里标题前放正文，那个标题就不再是章节标题了。
    ★ 为什么要有：decision 模板会渲染出「行动清单 / 负责人 / 时限 / 验收」
      这类**模板结构**；真跑实测它们被填成了不存在的岗位与会议
      （「党史研究室编研岗」「定稿会前2个工作日」）。声明一行，
      读的人才知道哪些段落是模板约定、哪些是问题本身要求的。
    """
    _decl = (f"\\n> **形态声明**：本次落地层用 **{template}** 模板 —— {why}。\\n"
             "> 模板里的分节（如 decision 的「行动清单 / 负责人 / 时限 / "
             "验收」）是**渲染约定**，不等于提问者的要求。\\n")
    _nl = body.find("\\n")
    if _nl < 0:
        return _decl + body
    return body[:_nl] + "\\n" + _decl + body[_nl:]


def _auto_profile(question: str) -> str:
    """按题面**规则式**选成本档（纯函数，不调 LLM）。

    ★ 判据同 `_has_decision_context`：无决策语境的单点事实询问 → `economy`；
      含决策语境 → `balanced`（默认档，token 精简）。**不选 `quality`** ——
      那是「不裁剪」，留给显式要求的人。
    ★ 与 `--profile economy` 的差别：本函数只改**成本档**；要真控规模还得显式
      传 `--rounds`（实测：`economy` 只裁 token，圈数照旧，反而可能更贵）。
    """
    return "economy" if not _has_decision_context(question) else "balanced"


_APPENDIX_JSON_RE = re.compile(r"```json\\n(.*?)\\n```\\n?", re.S)


def _appendix_to_file(text: str, side_path) -> str:
    """把附录里的内联全量 JSON 搬到旁挂文件；正文只留文件名与读法。

    ★ 红线不变：「**不得因为没写渲染点就丢信息**」。变的是**位置**，不是有没有 ——
      `_render_full_appendix` 一字未改，它依旧是「机械全量」的权威实现；
      本函数只做**搬运**，搬运失败就原样退回内联（并留痕），绝不悄悄丢。
    ★ 为什么值得搬：真跑实测内联 JSON 占全文 81.7%（9987 行里 4760 行是它）。
    """
    _m = _APPENDIX_JSON_RE.search(text)
    if not _m:
        return text
    _dump = _m.group(1)
    try:
        _p = Path(side_path)
        _p.write_text(_dump, encoding="utf-8")
    except Exception as e:                      # 搬运失败 → 退回内联 + 留痕
        return text.replace(
            _m.group(0),
            "⚠️ **全量 JSON 外置失败**（已回退为内联）："
            f"{type(e).__name__}: {e}\\n", 1)
    _tip = ("```text\\n" + str(Path(side_path).name) + "\\n```\\n\\n"
            f"（{len(_dump)} 字符 / {_dump.count(chr(10)) + 1} 行；"
            "用 `json.load` 打开即可，UTF-8，与产物 md 同目录。）\\n")
    return text.replace(_m.group(0), _tip, 1)


'''
i = find_row(lambda l: l == "def render_landing(res: dict) -> str:", "render_landing")
lines[i:i] = NEW_FUNCS.split("\n")[:-1]

# ── C render_landing：三个 return 都包上形态声明 ─────────────────
i = find_row(lambda l: l == "def render_landing(res: dict) -> str:", "分流壳")
# ★ docstring 是多行，函数体起点不能硬编码偏移 —— 从函数头往下找
j0 = i + 1
while 'cfg = res.get("_config") or {}' not in lines[j0]:
    j0 += 1
    assert j0 < i + 40, "找不到分流壳函数体起点"
j = j0
while lines[j].strip() != "return _render_landing_decision(res)":
    j += 1
    assert j < i + 45, "找不到分流壳末尾"
NEW_BODY = [
    '    cfg = res.get("_config") or {}',
    '    orientation = str(res.get("orientation") or "auto").strip().lower()',
    '    if orientation == "boundary" or not _action_on(cfg, "landing_decision"):',
    '        _why = ("取向显式指定 boundary" if orientation == "boundary"',
    '                else "落地决策模板已关闭")',
    "        return _with_form_declaration(",
    "            res, _render_landing_boundary(res), \"boundary\", _why)",
    '    if orientation == "auto" and not _has_decision_context(',
    '            str(res.get("question") or "")):',
    "        return _with_form_declaration(",
    '            res, _render_landing_boundary(res), "boundary",',
    '            "auto：题面无决策语境（单点事实询问）")',
    "    return _with_form_declaration(",
    '        res, _render_landing_decision(res), "decision",',
    '        ("取向 %s" % orientation)',
    '        + ("：题面含决策语境" if orientation == "auto" else ""))',
]
lines[j0:j + 1] = NEW_BODY

# ── D save_result：读附录模式 + 搬运 ────────────────────────────
i = find_row(lambda l: l == 'def save_result(result: dict, save_dir: str = "outputs") -> Path:',
             "save_result")
assert lines[i + 1].strip() == "d = Path(save_dir)", f"save_result 第 2 行不符：{lines[i + 1]!r}"
lines[i + 1:i + 1] = [
    '    _ap_mode = str(((result.get("_config") or {}).get("actions") or {})',
    '                   .get("appendix_mode") or "file").strip().lower()',
    '    if _ap_mode not in ("inline", "file"):',
    '        _ap_mode = "file"',
]

i = find_row(lambda l: l == "            _fa.write(_render_full_appendix(result, _md_so_far))",
             "附录调用")
NEW_CALL = [
    "            _ap_text = _render_full_appendix(result, _md_so_far)",
    '            if _ap_mode == "file":',
    "                _ap_text = _appendix_to_file(",
    '                    _ap_text, md.with_name(md.stem + ".packed.json"))',
    "            _fa.write(_ap_text)",
]
lines[i:i + 1] = NEW_CALL

# ── E R10：事实型询问显式写「未接入外部校验」 ────────────────────
i = find_row(lambda l: l == '                f.write("**外部锚点**：无（本产物不含外部事实校验；"',
             "外部锚点")
assert lines[i + 2].strip() == '"这是设计边界，不是缺陷）\\n\\n")', \
    f"外部锚点块第 3 行不符：{lines[i + 2]!r}"
lines[i + 3:i + 3] = [
    "                if not _has_decision_context(",
    '                        str(result.get("question") or "")):',
    "                    f.write(",
    '                        "★ **本题是事实型询问，但本次未接入外部校验**"',
    '                        " —— 这是一次**显式选择**，不是默认特权：\\n"',
    '                        "  - 要接入：`--web on`（或配置 `web_search.*` 五档）。\\n"',
    '                        "  - 接入后头部会多出「锚点对照 / 冲突 / triage 降级」各行；\\n"',
    '                        "  - 未接入时，史实类结论**没有外部证据支撑**，请自行核对。\\n\\n")',
]

# ── F argparse：--profile 加 auto、新增 --appendix ──────────────
i = find_row(lambda l: l == '                        choices=["quality", "balanced", "economy"],',
             "profile choices")
lines[i] = '                        choices=["auto", "quality", "balanced", "economy"],'
i = find_row(lambda l: l == '    parser.add_argument("--orientation", default="auto",',
             "orientation 参数")
lines[i:i] = [
    '    parser.add_argument("--appendix", default="file",',
    '                        choices=["file", "inline"],',
    '                        help="全量字段附录：file（默认，JSON 外置旁挂文件）"',
    '                             " / inline（旧行为，JSON 内联正文）")',
]

# ── G main：auto 档规则化 + 附录模式注入 ───────────────────────
i = find_row(lambda l: l == "    if args.profile:", "profile 应用")
assert lines[i + 1].strip() == 'cfg["cost_profile"] = args.profile'
assert lines[i + 2].strip() == 'print(f"   ✓ 成本档位：{args.profile}")'
lines[i:i + 3] = [
    "    if args.profile:",
    '        _pf = args.profile',
    '        if _pf == "auto":',
    '            _pf = _auto_profile(" ".join(args.question))',
    '            print(f"   ✓ 成本档位：auto → {_pf}（按题面规则选定）")',
    "        else:",
    '            print(f"   ✓ 成本档位：{_pf}")',
    '        cfg["cost_profile"] = _pf',
]

i = find_row(lambda l: l == "    cfg = load_config(args.config)", "load_config")
lines[i + 1:i + 1] = [
    '    cfg.setdefault("actions", {})["appendix_mode"] = args.appendix',
]

out = "\n".join(lines)
out_b = out.replace("\n", "\r\n").encode("utf-8")
assert out_b.count(b"\r\n") == out_b.count(b"\n"), "写出前 CRLF 校验失败"
assert out_b.count(b"\r\r\n") == 0, "出现 CRCRLF"
SRC.write_bytes(out_b)

chk = SRC.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\r\n") == chk.count(b"\n")
import ast  # noqa: E402
ast.parse(chk.decode("utf-8"))
_c = chk.decode("utf-8")
print(f"OK 行数 {N0} → {_c.count(chr(10)) + 1}")
for _n in ("_with_form_declaration", "_auto_profile", "_appendix_to_file"):
    print(f"  新函数 {_n}: {'def %s(' % _n in _c}")
print("  appendix 参数:", 'parser.add_argument("--appendix"' in _c)
print("  v1.23.9 残留:", "v1.23.9" in _c.replace("元 DGTF · v1.23.10", ""))

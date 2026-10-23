# -*- coding: utf-8 -*-
"""给 smoke_test.py 加 v1.21.76 的 7 条 check_v76_*（另加 2 条本轮 M1/S1）。

判别力要求：SRC 指回 v1.21.75 时，至少 changelog / 两通道 / claims 三条判红。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SMOKE = HERE / "smoke_test.py"

FUNC = '''

def _v76_strip(src: str) -> str:
    """抠掉 docstring 与注释 —— 判据只能扫**代码**。

    ★ 必须先 dedent：`_v76_body` 返回的是带缩进的片段，直接 ast.parse
      会 SyntaxError（unexpected indent）→ 静默退回原文 → docstring 里
      提到的符号被当成代码（v1.21.76 实测踩过：`_before_round` 体被数成
      2 处 `_anchor_round` 调用，真值 1）。
    """
    import ast as _ast
    import io as _io
    import textwrap as _tw
    import tokenize as _tk
    src = _tw.dedent(src)
    kill = set()
    try:
        tree = _ast.parse(src)
        for node in _ast.walk(tree):
            if not isinstance(node, (_ast.Module, _ast.FunctionDef,
                                     _ast.AsyncFunctionDef, _ast.ClassDef)):
                continue
            body = getattr(node, "body", None) or []
            if (body and isinstance(body[0], _ast.Expr)
                    and isinstance(body[0].value, _ast.Constant)
                    and isinstance(body[0].value.value, str)):
                d = body[0]
                for ln in range(d.lineno, (d.end_lineno or d.lineno) + 1):
                    kill.add(ln)
    except SyntaxError:
        pass
    try:
        for tok in _tk.generate_tokens(_io.StringIO(src).readline):
            if tok.type == _tk.COMMENT:
                kill.add(tok.start[0])
    except Exception:
        pass
    lines = src.split("\\n")
    return "\\n".join("" if (i + 1) in kill else l
                     for i, l in enumerate(lines))


def _v76_src() -> str:
    raw = SRC.read_text(encoding="utf-8").replace("\\r\\r\\n", "\\n")
    return raw.replace("\\r\\n", "\\n").replace("\\r", "\\n")


def _v76_body(name: str) -> str:
    """取 SRC 里名为 name 的方法体（已抠文档）。"""
    import re as _re
    lines = _v76_src().split("\\n")
    start = None
    for i, l in enumerate(lines):
        if _re.match(r"\\s*def " + _re.escape(name) + r"\\s*\\(", l):
            start = i
            break
    if start is None:
        return ""
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _re.match(r"\\s*def \\w+\\s*\\(", lines[j]) and \\
                len(lines[j]) - len(lines[j].lstrip()) <= indent:
            end = j
            break
    return _v76_strip("\\n".join(lines[start:end]))


def check_v76_anchor_two_channels():
    """[v1.21.76 A1] 圈前动作只走一个入口 —— 防「只在一个通道接线」。

    ★ 改前实测：`self._anchor_round(` 全源码 1 处（在 `_run_layer`），
      `_before_round` 0 处；`_run_one_round_B` 含 `_print_polarity_snapshot`
      但不含 `_anchor_round` → B/C/D-H 七模式锚点恒为空。
    """
    print("\\n[v1.21.76 A1] 锚点入池的通道覆盖")
    import re as _re
    code = _v76_strip(_v76_src())
    bad = []
    n_def = len(_re.findall(r"^\\s*def _before_round\\s*\\(", code, _re.M))
    n_call = code.count("self._before_round(")
    n_round = code.count("self._anchor_round(")
    n_snap = code.count("self._print_polarity_snapshot(")
    if n_def != 1:
        bad.append(f"[A1] `_before_round` 定义 {n_def} 处，期望 1")
    if n_call != 2:
        bad.append(f"[A1] `_before_round` 调用 {n_call} 处，期望 2"
                   f"（serial + B 两条通道各一）")
    if n_round != 1:
        bad.append(f"[A1] `_anchor_round` 直接调用 {n_round} 处，期望 1"
                   f"（只该在 `_before_round` 里）")
    if n_snap != 1:
        bad.append(f"[A1] `_print_polarity_snapshot` 直接调用 {n_snap} 处，"
                   f"期望 1（只该在 `_before_round` 里）")
    _br = _v76_body("_before_round")
    if "self._anchor_round(" not in _br:
        bad.append("[A1] `_before_round` 里没有调 `_anchor_round` —— 空壳")
    _b = _v76_body("_run_one_round_B")
    if "_before_round" not in _b:
        bad.append("[A1] `_run_one_round_B` 里没有 `_before_round`"
                   " —— B 通道又不入锚点了")
    _rl = _v76_body("_run_layer")
    if "_before_round" not in _rl:
        bad.append("[A1] `_run_layer` 里没有 `_before_round`")
    # 负对照：立刻在**原文**里验一次"抠文档确实生效"
    if "self._anchor_round(" in _v76_src() and n_round == 0:
        bad.append("[A1] 抠文档后数为 0 但原文有 —— 抠除逻辑坏了")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print(f"  \\u2713 _before_round def=1 调用=2；_anchor_round 直调=1"
          f"（在 _before_round 内）；_print_polarity_snapshot 直调=1")
    print("  \\u2713 serial(`_run_layer`) 与 B(`_run_one_round_B`) 都走统一入口")
    return True


def check_v76_anchor_calls():
    """[v1.21.76 A2] `_anchor_calls` 必须**真的被赋值**，且不再挂预算空档。

    ★ 改前实测：该字段全源码出现 2 次、**都是读**、0 次写 →
      v1.21.75 宣称的"检索调用纳预算"是恒为 0 的挂空档。
    """
    print("\\n[v1.21.76 A2] anchor_calls 真的被写入")
    code = _v76_strip(_v76_src())
    bad = []
    if code.count("self._anchor_calls: int = 0") != 1:
        bad.append("[A2] `__init__` 里没有唯一的 `self._anchor_calls: int = 0`")
    _cc = _v76_body("_anchor_crosscheck")
    if not _re_find(r"self\\._anchor_calls[^\\n]*\\+\\s*1", _cc):
        bad.append("[A2] `_anchor_crosscheck` 里没有自增 —— 还是只读不写")
    if '"anchor_calls": self._anchor_calls' not in _cc:
        bad.append("[A2] packed 的 `anchor_calls` 没有回填本次计数")
    _be = _v76_body("_budget_exhausted")
    if "_anchor_calls" in _be:
        bad.append("[A2] `_budget_exhausted` 还在引用 `_anchor_calls`"
                   " —— 收尾对照不在圈循环内，不该挂这里")
    if "预算已用尽" not in _cc:
        bad.append("[A2] `_anchor_crosscheck` 缺独立预算判断（且要留痕）")
    # 负对照：旧版必须被判红
    if not bad and "self._anchor_calls" in _v76_src() and \\
            code.count("self._anchor_calls") == 0:
        bad.append("[A2] 抠文档后为 0 —— 抠除逻辑坏了")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 初始化 1 处 + 收尾对照自增 1 处 + packed 回填")
    print("  \\u2713 `_budget_exhausted` 已不再挂空档；收尾对照有独立预算判断")
    return True


def _re_find(pat: str, text: str) -> bool:
    import re as _re
    return _re.search(pat, text) is not None


def check_v76_changelog_wording():
    """[v1.21.76 B1] changelog 不许说「重做/改到池」—— 外判接入点还在。"""
    print("\\n[v1.21.76 B1] changelog 措辞与实现一致")
    raw = _v76_src()
    bad = []
    if "重做**锚点接入" in raw or "接入点从「外判」改到「池」" in raw:
        bad.append("[B1] 仍有「重做锚点接入 / 改到池」的旧措辞")
    if "新增池接入点" not in raw:
        bad.append("[B1] 找不到「新增池接入点」")
    if "v1.21.76" not in raw:
        bad.append("[B1] 找不到 v1.21.76 changelog 段")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 措辞已改为「新增池接入点」（外判接入点保留）")
    print("  \\u2713 v1.21.76 changelog 段存在")
    return True


def check_v76_anchor_visibility():
    """[v1.21.76 B2] 池判的可见性必须写清（只读第 1 圈）。"""
    print("\\n[v1.21.76 B2] 锚点可见性说明")
    body = _v76_body("_anchor_view_ctx")
    bad = []
    if "只跑一次" not in body and "只读" not in body:
        bad.append("[B2] `_anchor_view_ctx` 没说清池判只跑一次/只读第 1 圈")
    if "per_round" not in body:
        bad.append("[B2] 没提 `per_round`")
    if "max_items" not in body:
        bad.append("[B2] 没提 `max_items` 上限")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 docstring 写明：池判只跑一次、只看得见第 1 圈那批"
          "（受 max_items 约束）")
    return True


def check_v76_anchor_evidence_key():
    """[v1.21.76 B3] `Pool.to_dict` 必须挂 `anchor_as_evidence`，且受保护。"""
    print("\\n[v1.21.76 B3] anchor_as_evidence 有出口")
    import re as _re
    code = _v76_strip(_v76_src())
    bad = []
    tds = _re.findall(
        r"\\n    def to_dict\\(self\\) -> dict:.*?(?=\\n    def |\\Z)", code, _re.S)
    hit = [t for t in tds if "anchor_as_evidence" in t]
    if not hit:
        bad.append("[B3] 没有哪个 `to_dict` 挂 `anchor_as_evidence`")
    else:
        t = hit[-1]
        if 'd["anchors"] = self.anchors' not in t:
            bad.append("[B3] 没有跟着 `anchors` 一起挂（加性会破）")
        i_an = t.find('d["anchors"] = self.anchors')
        i_ae = t.find('d["anchor_as_evidence"]')
        if not (-1 < i_an < i_ae):
            bad.append("[B3] `anchor_as_evidence` 没在 `if self.anchors` 块内")
        # 负对照：无 anchors 时不该挂（块结构必须保持）
        if "if self.anchors:" not in t:
            bad.append("[B3] `if self.anchors:` 守卫不见了（关闭态会多键）")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 `to_dict` 在 `if self.anchors:` 块内挂 `anchor_as_evidence`"
          "（关闭态仍一个键不多）")
    return True


def check_v76_anchor_retriever_stub():
    """[v1.21.76 B4] snapshot 不该走检索层；未实现的后端仍要抛错。"""
    print("\\n[v1.21.76 B4] 检索层只在非 snapshot 走")
    body = _v76_body("_anchor_round")
    bad = []
    if '_mode != "snapshot"' not in body:
        bad.append("[B4] `_anchor_round` 里没有 `_mode != \"snapshot\"` 分支")
    ret = _v76_body("_retrieve_anchors")
    if "尚未实现" not in ret:
        bad.append("[B4] `_retrieve_anchors` 丢了「尚未实现」的抛错"
                   " —— 等于允许静默降级")
    if "不静默降级" not in ret:
        bad.append("[B4] 抛错里没有「不静默降级」的表态")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 snapshot 直接跳过检索层（零调用）；非 snapshot 抛错留痕")
    return True


def check_v76_anchor_triage_cohesion():
    """[v1.21.76 B5] 分诊判据必须与锚点清单**同段**（不跨 system/user）。"""
    print("\\n[v1.21.76 B5] 分诊判据不跨段")
    ts = _v76_body("_anchor_triage_sys")
    vc = _v76_body("_anchor_view_ctx")
    bad = []
    if 'return ""' not in ts:
        bad.append("[B5] `_anchor_triage_sys` 没退化成空壳")
    if "【外部锚点分诊】" in ts or "分诊判据" in ts:
        bad.append("[B5] `_anchor_triage_sys` 里还留着分诊判据")
    if "【分诊判据" not in vc:
        bad.append("[B5] `_anchor_view_ctx` 里没有【分诊判据】段")
    if "自指循环" not in vc:
        bad.append("[B5] 分诊判据内容不全（缺「自指循环不降级」那条）")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 `_anchor_triage_sys` 已空壳；判据与锚点清单同处 user 段")
    return True


def check_v76_claims_scope():
    """[v1.21.76 M1] 对照条目必须含 `views[*].candidates`（领域事实层）。"""
    print("\\n[v1.21.76 M1] claims 取值处含 candidates")
    body = _v76_body("_anchor_claims")
    bad = []
    if '"candidates"' not in body and "'candidates'" not in body:
        bad.append("[M1] `_anchor_claims` 没有取 `candidates`")
    if "candidates" not in body:
        bad.append("[M1] 缺 candidates 来源说明")
    if "decidable_product" not in body:
        bad.append("[M1] 原有来源（成品答案）被误删")
    if "sub_questions" not in body:
        bad.append("[M1] 原有来源（已答子问题）被误删")
    # candidates 必须排在成品答案**之前**（领域层优先占配额）
    i_c = body.find('"candidates"')
    i_d = body.find("decidable_product")
    if i_c != -1 and i_d != -1 and i_c > i_d:
        bad.append("[M1] candidates 排在成品答案之后 —— 会被 12 条配额挤掉")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 `_anchor_claims` 三处来源齐备，candidates 优先")
    return True


def check_v76_input_sanity_shape():
    """[v1.21.76 S1] 输入自检必须显式覆盖「形似标准记号的非标准记号」。"""
    print("\\n[v1.21.76 S1] 输入自检补 P=PN 型判据")
    body = _v76_body("_check_input_sanity")
    bad = []
    if "形似标准记号" not in body:
        bad.append("[S1] 判据里没有「形似标准记号的非标准记号」")
    if "P=PN" not in body and "PN" not in body:
        bad.append("[S1] 没有点出 `P=PN` 这个真实漏报案例")
    if bad:
        for b in bad:
            print(f"  \\u2717 {b}")
        return False
    print("  \\u2713 判据已显式覆盖伪专名，并写明 P=PN 漏报案例")
    return True
'''

CALLS = (
    "    if not check_v76_anchor_two_channels():\n        return 1\n"
    "    if not check_v76_anchor_calls():\n        return 1\n"
    "    if not check_v76_changelog_wording():\n        return 1\n"
    "    if not check_v76_anchor_visibility():\n        return 1\n"
    "    if not check_v76_anchor_evidence_key():\n        return 1\n"
    "    if not check_v76_anchor_retriever_stub():\n        return 1\n"
    "    if not check_v76_anchor_triage_cohesion():\n        return 1\n"
    "    if not check_v76_claims_scope():\n        return 1\n"
    "    if not check_v76_input_sanity_shape():\n        return 1\n"
)


def main() -> None:
    b = SMOKE.read_bytes()
    t = b.decode("utf-8").replace("\r\r\n", "\n").replace("\r\n", "\n")
    t = t.replace("\r", "\n")

    # 插函数：check_v75_anchor_pool 之后的下一个顶层 def 之前
    lines = t.split("\n")
    i75 = next(i for i, l in enumerate(lines)
               if l.startswith("def check_v75_anchor_pool("))
    j = i75 + 1
    while j < len(lines) and not lines[j].startswith("def "):
        j += 1
    lines[j:j] = FUNC.split("\n")
    t = "\n".join(lines)
    print(f"  [9 条判据] 插在第 {j+1} 行前")

    old_call = "    if not check_v75_anchor_pool():\n        return 1\n"
    assert t.count(old_call) == 1, t.count(old_call)
    t = t.replace(old_call, old_call + CALLS)
    print("  [main 接线] 9 条")

    out = t.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\n") == out.count(b"\n")
    SMOKE.write_bytes(out)
    print(f"已更新 {SMOKE.name}（{len(out)} 字节，纯 CRLF）")


if __name__ == "__main__":
    main()

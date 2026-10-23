# -*- coding: utf-8 -*-
"""v1.23.47：插 P-2b 判据 + 切两处 SRC + 加 M98 + 登记 + 接 runner + yaml 头/升级段。"""
import ast
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
MUT = HERE / "_mut_v12332.py"
ENG = HERE / "元DGTF-V1.23.47.py"
YML = HERE / "dgtf_config.yaml"


def _rw(path, fn):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    assert s2 != s
    ast.parse(s2)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0 and out.count(b"\n") == out.count(b"\r\n")
    path.write_bytes(out)
    return out.decode("utf-8")


snippet = (Path("_v12347_judge_snippet.py").read_bytes().decode("utf-8")
           .replace("\r\n", "\n").rstrip() + "\n\n\n")


def _sm(s):
    a = "def check_v12346_duty_span():"
    assert s.count(a) == 1
    s = s.replace(a, snippet + a, 1)
    c = "    if not check_v12346_duty_span():\n        return 1\n"
    assert s.count(c) == 1
    s = s.replace(c, c + "    if not check_v12347_gain_suggest():\n"
                        "        return 1\n", 1)
    s = s.replace('SRC = HERE / "元DGTF-V1.23.46.py"',
                  'SRC = HERE / "元DGTF-V1.23.47.py"')
    return s


def _mut(s):
    s = s.replace('SRC = HERE / "元DGTF-V1.23.46.py"',
                  'SRC = HERE / "元DGTF-V1.23.47.py"')
    new = ('    ("M98 阈值建议不看质量（质量差也抬高）",\n'
           "     '    if _med >= float(quality_floor):',\n"
           "     '    if True:'),\n")
    lines = s.split("\n")
    idx = max(i for i, l in enumerate(lines) if l == "]")
    lines[idx:idx] = new.rstrip("\n").split("\n")
    s = "\n".join(lines)
    c = '             "st.check_v12346_duty_span() and "\n'
    assert s.count(c) == 1
    s = s.replace(c, c + '             "st.check_v12347_gain_suggest() and "\n', 1)
    assert 'SRC = HERE / "元DGTF-V1.23.47.py"' in s
    return s


def _yml(s):
    lines = s.split("\n")
    i = next(k for k, l in enumerate(lines)
             if l.startswith("# 元 DGTF · v1.23.46 配置文件"))
    lines[i] = "# 元 DGTF · v1.23.47 配置文件"
    j = next(k for k, l in enumerate(lines) if l.startswith("# 【v1.23.45 → v1.23.46】"))
    NEW = [
        "# 【v1.23.46 → v1.23.47】P-2b 早停阈值跨跑建议 —— **无新增配置键**",
        "#   依据：SOTA 点名 static thresholds 是学习回路失败模式 ⇒ α 该跟着历史跑调。",
        "#   新增纯函数 autotune_suggest_gain_floor：从「被截断的层 + 当时质量」推建议 α",
        "#   （截断多且质量不差 ⇒ 该早停 ⇒ 建议抬高）；挂进 autotune_phase_learn 输出。",
        "#   ★ 红线「建议与执行分开」：只出建议，采纳仍走 autotune_apply_to_cfg。",
        "",
    ]
    lines[j:j] = NEW
    return "\n".join(lines)


if __name__ == "__main__":
    _rw(SM, _sm)
    print("[ok] smoke：判据已插 + SRC→V1.23.47")
    _rw(MUT, _mut)
    print("[ok] _mut：SRC→V1.23.47 + M98 + runner 已接")
    _rw(YML, _yml)
    print("[ok] yaml：头 + 升级段")
    p = HERE / "_v122_ast_registry.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["registry"].setdefault("autotune_suggest_gain_floor", {
        "phase": "47",
        "reason": "P-2b 从历史跑建议早停阈值 α（截断多且质量不差 ⇒ 建议抬高）"})
    d["n_symbols_current"] = int(d["n_symbols_current"]) + 1
    d["current"] = "元DGTF-V1.23.47.py"
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[ok] registry:", len(d["registry"]), "条")
    eng = ENG.read_bytes().decode("utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("mm", str(MUT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["mm"] = m
    spec.loader.exec_module(m)
    print("[ok] MUTS 总数:", len(m.MUTS))
    for nm, old, nw in m.MUTS:
        if nm.startswith("M98"):
            h = eng.count(old)
            mut = eng.replace(old, nw, 1)
            try:
                ast.parse(mut)
                aok = "OK"
            except SyntaxError as e:
                aok = "ERR %s" % e
            print("  %s | 命中 %d | 变异后 %s" % (nm[:30], h, aok))

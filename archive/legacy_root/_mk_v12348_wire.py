# -*- coding: utf-8 -*-
"""v1.23.48：插 P-3b 判据 + 切两处 SRC + 加 M99 + 接 runner + yaml/params。"""
import ast
import importlib.util
import sys
import yaml
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
MUT = HERE / "_mut_v12332.py"
ENG = HERE / "元DGTF-V1.23.48.py"


def _rw_py(path, fn):
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


snippet = (Path("_v12348_judge_snippet.py").read_bytes().decode("utf-8")
           .replace("\r\n", "\n").rstrip() + "\n\n\n")


def _sm(s):
    a = "def check_v12347_gain_suggest():"
    assert s.count(a) == 1
    s = s.replace(a, snippet + a, 1)
    c = "    if not check_v12347_gain_suggest():\n        return 1\n"
    assert s.count(c) == 1
    s = s.replace(c, c + "    if not check_v12348_eml_semantic():\n"
                        "        return 1\n", 1)
    s = s.replace('SRC = HERE / "元DGTF-V1.23.47.py"',
                  'SRC = HERE / "元DGTF-V1.23.48.py"')
    return s


def _mut(s):
    s = s.replace('SRC = HERE / "元DGTF-V1.23.47.py"',
                  'SRC = HERE / "元DGTF-V1.23.48.py"')
    new = ('    ("M99 语义近重合并失效（粗键永不命中）",\n'
           "     '        if _ek != _key and _coarse is not None:',\n"
           "     '        if False:'),\n")
    lines = s.split("\n")
    idx = max(i for i, l in enumerate(lines) if l == "]")
    lines[idx:idx] = new.rstrip("\n").split("\n")
    s = "\n".join(lines)
    c = '             "st.check_v12347_gain_suggest() and "\n'
    assert s.count(c) == 1
    s = s.replace(c, c + '             "st.check_v12348_eml_semantic() and "\n', 1)
    assert 'SRC = HERE / "元DGTF-V1.23.48.py"' in s
    return s


if __name__ == "__main__":
    _rw_py(SM, _sm)
    print("[ok] smoke：判据已插 + SRC→V1.23.48")
    _rw_py(MUT, _mut)
    print("[ok] _mut：SRC→V1.23.48 + M99 + runner 已接")
    # yaml（不用 ast.parse）
    p = HERE / "dgtf_config.yaml"
    raw = p.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
    i = next(k for k, l in enumerate(lines)
             if l.startswith("# 元 DGTF · v1.23.47 配置文件"))
    lines[i] = "# 元 DGTF · v1.23.48 配置文件"
    j = next(k for k, l in enumerate(lines) if l.startswith("# 【v1.23.46 → v1.23.47】"))
    lines[j:j] = [
        "# 【v1.23.47 → v1.23.48】P-3b EML commit 前语义近重合并 —— 新增配置键 memory.eml_semantic_merge",
        "#   ① 实测：eml_merge_candidate 只按**精确** (kind,cond,action) 去重 ⇒ 值差一点",
        "#      （delta=1 vs 2、rate=0.30 vs 0.31）就另开一条 ⇒ 冗余堆积。",
        "#      这是 SOTA 点名的 failure mode：noisy accumulation / redundancy。",
        "#   ② 修法：加 semantic_merge 形参 —— 精确键不中再按**粗键**（kind + cond.issue +",
        "#      action.key）找已有条目 ⇒ 命中则并入（证据累加），不再新开。",
        "#   ③ 新键 memory.eml_semantic_merge：**默认 false = 关 ⇒ 逐字零行为差**。",
        "",
    ]
    p.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))
    chk = p.read_bytes()
    assert chk.count(b"\n") == chk.count(b"\r\n")
    d = yaml.safe_load(chk.decode("utf-8"))
    print("[ok] yaml -> v1.23.48 | memory.eml_semantic_merge =",
          d["memory"]["eml_semantic_merge"])
    # params.py（纯 LF）
    q = HERE / "dgtf_app/params.py"
    t = q.read_bytes().decode("utf-8")
    anchor = '    "memory.eml_adaptive": "EML 阈值冷启自适应（库小时降晋升门槛；默认关）",\n'
    assert t.count(anchor) == 1
    t = t.replace(anchor, anchor
                  + '    "memory.eml_semantic_merge": "EML 语义近重合并（值差也并入；默认关）",\n', 1)
    q.write_bytes(t.encode("utf-8"))
    print("[ok] params.py 加了 memory.eml_semantic_merge 标签")
    # M99 校验
    eng = ENG.read_bytes().decode("utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("mm", str(MUT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["mm"] = m
    spec.loader.exec_module(m)
    print("[ok] MUTS 总数:", len(m.MUTS))
    for nm, old, nw in m.MUTS:
        if nm.startswith("M99"):
            h = eng.count(old)
            mut = eng.replace(old, nw, 1)
            try:
                ast.parse(mut)
                aok = "OK"
            except SyntaxError as e:
                aok = "ERR %s" % e
            print("  %s | 命中 %d | 变异后 %s" % (nm[:30], h, aok))

# -*- coding: utf-8 -*-
"""v1.23.49：插判据 + 切两处 SRC + 加 M100 + 登记 + 接 runner + yaml/params。"""
import ast
import importlib.util
import json
import sys
import yaml
from pathlib import Path

HERE = Path(__file__).resolve().parent
SM = HERE / "smoke_test.py"
MUT = HERE / "_mut_v12332.py"
ENG = HERE / "元DGTF-V1.23.49.py"


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


snippet = (Path("_v12349_judge_snippet.py").read_bytes().decode("utf-8")
           .replace("\r\n", "\n").rstrip() + "\n\n\n")


def _sm(s):
    a = "def check_v12348_eml_semantic():"
    assert s.count(a) == 1
    s = s.replace(a, snippet + a, 1)
    c = "    if not check_v12348_eml_semantic():\n        return 1\n"
    assert s.count(c) == 1
    s = s.replace(c, c + "    if not check_v12349_run_ckpt():\n"
                        "        return 1\n", 1)
    s = s.replace('SRC = HERE / "元DGTF-V1.23.48.py"',
                  'SRC = HERE / "元DGTF-V1.23.49.py"')
    return s


def _mut(s):
    s = s.replace('SRC = HERE / "元DGTF-V1.23.48.py"',
                  'SRC = HERE / "元DGTF-V1.23.49.py"')
    new = ('    ("M100 孤儿回收不判过期（永远不动）",\n'
           "     '        if _age < float(stale_sec):',\n"
           "     '        if True:'),\n")
    lines = s.split("\n")
    idx = max(i for i, l in enumerate(lines) if l == "]")
    lines[idx:idx] = new.rstrip("\n").split("\n")
    s = "\n".join(lines)
    c = '             "st.check_v12348_eml_semantic() and "\n'
    assert s.count(c) == 1
    s = s.replace(c, c + '             "st.check_v12349_run_ckpt() and "\n', 1)
    assert 'SRC = HERE / "元DGTF-V1.23.49.py"' in s
    return s


if __name__ == "__main__":
    _rw_py(SM, _sm)
    print("[ok] smoke：判据已插 + SRC→V1.23.49")
    _rw_py(MUT, _mut)
    print("[ok] _mut：SRC→V1.23.49 + M100 + runner 已接")
    # 登记 5 个新符号
    p = HERE / "_v122_ast_registry.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    for nm, rsn in (
            ("run_ckpt_dir", "跑中快照目录（outputs/_run_ckpt/）"),
            ("run_ckpt_path", "跑中快照路径"),
            ("write_run_ckpt", "原子写跑中快照（tmp + os.replace）"),
            ("_ckpt_snapshot", "从引擎抽可恢复状态（各层 View.to_dict）"),
            ("start_run_ckpt", "起 daemon 心跳线程（返回 stop 回调）"),
            ("stop_run_ckpt", "停心跳并落最后一份"),
            ("recover_orphan_runs", "孤儿快照回填 interrupted（幂等）")):
        d["registry"].setdefault(nm, {"phase": "49", "reason": rsn})
    d["n_symbols_current"] = int(d["n_symbols_current"]) + 7
    d["current"] = "元DGTF-V1.23.49.py"
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[ok] registry:", len(d["registry"]), "条")
    # yaml（不用 ast.parse）
    y = HERE / "dgtf_config.yaml"
    raw = y.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
    i = next(k for k, l in enumerate(lines)
             if l.startswith("# 元 DGTF · v1.23.48 配置文件"))
    lines[i] = "# 元 DGTF · v1.23.49 配置文件"
    j = next(k for k, l in enumerate(lines) if l.startswith("# 【v1.23.47 → v1.23.48】"))
    lines[j:j] = [
        "# 【v1.23.48 → v1.23.49】跑中快照 —— 新增配置键 runtime.live_checkpoint / runtime.ckpt_interval",
        "#   ① 根因：MetaDGTF.run() 是 60 分钟级长跑，packed 只在 return 前组装、调用方只在",
        "#      返回后才写盘 ⇒ 宿主一回收进程，连层 0 的五圈都消失（12:37 真跑就这么丢了 ~24 分钟）。",
        "#   ② 解法：run() 起 daemon 心跳线程，每 N 秒把 self._results（各层 View.to_dict）",
        "#      **原子**落盘（tmp + os.replace ⇒ 强杀也不会留半份）⇒ 最多丢一个间隔。",
        "#   ③ 孤儿回收：recover_orphan_runs() 把「起跑过但没收尾」的回填 interrupted + 原因。",
        "#   ④ 新键 runtime.live_checkpoint：**默认 false = 关 ⇒ 逐字零行为差**（是否该默认开，",
        "#      待用户拍板——它是纯安全网，不影响任何引擎输出）。",
        "",
    ]
    y.write_bytes("\n".join(lines).replace("\n", "\r\n").encode("utf-8"))
    chk = y.read_bytes()
    assert chk.count(b"\n") == chk.count(b"\r\n")
    d2 = yaml.safe_load(chk.decode("utf-8"))
    print("[ok] yaml -> v1.23.49 | runtime.live_checkpoint =",
          d2["runtime"]["live_checkpoint"],
          "| ckpt_interval =", d2["runtime"]["ckpt_interval"])
    # params.py
    q = HERE / "dgtf_app/params.py"
    t = q.read_bytes().decode("utf-8")
    anchor = '    "memory.eml_semantic_merge": "EML 语义近重合并（值差也并入；默认关）",\n'
    assert t.count(anchor) == 1
    t = t.replace(anchor, anchor
                  + '    "runtime.live_checkpoint": "跑中快照（心跳落盘，防中断全丢；默认关）",\n'
                    '    "runtime.ckpt_interval": "跑中快照心跳间隔（秒）",\n', 1)
    q.write_bytes(t.encode("utf-8"))
    print("[ok] params.py 加了 runtime.live_checkpoint / ckpt_interval 标签")
    # M100 校验
    eng = ENG.read_bytes().decode("utf-8").replace("\r\n", "\n")
    spec = importlib.util.spec_from_file_location("mm", str(MUT))
    m = importlib.util.module_from_spec(spec)
    sys.modules["mm"] = m
    spec.loader.exec_module(m)
    print("[ok] MUTS 总数:", len(m.MUTS))
    for nm, old, nw in m.MUTS:
        if nm.startswith("M100"):
            h = eng.count(old)
            mut = eng.replace(old, nw, 1)
            try:
                ast.parse(mut)
                aok = "OK"
            except SyntaxError as e:
                aok = "ERR %s" % e
            print("  %s | 命中 %d | 变异后 %s" % (nm[:30], h, aok))

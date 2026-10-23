# -*- coding: utf-8 -*-
"""v1.23.60 开发期验证：快照记层内进度，且**续跑行为一个字没变**。

判据：
  A 快照里有 `layer_progress.<层>.rounds_done`，且 == 该层 `rounds_run`；含本圈目标读数
  B `goal_hist.<层>` 条数 == `rounds_run`（跨圈历史也进了快照）
  C `load_resume_snapshot` 返回键集合**没变**，且函数体里没有这两个字段（只记不恢复）
  D 已完成的快照**拒绝**续跑（`ok=False`）—— 既有正确行为，别被这次改动带坏
"""
import importlib.util
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

Q = "冒烟题面：这件事的边界在哪里（v12360 层内进度判据）"
bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


def load(py):
    spec = importlib.util.spec_from_file_location("p60_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    m.LLM._real_call = m.LLM.call
    m.LLM.call = st.fake_call
    assert getattr(m.LLM.call, "__name__", "") == "fake_call", "LLM 桩没装上"
    return m


def mkcfg(mod, mem):
    c = mod.load_config(str(HERE / "__nonexistent__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="v60out_")))
    c["playbook"] = {"mode": "off", "dir": str(mem)}
    c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(mem)
    c.setdefault("runtime", {})
    c["runtime"]["live_checkpoint"] = True
    c["runtime"]["ckpt_interval"] = 0.05
    c["all_on"] = False
    return c


new = load(HERE / "元DGTF-V1.23.60.py")
ckdir = pathlib.Path(tempfile.mkdtemp(prefix="v60ck_"))
mem = pathlib.Path(tempfile.mkdtemp(prefix="v60mem_"))
orig = new.run_ckpt_dir
new.run_ckpt_dir = lambda base=None: ckdir
rid = "CK60A"
try:
    new.MetaDGTF(mkcfg(new, mem)).run(
        Q, route=["0"], rounds={"0": 3}, parallel_mode="serial", run_id=rid)
    p = ckdir / ("%s.json" % rid)
    d = json.loads(p.read_text(encoding="utf-8"))
    v0 = (d.get("views") or {}).get("0") or {}
    rr = int(v0.get("rounds_run") or 0)

    print("=" * 62)
    print("【A】快照里有 layer_progress，且圈数与视图一致")
    lp = d.get("layer_progress") or {}
    e0 = lp.get("0") or {}
    ck("0" in lp, "layer_progress 含层 0：%r" % (list(lp),))
    ck(int(e0.get("rounds_done") or 0) >= 1,
       "rounds_done=%r（≥1）" % (e0.get("rounds_done"),))
    ck(int(e0.get("rounds_done") or -1) == rr,
       "rounds_done(%r) == rounds_run(%r)"
       % (e0.get("rounds_done"), rr))
    ck("goal" in e0, "含本圈目标读数：%r" % (list(e0.get("goal") or {}),))

    print("\n【B】goal_hist 也进了快照，条数 == 圈数")
    gh = (d.get("goal_hist") or {}).get("0") or []
    ck(len(gh) == rr, "goal_hist 条数=%d == rounds_run=%d" % (len(gh), rr))

    print("\n【C】续跑侧**不读**这两个字段")
    _rs = new.load_resume_snapshot(str(p), str(mem))
    ck(set(_rs) == {"ok", "why", "views", "pools", "llm_calls", "llm_tokens"},
       "返回键集合没变：%r" % (sorted(_rs),))
    _src = (HERE / "元DGTF-V1.23.60.py").read_text(encoding="utf-8")
    # ★ 抠函数体必须走 AST：用 `split("\ndef ")` 会把后面 7700 行（类方法缩进 4 格）
    #   全当成这个函数的体 ⇒ 判据测的是整份文件，永远判红。
    import ast as _ast
    _tree = _ast.parse(_src)
    _body = ""
    for _n in _ast.walk(_tree):
        if isinstance(_n, _ast.FunctionDef) and _n.name == "load_resume_snapshot":
            _body = _ast.get_source_segment(_src, _n) or ""
            break
    ck(bool(_body), "取到 load_resume_snapshot 函数体（%d 行）" % _body.count("\n"))
    ck("layer_progress" not in _body and "goal_hist" not in _body,
       "函数体里没有这两个字段（只记不恢复）")

    print("\n【D】已完成的快照拒绝续跑（既有正确行为）")
    ck(_rs.get("ok") is False, "ok=False（%r）" % (_rs.get("why"),))
except Exception as ex:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    bad.append("异常：%r" % (ex,))
finally:
    new.run_ckpt_dir = orig

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)

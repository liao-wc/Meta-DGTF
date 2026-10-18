# -*- coding: utf-8 -*-
"""v1.23.63 开发期验证：`json_mode` 解析失败会留痕（且不改控制流）。

★ 为什么直接驱动 `LLM.call` 而不跑整层：修行层 1 圈**根本不走 json_mode 环节**
  （实测：注入散文后 `llm_bad_json` 仍是 0 —— 不是钩子坏了，是这条路径上没有
  json_mode 调用）。这是「判据的触发条件在测试路径上到不了」的老坑，所以
  这一支改成**最小粒度的真入口**：直接调 `LLM.call(json_mode=True)`。

判据：
  A json_mode=True + 散文 ⇒ `bad_json` +1，且返回原文（控制流不变）
  B json_mode=True + "null" ⇒ 同样 +1
  C 负对照：json_mode=False + 散文 ⇒ **不计数**（不该误记为"JSON 失败"）
  D json_mode=True + 合法 JSON ⇒ 不计数
  E 产物出口：正常运行 ⇒ 字段存在且为 0
  F 旧版对照：v1.23.62 的 LLM 没有 `bad_json` 属性
"""
import importlib.util
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

bad, ok = [], []


def ck(cond, msg):
    (ok if cond else bad).append(msg)
    print(("  [OK]   " if cond else "  [BAD]  ") + msg)
    return bool(cond)


class _Resp:
    def __init__(self, c):
        self.choices = [type("C", (), {
            "message": type("M", (), {"content": c})(),
            "finish_reason": "stop"})()]
        self.usage = type("U", (), {"total_tokens": 11})()


def load(py):
    spec = importlib.util.spec_from_file_location("j63_" + py.stem[-5:], str(py))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def llm_with(mod, text):
    c = mod.load_config(str(HERE / "__none__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c.setdefault("api", {})["max_retries"] = 0
    llm = mod.LLM(c)
    llm.client.chat.completions.create = lambda **kw: _Resp(text)
    llm.max_retries = 0
    llm.backoff = 1.0
    return llm


new = load(HERE / "元DGTF-V1.23.63.py")

print("=" * 62)
print("【A】json_mode=True + 散文 ⇒ 计数 +1，返回原文")
_l = llm_with(new, "答案大概是这样……一段散文。")
_out = _l.call("sys", "usr", json_mode=True)
ck(_l.bad_json == 1, "bad_json=%r" % (_l.bad_json,))
ck(_out == "答案大概是这样……一段散文。", "返回原文（控制流不变）")

print("\n【B】json_mode=True + \"null\" ⇒ 也 +1")
_l2 = llm_with(new, "null")
_l2.call("sys", "usr", json_mode=True)
ck(_l2.bad_json == 1, "bad_json=%r" % (_l2.bad_json,))

print("\n【C】负对照：json_mode=False + 散文 ⇒ 不计数")
_l3 = llm_with(new, "一段散文，本来就不是 JSON 请求。")
_l3.call("sys", "usr", json_mode=False)
ck(_l3.bad_json == 0, "bad_json=%r（应 0，不能误记）" % (_l3.bad_json,))

print("\n【D】json_mode=True + 合法 JSON ⇒ 不计数")
_l4 = llm_with(new, json.dumps({"ok": 1}, ensure_ascii=False))
_l4.call("sys", "usr", json_mode=True)
ck(_l4.bad_json == 0, "bad_json=%r（应 0）" % (_l4.bad_json,))

print("\n【E】产物出口：正常运行字段存在且为 0")
m5 = load(HERE / "元DGTF-V1.23.63.py")
m5.LLM.call = st.fake_call
c = m5.load_config(str(HERE / "__none__.yaml"))
c["api"]["key"] = "sk-smoke-test-key"
c["output"]["verbose"] = False
c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="j63o_")))
mm = pathlib.Path(tempfile.mkdtemp(prefix="j63m_"))
c["playbook"] = {"mode": "off", "dir": str(mm)}
c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(mm)
c.setdefault("runtime", {})["live_checkpoint"] = False
c["all_on"] = False
_r = m5.MetaDGTF(c).run("常识是怎么形成的", route=["0"], rounds={"0": 1},
                       parallel_mode="serial", run_id="J63E")
ck("llm_bad_json" in _r, "产物里有 llm_bad_json 字段")
ck(_r.get("llm_bad_json") == 0, "值=%r（应 0）" % (_r.get("llm_bad_json"),))

print("\n【F】旧版对照：v1.23.62 的 LLM 没有 bad_json")
old = load(HERE / "元DGTF-V1.23.62.py")
_l5 = llm_with(old, "一段散文。")
ck(not hasattr(_l5, "bad_json"), "旧版无 bad_json 属性（缺口重现）")

print("\n" + "=" * 62)
print("通过 %d / 判红 %d" % (len(ok), len(bad)))
for b in bad:
    print("  ! " + b)
sys.exit(1 if bad else 0)

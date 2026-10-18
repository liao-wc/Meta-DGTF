# -*- coding: utf-8 -*-
"""故障注入探针 v2：打**真正执行的那一层**（OpenAI client），让 `LLM.call` 的
重试/抛错逻辑真的跑起来。

★ 为什么要重做：v1 版本直接替换 `LLM.call` 本身 ⇒ 把**被测对象连同它的重试包装
  一起换掉了** ⇒ 测到的只是"各调用点对空串/乱答的反应"，而不是"生产路径遇到这些
  故障会怎样"。这正是记忆里那条「观测要在被测逻辑真正执行的那一层」。

5 种故障（都施加在 `client.chat.completions.create` 上）：
  1) 抛 RuntimeError（网络挂）
  2) content 为空字符串
  3) content 是散文（非 JSON）
  4) content 是 "null"
  5) 正常返回但内容里 candidates 类型不对
"""
import importlib.util
import json
import pathlib
import sys
import tempfile
import traceback

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402

Q = "常识是怎么形成的，它靠不靠得住"


class _Msg:
    def __init__(self, c):
        self.content = c


class _Ch:
    def __init__(self, c, finish="stop"):
        self.message = _Msg(c)
        self.finish_reason = finish


class _Resp:
    def __init__(self, c, finish="stop"):
        self.choices = [_Ch(c, finish)]
        self.usage = type("U", (), {"total_tokens": 11})()


def _patch(mod, behaviour):
    """把 create() 换成 behaviour；返回 restore 回调。"""
    spec = importlib.util.spec_from_file_location("x", str(HERE / "元DGTF-V1.23.62.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    # 真实 LLM.call 保持不动 —— 只换最底层的 create
    orig_init = m.LLM.__init__

    def _init(self, *a, **kw):
        orig_init(self, *a, **kw)
        self.client.chat.completions.create = behaviour
        self.max_retries = 1          # 少重试，探针跑快点（真实默认 2）
        self.backoff = 1.0

    m.LLM.__init__ = _init
    return m


def mkcfg(mod):
    c = mod.load_config(str(HERE / "__none__.yaml"))
    c["api"]["key"] = "sk-smoke-test-key"
    c["output"]["verbose"] = False
    c["output"]["save_dir"] = str(pathlib.Path(tempfile.mkdtemp(prefix="f2o_")))
    mm = pathlib.Path(tempfile.mkdtemp(prefix="f2m_"))
    c["playbook"] = {"mode": "off", "dir": str(mm)}
    c.setdefault("auto", {}).setdefault("bandit", {})["dir"] = str(mm)
    c.setdefault("runtime", {})["live_checkpoint"] = False
    c["all_on"] = False
    return c


def _raise(**kw):
    raise RuntimeError("simulated network down")


GOOD = st.fake_call.__wrapped__ if hasattr(st.fake_call, "__wrapped__") else None


FAULTS = [
    ("1 抛异常", _raise),
    ("2 空内容", lambda **kw: _Resp("")),
    ("3 非JSON", lambda **kw: _Resp("我觉这个问题的答案是……一段散文。")),
    ("4 null", lambda **kw: _Resp("null")),
    ("5 类型不对", lambda **kw: _Resp(
        json.dumps({"candidates": "本该是列表", "threads": 42},
                   ensure_ascii=False))),
]

print("%-12s %-8s %-8s %-8s %s" % ("故障", "抛异常", "views", "errors", "备注"))
print("-" * 76)
rows = []
for name, fn in FAULTS:
    mod = _patch(None, fn)
    try:
        r = mod.MetaDGTF(mkcfg(mod)).run(
            Q, route=["0"], rounds={"0": 1}, parallel_mode="serial", run_id="F2")
        views = r.get("views") or {}
        v0 = views.get("0") or {}
        errs = v0.get("errors") if isinstance(v0, dict) else None
        n_err = len(errs or []) if isinstance(errs, (list, dict)) else 0
        note = "候选=%d" % len(v0.get("candidates") or []) if isinstance(v0, dict) else ""
        print("%-12s %-8s %-8s %-8s %s" % (name, "否", len(views), n_err, note))
        rows.append((name, False, n_err))
    except Exception as e:  # noqa: BLE001
        print("%-12s %-8s %-8s %-8s %s"
              % (name, "**是**", "-", "-", "%s: %s" % (type(e).__name__, str(e)[:36])))
        rows.append((name, True, None))
    finally:
        sys.modules.pop("x", None)

print("-" * 76)
print("异常穿透：%d / %d ｜ 静默（无异常且零 errors）：%d / %d"
      % (sum(1 for r in rows if r[1]),
         len(rows),
         sum(1 for r in rows if (not r[1]) and (r[2] or 0) == 0),
         len(rows)))

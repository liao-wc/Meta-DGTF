# -*- coding: utf-8 -*-
"""v1.23.33 打点探针：核验 `view.aspect_hist` 在**真实入口**下可达且有值。

判据（两向）：
  A. 真实入口（Orchestrator 主循环）跑完后，`view.aspect_hist` 是否非空；
  B. `pool.aspect_hist` 每圈是否都在长（len 单调不减且 >= 圈数）；
  C. 回填那一行（14713 的 falsy 检查）在首圈时 `_p0.aspect_hist` 究竟是不是 []。

做法：猴补丁包一层 `Pool.merge` / `DGTF.run`（**不改主文件**），
进出各读一次 `aspect_hist`。零花费（mock 掉 LLM）。
"""
import importlib.util
import sys
import types

SRC = "元DGTF-V1.23.33.py"

spec = importlib.util.spec_from_file_location("dgtf_probe", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_probe"] = m
spec.loader.exec_module(m)

# ---- 记录器 ----
_REC = {"merge_calls": 0, "merge_hist_after": [],
        "run_hist_before": [], "run_hist_after": [],
        "view_hist": []}

_Pool = m.Pool
_orig_merge = _Pool.merge


def _merge_spy(self, *a, **k):
    before = len(getattr(self, "aspect_hist", []) or [])
    r = _orig_merge(self, *a, **k)
    after = len(getattr(self, "aspect_hist", []) or [])
    _REC["merge_calls"] += 1
    _REC["merge_hist_after"].append((before, after))
    return r


_Pool.merge = _merge_spy

_DGTF = m.DGTF
_orig_run = _DGTF.run


def _run_spy(self, inp):
    pool = getattr(inp, "pool", None)
    _REC["run_hist_before"].append(
        None if pool is None else len(getattr(pool, "aspect_hist", []) or []))
    v = _orig_run(self, inp)
    _REC["view_hist"].append(len(getattr(v, "aspect_hist", []) or []))
    return v


_DGTF.run = _run_spy

# ---- 假 LLM：回最小合法 JSON ----
class FakeLLM:
    model = "fake"
    last_truncated = False

    def __init__(self):
        self.calls = 0

    def json_chat(self, *a, **k):
        self.calls += 1
        return {}

    def chat(self, *a, **k):
        self.calls += 1
        return ""


def main():
    cfg = dict(getattr(m, "DEFAULT_CONFIG", {}) or {})
    try:
        cfg.update(m.load_config("dgtf_config.yaml"))
    except Exception:
        pass
    llm = FakeLLM()
    # MetaDGTF 内部自建 LLM ⇒ 猴补丁类方法（零花费）
    m.LLM.json_chat = lambda self, *a, **k: {}
    m.LLM.chat = lambda self, *a, **k: ""
    orch = m.MetaDGTF(cfg)
    print("== 真实入口打点 ==")
    try:
        res = orch.run("探针问题：测试 aspect_hist 可达性", rounds=3)
    except Exception as e:
        import traceback
        print("run 异常（真跑数据仍有效）：", type(e).__name__, e)
        traceback.print_exc()
        res = None
    print("merge 调用次数 :", _REC["merge_calls"])
    print("merge 前后 len :", _REC["merge_hist_after"])
    print("run 前池 len   :", _REC["run_hist_before"])
    print("view 出口 len  :", _REC["view_hist"])
    ok_a = any(x > 0 for x in _REC["view_hist"])
    ok_b = bool(_REC["merge_hist_after"]) and all(
        a >= b for (b, a) in _REC["merge_hist_after"])
    print("判据A（view.aspect_hist 非空）:", ok_a)
    print("判据B（池序列单调不减）     :", ok_b)
    if res is not None:
        try:
            g = m.layer_goal_summary({k: v for k, v in
                                      (res.get("views") or {}).items()})
            print("layer_goal_summary:", g)
        except Exception as e:
            print("layer_goal_summary 取不到：", e)


if __name__ == "__main__":
    main()

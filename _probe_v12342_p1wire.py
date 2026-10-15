# -*- coding: utf-8 -*-
"""P-1 接线核查（轻量）：配置 `spiral.shape_limit` 是否真传到 `View.shape_of`
⇒ `_expand_from_views` 拼出的 user prompt 是否随之变短。

不整跑 mock：直接造一个大 upstream view + stub 掉 LLM.call（抓 user prompt）。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tgt", HERE / "元DGTF-V1.23.42.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["tgt"] = mod
spec.loader.exec_module(mod)
sys.path.insert(0, str(HERE))
import smoke_test as st  # noqa: E402


def _mk_view(entry="0"):
    v = mod.View(entry=entry)
    v.anchor = "一个领域里的常识是如何形成的，它可靠吗？"
    v.manifest = "显形说明" * 6
    v.candidates = [{"desc": "候选%d：一条比较长的候选描述，用来撑起长度" % i}
                    for i in range(48)]
    v.amps = [{"type": "ontological", "desc": "& 印记 %d 的较长说明文字" % i}
              for i in range(15)]
    v.threads = [{"desc": "悬空线头 %d" % i} for i in range(12)]
    v.probes = [{"question": "自问 %d？" % i, "link": "回来 %d" % i}
                for i in range(10)]
    v.suspensions = [{"target": "悬置 %d" % i, "reason": "理由 %d" % i,
                      "status": "active"} for i in range(9)]
    return v


CAPT = {}


def _run(limit):
    cfg = st.build_cfg(False)
    cfg.setdefault("spiral", {})["shape_limit"] = limit
    dg = mod.DGTF("1", st.mod.LLM(st.build_cfg(False)), cfg)
    # stub LLM.call：抓 user prompt 长度，返回空（不解析）
    users = []
    dg.llm.call = lambda system, user, *a, **k: (
        users.append(len(str(user))) or "- [concept] 占位候选，长度足够凑过解析门槛")
    pool = mod.Pool()
    up = _mk_view("0")
    dg._expand_from_views([up], pool, "锚点问题", seeds=(), context="",
                          upstream_pools=(), role="摊开", round_no=2, inp=None)
    return users


for lim in (0, 8):
    u = _run(lim)
    CAPT[lim] = sum(u)
    print("limit=%d: %d 次调用 | user prompt 合计 %d 字符 | 单次 %s"
          % (lim, len(u), sum(u), u))
print("=> user prompt 随 limit 8 变短：",
      "✅ ↓%.0f%%" % (100 * (1 - CAPT[8] / CAPT[0]))
      if CAPT[8] < CAPT[0] else "✗ 未变（接线没生效）")

# -*- coding: utf-8 -*-
"""[v1.23.3] 环境与耗时探针：key 可用？短跑多快？子问题几条？

设计依据：后续三个批次（正交度受控实验 / 思考 A/B / triage 频度批）都要
按「每次调用多贵、每跑多长」来定 n。不先量就定 n 一定会超预算。
"""
import contextlib
import importlib.util
import io
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "元DGTF-V1.23.2.py"
if not SRC.is_absolute():
    SRC = HERE / SRC

spec = importlib.util.spec_from_file_location("dgtf_env", SRC)
m = importlib.util.module_from_spec(spec)
sys.modules["dgtf_env"] = m
spec.loader.exec_module(m)
m.load_dotenv_if_any = None  # 占位（模块 import 时已 load_dotenv）

print("[env] src=%s" % SRC.name, flush=True)
print("[env] key_len=%d tavily_len=%d"
      % (len(m.os.environ.get("DGTF_API_KEY") or ""),
         len(m.os.environ.get("TAVILY_API_KEY") or "")), flush=True)

# ---- 1 单次 LLM 调用（最便宜的连通性验证）----
_cfg = m.DEFAULT_CONFIG.copy()
try:
    _llm = m.LLM(_cfg)
    t0 = time.time()
    _r = _llm.call("你是测试。", "只回 JSON：{\"ok\": 1}", 0.0, 32,
                   json_mode=True)
    print("[env] LLM ok=%.1fs raw=%r" % (time.time() - t0, _r[:60]),
          flush=True)
    print("[env] 解析=%r" % (_llm.parse_json(_r),), flush=True)
except Exception as exc:  # noqa: BLE001
    print("[env] LLM 失败：%s: %s" % (type(exc).__name__, exc), flush=True)

# ---- 2 短跑：只走研究层 1 圈（量耗时与子问题数）----
d = HERE / "outputs" / "_v1233_probe"
d.mkdir(parents=True, exist_ok=True)
cfg = m.DEFAULT_CONFIG.copy()
cfg["output"] = dict(cfg.get("output") or {})
cfg["output"]["save_dir"] = str(d)
cfg["output"]["verbose"] = False
buf = io.StringIO()
t0 = time.time()
try:
    with contextlib.redirect_stdout(buf):
        meta = m.MetaDGTF(cfg)
        res = meta.run("老城区暴雨内涝频发，排水系统重建还是局部改造加海绵城市措施？",
                       route=["0"], rounds={"0": 1},
                       parallel_mode="serial", orientation="auto")
    p1 = (res.get("pools") or {}).get("1") or {}
    subs = p1.get("sub_questions") or []
    print("[env] 短跑 %.1fs calls=%s subs=%d 判定=%s"
          % (time.time() - t0, res.get("llm_calls"), len(subs),
             [s.get("decidability") for s in subs]), flush=True)
except Exception as exc:  # noqa: BLE001
    print("[env] 短跑失败 %.1fs：%s: %s"
          % (time.time() - t0, type(exc).__name__, exc), flush=True)
    print(buf.getvalue()[-1500:], flush=True)
print("ENV_PROBE_DONE", flush=True)

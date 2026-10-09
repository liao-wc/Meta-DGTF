# -*- coding: utf-8 -*-
"""v1.23.19 真联网探针：`AnchorRetriever(backend='tavily')` 这条**从未执行过**的路。

为什么要单独测：改前它够不到（早退在前面），所以 `_tavily` 的请求/解析
从来没在真网络上跑过一次。至少要证明：
  ① 真能拿到结果（条数 > 0）；
  ② 返回的 dict 字段齐备（`id` / `claim` / `url` / `tier`），能直接当锚点用；
  ③ 未知 backend 仍然抛错（不静默降级）。
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("m", str(HERE / "元DGTF-V1.23.19.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["m"] = mod
spec.loader.exec_module(mod)

KEY_ENV = (mod.DEFAULT_CONFIG.get("external_anchor") or {}).get(
    "api_key_env") or "TAVILY_API_KEY"
key = os.environ.get(KEY_ENV, "")
print("key 环境变量 %s 有值: %s" % (KEY_ENV, bool(key)))

QS = ["老城区暴雨内涝 排水系统 重建 标准",
      "城市雨水管网 设计重现期 国家标准 GB"]

# ① 未实现 backend 必须抛错（不静默降级）——先测这条（零网络）
try:
    mod.AnchorRetriever("nope_backend", key, 24).search(["x"], 3)
    print("① 未知后端：★ 竟然没抛错（静默降级）")
except RuntimeError as e:
    print("① 未知后端抛错 OK：", str(e)[:60])

# ② snapshot 后端零调用、返回空
print("② snapshot 后端 search 返回:", mod.AnchorRetriever("snapshot", key, 24).search(QS, 5))

# ③ 真联网
r = mod.AnchorRetriever("tavily", key, 24)
got = r.search(QS, 6)
print("③ tavily 返回条数:", len(got))
for a in got[:3]:
    print("   ", json.dumps(a, ensure_ascii=False)[:170])
need = ("id", "claim", "url", "tier")
ok = bool(got) and all(all(k in a for k in need) for a in got)
print("③ 字段齐备（id/claim/url/tier）:", ok)
if got:
    print("③ claim 非空:",
          all(bool(str(a.get("claim") or "").strip()) for a in got))
# 缓存：第二次同 queries 应命中缓存（不再打网络）
import time
t0 = time.time()
got2 = r.search(QS, 6)
print("③ 第二次（应命中 cache/anchors）耗时 %.2fs，条数 %d" % (time.time() - t0,
                                                            len(got2)))

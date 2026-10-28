# -*- coding: utf-8 -*-
"""auto_dispatch 本地端点降档判据（V2.2.14b）。

为什么需要这条判据
------------------
auto 调度对事实型问题判 web=on / thinking=on（对云端强模型合理），在本地
0.5B 上是灾难链（实测，shim 请求转储定位）：
  thinking=on ⇒ 整表 stages 改 enabled ⇒ 推理模型语义「不发 temperature」
  ⇒ temp 0 确定性复读 ⇒ JSON 截断；
  web=on ⇒ 工具预检把检索材料灌进 self 通道 ⇒ system 污染 ⇒ 照抄。
⇒ re_anchor 解析失败 ⇒ aspect_units 不登记 ⇒ 修行层读数「零存量」。

V2.2.14 修法：`_is_local_llm_endpoint(cfg)` 命中时，**仅对 auto 来源**的
web/thinking/effort 降档。本判据钉四件事：
  1. 本地端点 + auto 来源 ⇒ 降档（source=local-downgrade）；
  2. explicit 来源**不**被降档（人定的不许机器改）；
  3. 非本地端点 ⇒ 行为不变（回归保护）；
  4. `_apply_auto_dispatch` 认 local-downgrade（降了档没人写 = 白降）。

引擎整模块导入（纯函数直调，零 API / 零 GPU / 不需要服务在线）。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "dgtf_engine"))

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def load_engine():
    """整模块导入当前最高版引擎（与 tests_layer_goal 同款脚手架）。"""
    import importlib.util
    best, best_ver = None, (0, 0, 0)
    import re
    for f in (HERE / "engine").glob("Meta-DGTF-V*.py"):
        m = re.search(r"V(\d+)\.(\d+)\.(\d+)\.py$", f.name)
        if m:
            ver = tuple(int(x) for x in m.groups())
            if ver > best_ver:
                best, best_ver = f, ver
    name = "_eng_local_downgrade_test"
    spec = importlib.util.spec_from_file_location(name, best)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # ★ 必须先注册，dataclass 内省才不炸
    spec.loader.exec_module(mod)
    return mod, best.name


LOCAL_CFG = {
    "api": {"base_url": "http://127.0.0.1:8773/v1", "default_model": "local"},
    "auto": {"enabled": True},
}
CLOUD_CFG = {
    "api": {"base_url": "https://api.example.com/v1",
            "default_model": "deepseek-flash"},
    "auto": {"enabled": True},
}
#: 事实型短问题 ⇒ auto 会表态 web/thinking/effort（历史特征 fact=true）。
FACT_Q = "成年人正常心率是多少次每分钟"


def main() -> int:
    eng, fname = load_engine()
    ck("Z0 引擎动态发现（最高版）", bool(fname), fname)

    # ── A _is_local_llm_endpoint 纯函数 ──────────────────
    ck("A1 127.0.0.1 认本地", eng._is_local_llm_endpoint(LOCAL_CFG))
    ck("A2 云端域名不认本地", not eng._is_local_llm_endpoint(CLOUD_CFG))
    ck("A3 空/坏配置不炸且不认", not eng._is_local_llm_endpoint({}))

    # ── B 本地 + auto ⇒ 降档 ────────────────────────────
    plan = eng.auto_dispatch(FACT_Q, config=LOCAL_CFG)
    items = plan.get("_items") or {}
    ck("B1 ★ 本地端点：web 的 auto 决策被降为 False",
       plan.get("web") is False and items.get("web", {}).get("source")
       == "local-downgrade", (plan.get("web"), items.get("web")))
    ck("B2 ★ 本地端点：thinking 的 auto 决策被降为 off",
       plan.get("thinking") == "off"
       and items.get("thinking", {}).get("source") == "local-downgrade",
       (plan.get("thinking"), items.get("thinking")))
    ck("B3 降档留痕带原因（产物里可指认）",
       "本地端点" in str(items.get("web", {}).get("reason") or ""))

    # ── C explicit 不被降档（人定的不许机器改）──────────────
    # ★ explicit 走 CLI 口径（"on"/"off" 字符串）——布尔 True 会被
    #   _auto_normalize_explicit 当非法值丢掉（这是它的设计，不是 bug）。
    plan2 = eng.auto_dispatch(
        FACT_Q, config=LOCAL_CFG,
        explicit={"web": "on", "thinking": "on"})
    it2 = plan2.get("_items") or {}
    ck("C1 ★ explicit web=on 在本地端点保持 on",
       plan2.get("web") is True and it2.get("web", {}).get("source")
       == "explicit", (plan2.get("web"), it2.get("web", {}).get("source")))
    ck("C2 explicit thinking=on 在本地端点保持 on（归一化为 True）",
       plan2.get("thinking") is True
       and it2.get("thinking", {}).get("source") == "explicit",
       (plan2.get("thinking"), it2.get("thinking", {}).get("source")))

    # ── D 非本地 ⇒ 行为不变（回归保护）──────────────────
    plan3 = eng.auto_dispatch(FACT_Q, config=CLOUD_CFG)
    it3 = plan3.get("_items") or {}
    ck("D1 ★ 云端：无 local-downgrade 来源（降档不误伤）",
       all(v.get("source") != "local-downgrade" for v in it3.values()),
       {k: v.get("source") for k, v in it3.items()})

    # ── E 降档决策真被写进配置（_apply 认 local-downgrade）────
    cfg = {"api": dict(LOCAL_CFG["api"]), "auto": {"enabled": True}}
    notes = eng._apply_auto_dispatch(cfg, plan)
    ck("E1 ★ 降档后 runtime.web=off（写进配置才生效）",
       (cfg.get("runtime") or {}).get("web") == "off", cfg.get("runtime"))
    ck("E2 降档后 runtime.thinking=off",
       (cfg.get("runtime") or {}).get("thinking") == "off")

    print("引擎文件: %s" % fname)
    print("TOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())

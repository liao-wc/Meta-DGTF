# -*- coding: utf-8 -*-
"""前缀缓存优化（prompt_stable_first）判据（Round 6）。

覆盖：
  · 默认配置必须是关（零行为差）；
  · `_move_var_to_user` 纯函数：空变量不改写、变量块按序后置、内容不丢；
  · `_stable_first()` 只读 output.prompt_stable_first；
  · 引擎源码含 dual_judge / self_check 两条 opt-in 分支与 CLI 开关。
"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ENGINE = HERE / "engine" / "Meta-DGTF-V2.2.3.py"
P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n +
          (" :: " + str(info) if info and not ok else ""))


def load_mod():
    spec = importlib.util.spec_from_file_location("engine_cache_test", str(ENGINE))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["engine_cache_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    mod = load_mod()
    # ① 默认关
    out_cfg = (mod.DEFAULT_CONFIG.get("output") or {})
    ck("DEFAULT_CONFIG.output.prompt_stable_first 默认 False（零行为差）",
       out_cfg.get("prompt_stable_first") is False,
       out_cfg.get("prompt_stable_first"))

    fn = mod.DGTF._move_var_to_user
    # ② 空变量 → 原样
    s0, u0 = fn("SYS", [], "USER")
    ck("空变量块 → system/user 不变", s0 == "SYS" and u0 == "USER", (s0, u0))
    s1, u1 = fn("SYS", ["", "   "], "USER")
    ck("空白变量块 → system/user 不变", s1 == "SYS" and u1 == "USER", (s1, u1))

    # ③ 变量块后置 + 顺序保持 + 内容不丢
    sys_txt = "你是【对偶判断者】。\n静态规范……\n严格 JSON：\n{\"judgments\":[]}"
    var1 = "【上一圈约束】禁止重述 A"
    var2 = "\n【你上一次是谁】记忆 B\n"
    s2, u2 = fn(sys_txt, [var1, var2], "【候选列表】\n1. X")
    ck("system 不再包含变量块", var1 not in s2 and var2.strip() not in s2, s2[-60:])
    ck("user 末尾按序包含变量块",
       u2.rstrip().endswith(var2.strip())
       and var1 in u2 and u2.index(var1) < u2.index("记忆 B"),
       u2[-80:])
    ck("静态 system 内容原样保留（缓存前缀不被截短）",
       s2.startswith(sys_txt) or sys_txt in s2)
    ck("user 原有内容在前（候选列表仍可见）",
       u2.startswith("【候选列表】") and u2.index("1. X") < u2.index(var1))

    # ④ _stable_first 只认 output 键
    fake_on = SimpleNamespace(config={"output": {"prompt_stable_first": True}})
    fake_off = SimpleNamespace(config={"output": {}})
    fake_bad = SimpleNamespace(config=None)
    ck("_stable_first()：True 生效",
       mod.DGTF._stable_first(fake_on) is True)
    ck("_stable_first()：缺键 → False",
       mod.DGTF._stable_first(fake_off) is False)
    ck("_stable_first()：config 异常 → False（fail-open）",
       mod.DGTF._stable_first(fake_bad) is False)

    # ⑤ 源码结构：两条 opt-in 分支 + CLI
    src = ENGINE.read_text(encoding="utf-8", errors="replace")
    ck("dual_judge 分支存在", "_carry_txt" in src and "_static_sys" in src)
    ck("self_check 分支存在", "if self._stable_first():" in src)
    ck("CLI 开关存在", "--prompt-stable-first" in src)
    ck("DEFAULT_CONFIG 注释含 cache 命中说明", "cache hit" in src)

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())

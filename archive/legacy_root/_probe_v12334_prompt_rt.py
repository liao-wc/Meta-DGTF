#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：**运行期**导出提示词，人读检查（不是看源码字面）。

## 为什么必须看运行期
提示词是**拼接**出来的：
    "你处于【0 · 阴视角】。\n" + ... + EXPLORE_FORMAT + VOICE + EVIDENCE
    + ANTI_PRETTY + self._self_block()
源码里读到的是**片段**；只有调用真实方法，才看得到**模型实际收到的那一段**。
「拼错顺序 / 常量是空串 / 漏拼 / 拼接处少换行」这些错误，源码级判据看不出来
（本项目已栽过「纯函数/源码判据全绿，运行时不可达」多次）。

## 本探针查什么
  ① 六处视角 `*_prompt()` 的**实际字符串**：三常量都在、顺序对、不打架；
  ② ing 的 system：猴补丁 `_call_long` 捕获**真实 system**（不是从源码拼）；
  ③ 关键副产物：`VOICE` / `EVIDENCE` 在拼接处**前后换行正常**（不然会连成一行）。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    spec = importlib.util.spec_from_file_location("smoke_rt", HERE / "smoke_test.py")
    st = importlib.util.module_from_spec(spec)
    sys.modules["smoke_rt"] = st
    spec.loader.exec_module(st)
    mod = st.mod
    cfg = st.build_cfg(False)
    dg = mod.DGTF("0", mod.LLM(cfg), cfg)
    dg2 = mod.DGTF("both", mod.LLM(cfg), cfg)
    dg3 = mod.DGTF("all", mod.LLM(cfg), cfg)

    bad = []
    print("=" * 72)
    for _name, _obj in (("_yin_prompt", dg), ("_yang_prompt", dg),
                        ("_both_yin_prompt", dg2), ("_both_yang_prompt", dg2),
                        ("_all_yin_prompt", dg3), ("_all_yang_prompt", dg3)):
        try:
            t = getattr(_obj, _name)()
        except Exception as e:
            bad.append("%s 调用抛错：%r" % (_name, e))
            continue
        _has = [k for k, v in (("VOICE", "【怎么说话】"),
                               ("EVIDENCE", "【有据"),
                               ("EXPLORE_FORMAT", "每行格式"),
                               ("ANTI_PRETTY", "【反漂亮约束")) if v in t]
        _ord_ok = (t.find("【怎么说话】") < t.find("【有据")
                   < t.find("【反漂亮约束"))
        _nl_ok = "\n【怎么说话】" in t and "\n【有据" in t
        print("[%-16s] 长度 %4d | 常量齐 %s | 顺序对 %s | 换行对 %s"
              % (_name, len(t), _has, _ord_ok, _nl_ok))
        if len(_has) != 4 or not _ord_ok or not _nl_ok:
            bad.append("%s 的运行期文本有问题：常量 %r / 顺序 %r / 换行 %r"
                       % (_name, _has, _ord_ok, _nl_ok))

    # ── ing：猴补丁 `_call_long` 捕获**真实 system** ──
    _cap = {}

    def _spy_call_long(system, user, *a, **kw):
        _cap["system"] = system
        _cap["user"] = user
        return ("一、这是 mock 的六步正文。\n二、……\n六、回到原问题。", False)
    _orig_cl = dg2._call_long
    dg2._call_long = _spy_call_long
    try:
        dg2._ing([], object(), "锚点")          # candidates 空 ⇒ 早退，不会走调用
        # 造一条最小候选，逼它真走 prompt 构造
        class _C:
            attribute = "0"
            position = "1"
            desc = "一条最小候选"
            is_amp_candidate = False
            why_attribute = ""
            why_position = ""
        _inp = type("I", (), {})()
        _inp.is_base = False
        _inp.upstream_views = []
        _inp.carry_constraints = []
        dg2._ing([_C()], _inp, "锚点")
    except Exception as e:
        bad.append("ing 调用抛错：%r（可能是 mock 不完整，非本版缺陷）" % (e,))
    finally:
        dg2._call_long = _orig_cl
    _sy = _cap.get("system") or ""
    print("=" * 72)
    if _sy:
        _has = [v for v in ("【怎么说话】", "【有据", "六步各起一行",
                            "===ING-STRUCT===", "【反漂亮约束") if v in _sy]
        print("[ing · system   ] 长度 %4d | 命中 %r" % (len(_sy), _has))
        if len(_has) < 5:
            bad.append("ing 的 system 缺要素：%r" % (_has,))
    else:
        print("[ing · system   ] **没捕获到**（调用没走到 `_call_long`）")
        bad.append("ing 的 system 没捕获到 —— 要么没走到调用，要么接错了")

    print("\n%s" % ("[OK] 运行期提示词拼接正确"
                    if not bad else "[FAIL] " + "；".join(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())

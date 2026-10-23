#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：量化读数是否**进得了产物 md 正文**（可读段，不是附录 JSON）。

断点背景：`quant_readings` 原来只出到 packed JSON（附录里得翻），
正文与日志都没有 ⇒ 「算了但看不见」。

本探针用猴补丁包 `DGTF._render`，**捕获每层正文**，断言里面出现
`【各环节量化】` 段且含 `candidate_yield` 的中文标签「候选产出率」。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    spec = importlib.util.spec_from_file_location("smoke_md", HERE / "smoke_test.py")
    st = importlib.util.module_from_spec(spec)
    sys.modules["smoke_md"] = st
    spec.loader.exec_module(st)
    mod = st.mod

    _orig = mod.DGTF._render
    _cap = []

    def _spy(self, view, inp):
        txt = _orig(self, view, inp)
        _cap.append(txt)
        return txt
    mod.DGTF._render = _spy

    cfg = st.build_cfg(False)
    mod.MetaDGTF(cfg).run("意识能否被还原为信息处理过程？",
                          route=["0"], rounds={"0": 3}, parallel_mode="serial")
    mod.DGTF._render = _orig

    body = "\n".join(_cap)
    print("=== _render 捕获 %d 层正文 ===" % len(_cap))
    _i = body.find("【各环节量化】")
    if _i >= 0:
        print("找到段落，摘录：")
        print(body[_i:_i + 400])
    print()

    ok = True
    if "【各环节量化】" not in body:
        print("[X] 正文里没有【各环节量化】段")
        ok = False
    if "候选产出率" not in body:
        print("[X] 正文里没有「候选产出率」标签（键→标签映射没生效）")
        ok = False
    if "锚点保真度" not in body:
        print("[X] 正文里没有「锚点保真度」（应为该层总会出现）")
        ok = False
    print("%s" % ("[OK] 量化读数已进产物正文" if ok else "[FAIL] 仍不可读"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

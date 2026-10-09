# -*- coding: utf-8 -*-
"""v1.23.10 渲染层四项 before/after 对表探针。

四项：R1 形态声明 / R8 附录外置 / R9 成本建议 / R10 事实题未校验留痕。

★ 驱动数据 = **v1.23.9 真跑产物的 packed 原文**（`_packed_v1239.json`，246KB），
  直接喂 `save_result` 重渲染 ⇒ **零 LLM 调用**，且是真实数据形态。
用法：python _probe_v12310_render.py <目标文件.py>
"""
import copy
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKED = HERE / "_packed_v1239.json"


def _load(path):
    spec = importlib.util.spec_from_file_location("dgtf_v1210probe", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dgtf_v1210probe"] = m
    spec.loader.exec_module(m)
    return m


def main():
    m = _load(sys.argv[1])
    packed = json.loads(PACKED.read_text(encoding="utf-8"))
    res = {}
    with tempfile.TemporaryDirectory() as td:
        out = m.save_result(copy.deepcopy(packed), td)
        md = Path(out)
        t = md.read_text(encoding="utf-8")
        tb = len(t.encode("utf-8"))
        res["产物行数"] = t.count("\n") + 1
        res["产物字节"] = tb

        i = t.find("## 附录 · 全量字段")
        res["附录存在"] = i >= 0
        res["附录字节"] = (tb - len(t[:i].encode("utf-8"))) if i >= 0 else 0
        res["附录占比"] = ("%.0f%%" % ((tb - len(t[:i].encode("utf-8"))) / tb * 100)
                        if i >= 0 else "n/a")
        res["正文含json块"] = "```json" in t
        _side = sorted(p.name for p in Path(td).glob("*.json"))
        res["旁挂文件"] = _side
        res["旁挂字节"] = sum(p.stat().st_size for p in Path(td).glob("*.json"))

        res["R1_形态声明"] = ("**形态声明**" in t)
        res["R9_有函数"] = hasattr(m, "_auto_profile")
        if res["R9_有函数"]:
            for _q in ("新中国的成立时间是什么时候", "老城区内涝该不该重建",
                       "这份方案怎么落地"):
                res["R9|" + _q[:10]] = m._auto_profile(_q)
        res["R10_未校验留痕"] = ("未接入外部校验" in t)
        res["R10_开关提示"] = ("--web on" in t)

        # 落盘函数若有 mode 参数，单独量一次 slim
        try:
            import inspect as _ins
            _sig = _ins.signature(m._render_full_appendix)
            res["_render_full_appendix 签名"] = str(_sig)
        except Exception as e:  # noqa: BLE001
            res["_render_full_appendix 签名"] = f"（取不到：{e}）"

    for k in res:
        print(f"{k} = {res[k]}")


main()

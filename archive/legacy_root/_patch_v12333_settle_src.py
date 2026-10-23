# -*- coding: utf-8 -*-
"""补丁：研究层读数改读**真实字段** `settlement`（原读臆造的 `covered_answer`）。

★ 真跑逮到（GOALCHK 产物）：层 1 的 view **没有** `covered_answer` 键
  ⇒ `v.get("covered_answer")` 恒 None ⇒ `settle` 恒 `null`
  （纯函数判据全绿，因为夹具自己塞了 `covered_answer` —— 经典「判据用了
   实现里不存在的字段」）。真实原料 = `settlement.answered/total`
  （`coverage` 与它同源：`coverage_of` 用的就是这两个数）。

兼容：`settlement` 优先，缺失时退回旧键（老产物 / 夹具）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

OLD = '''            _co = v.get("covered_answer") or {}
            _ans, _tot = _co.get("answered"), _co.get("total")
            d["settle"] = _lg_ratio(_ans, _tot)'''

NEW = '''            # ★ 真实原料 = `settlement`（`answered`/`total`，与 `coverage_of`
            #   同源）。原读 `covered_answer` 是**臆造键** —— 真跑层 1 的 view
            #   里根本没有它 ⇒ `settle` 恒 null（判据全绿是因为夹具自带该键）。
            _co = v.get("settlement") or v.get("covered_answer") or {}
            _ans, _tot = _co.get("answered"), _co.get("total")
            if _ans is None:
                # 再兜一层：由 covered/uncovered 层面数推（同源口径）。
                _ca = v.get("covered_aspects") or []
                _ua = v.get("uncovered_aspects") or []
                if _ca or _ua:
                    _ans, _tot = len(_ca), len(_ca) + len(_ua)
            d["settle"] = _lg_ratio(_ans, _tot)'''


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 主文件非纯 CRLF，拒绝改"); sys.exit(1)
    lf = txt.replace("\r\n", "\n")
    n = lf.count(OLD)
    if n != 1:
        print("X 锚点命中 %d 次（应为 1）" % n); sys.exit(1)
    out = lf.replace(OLD, NEW, 1)
    out_b = out.replace("\n", "\r\n").encode("utf-8")
    if out_b.decode("utf-8").count("\r\r\n"):
        print("X 产物含 r-r-n"); sys.exit(1)
    SRC.write_bytes(out_b)
    print("OK 已改：settle 读 settlement（真实字段）；锚点命中 1 次")


if __name__ == "__main__":
    main()

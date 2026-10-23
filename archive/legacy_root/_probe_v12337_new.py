#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探针：验证**副本 V1.23.37** 的两项新能力（零 API 花费）。

## 为什么单独写探针
`smoke_test.py` 的 `SRC` 仍指向**验证版 V1.23.36**（正在跑验收链），
**不能改** ⇒ 副本的新能力先用**独立探针**验，等链跑完再把判据正式接进冒烟。

## 验两件
① **联网按需协议** `parse_web_need`：
   · 不声明 ⇒ `[]`（**零行为差**）；
   · 标准声明 ⇒ 解出查询；
   · 超量声明 ⇒ 被 `limit` 截（防一次吃光配额）；
   · 畸形输入 ⇒ **不抛错**、返回 `[]`；
② **圈级心跳**：连跑两圈 ⇒ 必须出现 `@rN` 标记的圈级调用
   （证「上一圈读数 → 本圈决策」这条链真的走通）。
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    spec = importlib.util.spec_from_file_location("smoke_rt37", HERE / "smoke_test.py")
    st = importlib.util.module_from_spec(spec)
    sys.modules["smoke_rt37"] = st
    spec.loader.exec_module(st)
    # ★ 把被测模块**换成副本 V1.23.37**（smoke 的 mod 是 V1.23.36）
    _sp2 = importlib.util.spec_from_file_location("m37", HERE / "元DGTF-V1.23.37.py")
    mod = importlib.util.module_from_spec(_sp2)
    sys.modules["m37"] = mod
    _sp2.loader.exec_module(mod)

    bad = []
    print("=== ① 联网按需协议 parse_web_need ===")
    _M = getattr(mod, "_WEB_NEED_MARK", None)
    _fn = getattr(mod, "parse_web_need", None)
    if not _M or not _fn:
        bad.append("[按需] 缺 `_WEB_NEED_MARK` 或 `parse_web_need`")
    else:
        _cases = [
            ("不声明", "普通产出，没有声明", []),
            ("标准 JSON", "正文\n" + _M + '\n{"queries": ["甲","乙"]}', ["甲", "乙"]),
            ("超量", "正文\n" + _M + '\n{"queries": ["1","2","3","4","5"]}', None),
            ("单行", "正文\n" + _M + "\n丙", ["丙"]),
        ]
        for _nm, _in, _want in _cases:
            try:
                _got = _fn(_in)
            except Exception as _e:
                bad.append("[按需] %s **抛错**：%r" % (_nm, _e))
                print("   ✗ %-8s 抛错 %r" % (_nm, _e))
                continue
            _ok = (len(_got) <= 3) if _want is None else (_got == _want)
            print("   %s %-8s → %r" % ("✓" if _ok else "✗", _nm, _got))
            if not _ok:
                bad.append("[按需] %s 解析不对：%r（期望 %r）" % (_nm, _got, _want))
        # 畸形不许抛
        for _bad_in in ("", _M, _M + "\n{坏json", _M + "\n[]", _M + "\n{'q': 1}"):
            try:
                _fn(_bad_in)
            except Exception as _e:
                bad.append("[按需] 畸形输入抛错 %r：%r" % (_bad_in[:20], _e))
        print("   ✓ 畸形输入 5 例均不抛错")

    print("\n=== ② 圈级心跳（连跑两圈）===")
    try:
        _seen = []
        _orig = mod.MetaDGTF._schedule_tick

        def _spy(self, entry, view):
            _seen.append(str(entry))
            return _orig(self, entry, view)
        mod.MetaDGTF._schedule_tick = _spy
        try:
            mod.MetaDGTF(st.build_cfg(False)).run(
                "圈级心跳探针题", route=["0"], rounds={"0": 2},
                parallel_mode="serial", run_id="")
        finally:
            mod.MetaDGTF._schedule_tick = _orig
        _r = [x for x in _seen if "@r" in x]
        print("   全部调用：%r" % (_seen[:8],))
        print("   圈级调用：%r" % (_r[:6],))
        if not _r:
            bad.append("[圈级] 跑了两圈**没有圈级调用**（@rN 未出现）")
        elif len(_r) < 1:
            bad.append("[圈级] 圈级调用少于 1 次")
        else:
            print("   ✓ 第 %s 圈起出现圈级心跳" % (_r[0],))
    except Exception as _e:
        bad.append("[圈级] 构造性验证抛错：%r" % (_e,))

    print()
    if bad:
        for x in bad:
            print("  ✗", x)
        print("\n[FAIL] %d 项" % len(bad))
        return 1
    print("[OK] 副本 V1.23.37 两项新能力均可用（按需协议 + 圈级心跳）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

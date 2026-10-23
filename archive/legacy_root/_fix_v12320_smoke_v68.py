# -*- coding: utf-8 -*-
"""v1.23.20 连带修：check_v68_round_dump 专测「留痕全量」，需显式打开新开关。

它原本只把 `dg.verbose = True` 当闸；本版留痕另受 `dump_rounds` 控制且默认关，
故要补一行 `dg.dump_rounds = True`，否则会把「开关默认关」误判成「留痕坏了」。
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "smoke_test.py"

OLD_A = '    dg.verbose = True\n'
NEW_A = ('    dg.verbose = True\n'
         '    dg.dump_rounds = True  # 留痕另有独立开关（默认关）；这些检查测的是「开着时」的行为\n')
OLD_B = '    _dg.verbose = True\n'
NEW_B = ('    _dg.verbose = True\n'
         '    _dg.dump_rounds = True\n')


def main() -> None:
    s = ST.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "smoke_test 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "dg.dump_rounds = True" in s:
        print("已修，跳过（幂等）")
        return
    na, nb = s.count(OLD_A), s.count(OLD_B)
    assert na >= 4 and nb >= 1, f"命中不足：dg={na} _dg={nb}"
    s = s.replace(OLD_A, NEW_A).replace(OLD_B, NEW_B)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    ST.write_bytes(out.encode("utf-8"))
    print("v68 check 已修（补 dg.dump_rounds = True）")


if __name__ == "__main__":
    main()

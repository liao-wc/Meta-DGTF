# -*- coding: utf-8 -*-
"""v1.23.20 连带：CONFIG_TUNED 登记表销账。

`output.show_ing` / `output.show_manifest` 本版改回默认（false），
yaml 与 DEFAULT_CONFIG 不再有差异 ⇒ 这两条必须从「已销账手调项」表里删掉，
否则 `check_config_parses` 会判「登记表过期（yaml 已改回默认却没销账）」。
`output.show_probe_diag` 未改、仍是手调项，保留。
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "smoke_test.py"

OLD = ('    "output.show_ing": "调试期要看 ing / manifest / 探针诊断",\n'
       '    "output.show_manifest": "调试期要看 ing / manifest / 探针诊断",\n'
       '    "output.show_probe_diag": "调试期要看 ing / manifest / 探针诊断",\n')
NEW = '    "output.show_probe_diag": "调试期要看 ing / manifest / 探针诊断",\n'


def main() -> None:
    s = ST.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "smoke_test 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if '"output.show_ing":' not in s:
        print("已销账，跳过（幂等）")
        return
    n = s.count(OLD)
    assert n == 1, f"锚点命中 {n} 次（期望 1）"
    s = s.replace(OLD, NEW)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    ST.write_bytes(out.encode("utf-8"))
    print("CONFIG_TUNED 已销账（删 show_ing / show_manifest 两行）")


if __name__ == "__main__":
    main()

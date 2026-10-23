# -*- coding: utf-8 -*-
"""修 check_v12322：临时文件用「清空」而非 unlink（本机沙箱会拦删除，抛 OSError）。"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "smoke_test.py"

OLD = ('    _tmp = _tmpdir / "hits.jsonl"\n'
       '    if _tmp.exists():\n'
       '        _tmp.unlink()\n')
NEW = ('    _tmp = _tmpdir / "hits.jsonl"\n'
       '    if _tmp.exists():\n'
       '        _tmp.write_text("", encoding="utf-8")  # 清空：本机沙箱会拦 unlink\n')


def main() -> None:
    s = ST.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "smoke_test 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "清空：本机沙箱会拦 unlink" in s:
        print("已修，跳过（幂等）")
        return
    n = s.count(OLD)
    assert n == 1, f"锚点命中 {n} 次（期望 1）"
    s = s.replace(OLD, NEW)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    ST.write_bytes(out.encode("utf-8"))
    print("check_v12322 改为清空临时文件")


if __name__ == "__main__":
    main()

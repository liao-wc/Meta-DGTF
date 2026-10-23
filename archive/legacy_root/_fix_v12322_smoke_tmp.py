# -*- coding: utf-8 -*-
"""修 check_v12322 的临时路径：系统 TEMP 下落盘会被拦（静默失败），改用项目内目录。

顺带补上「文件可能不存在」的读取（0 条命中时**不建文件**是预期行为）。
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "smoke_test.py"

OLD_A = '    _tmp = Path(tempfile.mkdtemp()) / "hits.jsonl"\n'
NEW_A = ('    _tmpdir = Path("_audit_tmp") / "webhits_test"\n'
         '    _tmpdir.mkdir(parents=True, exist_ok=True)\n'
         '    _tmp = _tmpdir / "hits.jsonl"\n'
         '    if _tmp.exists():\n'
         '        _tmp.unlink()\n')

OLD_B = '        _n2 = _tmp.read_text(encoding="utf-8").count("\\n")\n'
NEW_B = ('        _n2 = (_tmp.read_text(encoding="utf-8").count("\\n")\n'
         '               if _tmp.exists() else 0)\n')


def main() -> None:
    s = ST.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "smoke_test 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if 'Path("_audit_tmp") / "webhits_test"' in s:
        print("已修，跳过（幂等）")
        return
    for old, new, tag in ((OLD_A, NEW_A, "A 临时路径"), (OLD_B, NEW_B, "B 读取容错")):
        n = s.count(old)
        assert n == 1, f"[{tag}] 锚点命中 {n} 次（期望 1）"
        s = s.replace(old, new)
    # tempfile 已不再使用；留着 import 无害，但顺手清掉未用变量风险，不动。
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    ST.write_bytes(out.encode("utf-8"))
    print("check_v12322 临时路径已修为项目内 _audit_tmp/")


if __name__ == "__main__":
    main()

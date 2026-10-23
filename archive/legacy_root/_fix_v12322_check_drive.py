# -*- coding: utf-8 -*-
"""修 check_v12322 的行为断言：别打桩 `_http`（落盘就写在它里面），直接驱动落盘器。"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "smoke_test.py"

OLD = '''    _old = mod._WEB_HITS_PATH
    mod._WEB_HITS_PATH = str(_tmp)
    try:
        _c = mod.WebSearchClient("tavily", "k")
        _c._http = lambda q, n: ([{"claim": "命中内容示例",
                                   "url": "https://example.com/x",
                                   "kind": "web", "tier": 3}], "")
        _c.search("测试查询", 3)
        _n1 = _tmp.read_text(encoding="utf-8").count("\\n") if _tmp.exists() else 0
        if _n1 != 1:
            bad.append("命中落盘行数 = %d（应 1）" % _n1)
        else:
            _rec = _json.loads(_tmp.read_text(encoding="utf-8").splitlines()[0])
            if "example.com" not in str(_rec.get("url", "")):
                bad.append("落盘条目缺 url")
            if not _rec.get("query"):
                bad.append("落盘条目缺 query（没法按检索聚合）")

        _c2 = mod.WebSearchClient("tavily", "k")
        _c2._http = lambda q, n: ([], "empty")
        _c2.search("空结果", 3)
        _n2 = (_tmp.read_text(encoding="utf-8").count("\\n")
               if _tmp.exists() else 0)
        if _n2 != 1:
            bad.append("0 条命中竟然也写了（行数 %d）" % _n2)
    finally:
        mod._WEB_HITS_PATH = _old
'''

NEW = '''    _old = mod._WEB_HITS_PATH
    mod._WEB_HITS_PATH = str(_tmp)
    try:
        # ★ 直接驱动落盘器：`_http` 是「可打桩的缝」，而落盘**就写在它里面** ——
        #   打桩 _http 会把落盘一起覆盖掉（第一版就这么写错了，落盘 0 行）。
        mod._record_web_hits("测试查询", [{"claim": "命中内容示例",
                                          "url": "https://example.com/x",
                                          "kind": "web", "tier": 3}])
        _n1 = _tmp.read_text(encoding="utf-8").count("\\n") if _tmp.exists() else 0
        if _n1 != 1:
            bad.append("落盘行数 = %d（应 1）" % _n1)
        else:
            _rec = _json.loads(_tmp.read_text(encoding="utf-8").splitlines()[0])
            if "example.com" not in str(_rec.get("url", "")):
                bad.append("落盘条目缺 url")
            if not _rec.get("query"):
                bad.append("落盘条目缺 query（没法按检索聚合）")
        # 负对照：0 条不写（文件有没有都算过 —— 不该多行）
        mod._record_web_hits("空结果", [])
        _n2 = _tmp.read_text(encoding="utf-8").count("\\n") if _tmp.exists() else 1
        if _n2 != 1:
            bad.append("0 条也写了（行数 %d）" % _n2)
    finally:
        mod._WEB_HITS_PATH = _old
'''


def main() -> None:
    s = ST.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "smoke_test 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "落盘**就写在它里面**" in s:
        print("已修，跳过（幂等）")
        return
    n = s.count(OLD)
    assert n == 1, f"锚点命中 {n} 次（期望 1）"
    s = s.replace(OLD, NEW)
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    ST.write_bytes(out.encode("utf-8"))
    print("check_v12322 改为直接驱动落盘器")


if __name__ == "__main__":
    main()

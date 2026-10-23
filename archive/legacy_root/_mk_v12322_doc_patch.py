# -*- coding: utf-8 -*-
"""v1.23.22 的文档与测试同步（保纯 CRLF、幂等）。

- yaml 头部 → v1.23.22；CHANGELOG 加段；smoke_test：SRC + `check_v12322_web_hits_dump`
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
CHG = HERE / "CHANGELOG.md"
ST = HERE / "smoke_test.py"

NEW_SEG = """v1.23.22 相对 v1.23.21

【要解决的问题】工作台的「联网检索库」要装**条目内容和链接**，但两条检索通道
  （`AnchorRetriever._tavily` / `WebSearchClient._http`）返回的条目虽然**本来就带
  `claim` + `url`**，却只在**失败**时留痕（成功时什么也不落）—— 应用层拿不到
  「检索到了什么、来自哪」。

【改了哪几处】
  1. 新增模块级 `_record_web_hits(query, items)`：把命中**追加**到
     `outputs/_web_hits.jsonl`（`ts` / `query` / `claim` / `url` / `tier` / `kind`）。
     路径可用环境变量 `DGTF_OUTPUT_DIR` 覆盖；任何写失败都**静默**（不拖累检索）。
  2. `AnchorRetriever._tavily` 与 `WebSearchClient._http` 的成功返回前各调一次。

【影响面】纯**新增落盘**：检索行为、产物 md / packed.json 都不变；
  0 条命中时不写文件（不留空行噪声）。"""

NEW_CHECK = '''def check_v12322_web_hits_dump():
    """[v1.23.22] 联网命中必须落盘（JSONL：内容 + 链接）。

    ① `_record_web_hits` 恰好定义 1 次；
    ② 两条检索通道的成功返回前都调它；
    ③ 行为：打桩 `_http` 返回一条命中 → `search()` → JSONL 多一行且含 url；
    ④ 负对照：0 条命中**不写**（不留空行噪声）。
    """
    import json as _json
    import tempfile
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    if src.count("def _record_web_hits(") != 1:
        bad.append("_record_web_hits 定义不是 1 处")
    for _m in ("def _tavily(", "def _http("):
        _i = src.find(_m)
        if _i < 0 or "_record_web_hits(" not in src[_i:_i + 4000]:
            bad.append("%s 之后没调 _record_web_hits" % _m)

    _tmp = Path(tempfile.mkdtemp()) / "hits.jsonl"
    _old = mod._WEB_HITS_PATH
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
        _n2 = _tmp.read_text(encoding="utf-8").count("\\n")
        if _n2 != 1:
            bad.append("0 条命中竟然也写了（行数 %d）" % _n2)
    finally:
        mod._WEB_HITS_PATH = _old

    if bad:
        for _x in bad:
            print("  \\u2717 [v12322] %s" % _x)
        return False
    print("  \\u2713 [v12322] 联网命中落盘 JSONL（内容 + 链接 + query）；0 条不写")
    return True


'''


def patch_yaml() -> None:
    s = YAML.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "yaml 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "# 元 DGTF · v1.23.22 配置文件" in s:
        print("yaml 已改，跳过（幂等）")
        return
    old = "# 元 DGTF · v1.23.21 配置文件"
    n = s.count(old)
    assert n == 1, f"[yaml] 头部锚点命中 {n} 次"
    s = s.replace(old, "# 元 DGTF · v1.23.22 配置文件")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    YAML.write_bytes(out.encode("utf-8"))
    print("yaml OK")


def patch_changelog() -> None:
    s = CHG.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "CHANGELOG 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "v1.23.22 相对 v1.23.21" in s:
        print("CHANGELOG 已改，跳过（幂等）")
        return
    anchor = "---\n\nv1.23.21 相对 v1.23.20"
    n = s.count(anchor)
    assert n == 1, f"[CHANGELOG] 锚点命中 {n} 次"
    s = s.replace(anchor, "---\n\n" + NEW_SEG + "\n\nv1.23.21 相对 v1.23.20")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    CHG.write_bytes(out.encode("utf-8"))
    print("CHANGELOG OK")


def patch_smoke() -> None:
    s = ST.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "smoke_test 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "check_v12322_web_hits_dump" in s:
        print("smoke_test 已改，跳过（幂等）")
        return

    def sub(old: str, new: str, tag: str) -> str:
        n = s.count(old)
        assert n == 1, f"[smoke {tag}] 锚点命中 {n} 次"
        return s.replace(old, new)

    s = sub('SRC = HERE / "元DGTF-V1.23.21.py"', 'SRC = HERE / "元DGTF-V1.23.22.py"', "SRC")
    s = sub("\n\ndef check_p23_units():\n",
            "\n\n" + NEW_CHECK + "def check_p23_units():\n", "插入 check")
    s = sub("    if not check_v12321_tok_line():\n        return 1\n",
            "    if not check_v12321_tok_line():\n        return 1\n"
            "    if not check_v12322_web_hits_dump():\n        return 1\n", "main 接线")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    ST.write_bytes(out.encode("utf-8"))
    print("smoke_test OK")


if __name__ == "__main__":
    patch_yaml()
    patch_changelog()
    patch_smoke()

# -*- coding: utf-8 -*-
"""生成 元DGTF-V1.23.22.py：联网检索命中落盘（供工作台「联网检索库」）。

为什么：两条检索通道（`AnchorRetriever._tavily` / `WebSearchClient._http`）返回的条目
**本来就带 `claim` + `url`**，但成功时**不外露**（只有失败才走 `logger_web.warning`），
于是应用层拿不到「检索到了什么、来自哪」。本版在成功返回前把条目**追加**到
`outputs/_web_hits.jsonl`（内容 + 链接 + tier + query）。

改动 4 处（每处断言命中 == 1）：
  A. docstring 标题  v1.23.21 → v1.23.22
  B. __version__     1.23.21 → 1.23.22
  C. `logger_web` 之后加 `_WEB_HITS_PATH` + `_record_web_hits()`
  D. 两处检索成功返回前各调一次 `_record_web_hits(...)`（D1 AnchorRetriever / D2 WebSearchClient）
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.22.py"

RECORDER = '''

# ── 联网检索命中落盘（给工作台的「联网检索库」）─────────────────
#   条目本来就有 claim + url，此前只在**失败**时留痕；成功时顺手落一份，
#   应用层读 JSONL 就能展示「检索到了什么、来自哪」。
_WEB_HITS_PATH = os.path.join(
    os.environ.get("DGTF_OUTPUT_DIR", "outputs"), "_web_hits.jsonl")


def _record_web_hits(query, items) -> None:
    """把一次检索命中的条目**追加**到 JSONL。任何失败都静默（不能拖累检索）。"""
    items = list(items or [])
    if not items:
        return
    try:
        _d = os.path.dirname(_WEB_HITS_PATH)
        if _d:
            os.makedirs(_d, exist_ok=True)
        with open(_WEB_HITS_PATH, "a", encoding="utf-8", newline="") as f:
            for it in items:
                if not isinstance(it, dict):
                    continue
                f.write(json.dumps({
                    "ts": time.time(),
                    "query": str(query or "")[:200],
                    "claim": str(it.get("claim", ""))[:400],
                    "url": str(it.get("url", "") or it.get("source", ""))[:400],
                    "tier": it.get("tier"),
                    "kind": str(it.get("kind", "")),
                }, ensure_ascii=False) + "\\n")
    except OSError:
        pass

'''


def main() -> None:
    b = SRC.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "源文件不是纯 CRLF"
    assert "\r\r\n" not in s, "源文件有 CRCRLF"
    s = s.replace("\r\n", "\n")

    if '元 DGTF · v1.23.22' in s and '__version__ = "1.23.22"' in s:
        print("已是 v1.23.22，跳过（幂等）")
        return

    def sub(old: str, new: str, tag: str) -> str:
        n = s.count(old)
        assert n == 1, f"[{tag}] 锚点命中 {n} 次（期望 1）"
        return s.replace(old, new)

    s = sub("元 DGTF · v1.23.21", "元 DGTF · v1.23.22", "A 标题")
    s = sub('__version__ = "1.23.21"', '__version__ = "1.23.22"', "B __version__")

    # C：logger_web 三行之后插落盘器
    s = sub(
        'logger_web = logging.getLogger("dgtf.websearch")\n'
        'logger_web.setLevel(logging.INFO)\n'
        'logger_web.propagate = False\n',
        'logger_web = logging.getLogger("dgtf.websearch")\n'
        'logger_web.setLevel(logging.INFO)\n'
        'logger_web.propagate = False\n'
        + RECORDER,
        "C 落盘器",
    )

    # D1：AnchorRetriever._tavily 返回前落盘
    s = sub(
        '                if len(out) >= max_n:\n'
        '                    return out\n'
        '        return out\n',
        '                if len(out) >= max_n:\n'
        '                    _record_web_hits(" | ".join(list(queries or [])[:2]), out)\n'
        '                    return out\n'
        '        _record_web_hits(" | ".join(list(queries or [])[:2]), out)\n'
        '        return out\n',
        "D1 AnchorRetriever",
    )

    # D2：WebSearchClient._http 返回前落盘
    s = sub(
        '                        "kind": "web", "tier": 3})\n'
        '        return out, ("" if out else "empty")\n',
        '                        "kind": "web", "tier": 3})\n'
        '        _record_web_hits(query, out)\n'
        '        return out, ("" if out else "empty")\n',
        "D2 WebSearchClient",
    )

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n"), "转回 CRLF 后不一致"
    assert out.count("\r") == out.count("\r\n"), "存在裸 CR"
    SRC.write_bytes(out.encode("utf-8"))
    print("OK：4 处替换完成，共", len(out.encode("utf-8")), "字节")


if __name__ == "__main__":
    main()

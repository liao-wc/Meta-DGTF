# -*- coding: utf-8 -*-
"""生成 元DGTF-V1.23.21.py：LLM 每次调用后输出一行 token 累计。

为什么：工作台要「运行时实时显示消耗 token」，而引擎此前只在**结束**时打
`完成 | N 次 LLM | M tokens`（`:18081`）—— 运行中拿不到数。
本版在 LLM 调用点（`total_calls` 累加处）补一行 `logger.info("[tok] calls=N tokens=M")`。

★ 为什么走 logging 不走 `vp`：`vp` 受 `output.verbose` 控制，而这是**运行状态**
  不是调试细节 —— 关 verbose（v1.23.20 的默认姿态）也必须能看到。

改动 3 处（每处断言命中 == 1）：
  A. docstring 标题  v1.23.20 → v1.23.21
  B. __version__     1.23.20 → 1.23.21
  C. LLM 调用点加 [tok] 行
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.21.py"


def main() -> None:
    b = SRC.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "源文件不是纯 CRLF"
    assert "\r\r\n" not in s, "源文件有 CRCRLF"
    s = s.replace("\r\n", "\n")

    if '元 DGTF · v1.23.21' in s and '__version__ = "1.23.21"' in s:
        print("已是 v1.23.21，跳过（幂等）")
        return

    def sub(old: str, new: str, tag: str) -> str:
        n = s.count(old)
        assert n == 1, f"[{tag}] 锚点命中 {n} 次（期望 1）"
        return s.replace(old, new)

    s = sub("元 DGTF · v1.23.20", "元 DGTF · v1.23.21", "A 标题")
    s = sub('__version__ = "1.23.20"', '__version__ = "1.23.21"', "B __version__")

    s = sub(
        "                with self._lock:\n"
        "                    self.total_calls += 1\n",
        "                with self._lock:\n"
        "                    self.total_calls += 1\n"
        "                    _tok_calls, _tok_total = (\n"
        "                        self.total_calls, self.total_tokens)\n"
        "                # 供调用方（工作台等）**实时**读数：每次调用后打一行累计。\n"
        "                #   走 logging 不走 vp —— vp 受 output.verbose 控制，\n"
        "                #   而这是「运行状态」不是「调试细节」，关 verbose 也要看得到。\n"
        "                logger.info(\"[tok] calls=%d tokens=%d\",\n"
        "                            _tok_calls, _tok_total)\n",
        "C LLM 调用点",
    )

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n"), "转回 CRLF 后不一致"
    assert out.count("\r") == out.count("\r\n"), "存在裸 CR"
    SRC.write_bytes(out.encode("utf-8"))
    print("OK：3 处替换完成，共", len(out.encode("utf-8")), "字节")


if __name__ == "__main__":
    main()

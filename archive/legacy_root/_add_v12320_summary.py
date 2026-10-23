# -*- coding: utf-8 -*-
"""给 CHANGELOG.md 的 v1.23.20 段尾补「★ 收束摘要」（保纯 CRLF、幂等）。"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
CHG = HERE / "CHANGELOG.md"

ADD = """
★ v1.23.20 收束摘要

- **交付物**：`元DGTF-V1.23.20.py`（18321 行 / 纯 CRLF）
- **改了哪几处（6）**：docstring 标题 · `__version__` · `DGTF.__init__` 新增
  `self.dump_rounds` · `dump_round` 守卫 · `dump_final` 守卫 ·
  `DEFAULT_CONFIG.output` 新增 `"dump_rounds": False`
- **配置同步**：`dgtf_config.yaml` 的 `show_ing` / `show_manifest` 回 `false`、
  新增 `dump_rounds: false`、头部版本 → v1.23.20
- **验收数字**：冒烟 exit 0 / 0 ✗ / **PASS 213**；离线 E2E 全绿；
  真跑 route 0（126s / 11 calls / 30445 tokens / 无异常）——
  `圈全量留痕` **0** 次、`收尾留痕` **0** 次、`【ing 全文】`/`【view 全文】` **0** 次，
  而 `━━━` 进度 **62** 次
- **未做**：无遗留
"""


def main() -> None:
    s = CHG.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "CHANGELOG 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "★ v1.23.20 收束摘要" in s:
        print("已有收束摘要，跳过（幂等）")
        return
    anchor = "\n\nv1.23.19 相对 v1.23.18"
    n = s.count(anchor)
    assert n == 1, f"锚点命中 {n} 次（期望 1）"
    s = s.replace(anchor, ADD + "\nv1.23.19 相对 v1.23.18")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    CHG.write_bytes(out.encode("utf-8"))
    print("CHANGELOG 收束摘要已补")


if __name__ == "__main__":
    main()

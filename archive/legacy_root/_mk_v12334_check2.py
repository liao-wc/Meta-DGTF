# -*- coding: utf-8 -*-
"""把「**运行期**提示词拼接」检查加进 `check_v12334_prompt`。

★ 依据：本项目那条铁律 ——「纯函数/源码判据全绿 ≠ 能力在引擎里可达」。
  提示词是**拼接**出来的（`+ VOICE + EVIDENCE + …`），源码里读到的是片段；
  「拼错顺序 / 常量是空串 / 漏拼 / 拼接处少换行」这些错误源码判据看不出来。
  ⇒ 必须**调真实方法**，看模型实际收到的那一段。
★ 成本：实例化一个 `DGTF` + 调 `_yin_prompt()` —— **零 LLM 调用**，很快。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "smoke_test.py"

ANCHOR = '''    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.34 提示词优化（VOICE/EVIDENCE/EXPLORE_FORMAT 三常量接线 · "'''

NEW = '''    # ── ⑦ 运行期拼接（**真实入口**：调真实方法，看模型实际收到的那一段）──
    #   ★ 为什么不能只看源码：常量是**拼接**上去的，源码里读到的是片段；
    #     「拼错顺序 / 常量是空串 / 漏拼 / 拼接处少换行」源码判据都看不出来。
    #   ★ 零 LLM 调用（只实例化 + 拼字符串），不会拖慢冒烟。
    try:
        _cfg_rt = build_cfg(False)
        _dg_rt = mod.DGTF("0", mod.LLM(_cfg_rt), _cfg_rt)
        _t_rt = _dg_rt._yin_prompt()
        for _need in ("【怎么说话】", "【有据", "每行格式", "【反漂亮约束"):
            if _need not in _t_rt:
                bad.append("[提示词] 运行期 `_yin_prompt()` 缺 %r（拼接坏了）"
                           % _need)
        if not (_t_rt.find("【怎么说话】") < _t_rt.find("【有据")
                < _t_rt.find("【反漂亮约束")):
            bad.append("[提示词] 运行期三常量**顺序错**（应先语气、再有据、"
                       "最后反漂亮）")
    except Exception as _e_rt:
        bad.append("[提示词] 运行期导出提示词抛错：%r" % (_e_rt,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.34 提示词优化（VOICE/EVIDENCE/EXPLORE_FORMAT 三常量接线 · "'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "smoke_test.py 应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    assert s.count(ANCHOR) == 1, "锚点命中 %d 次" % s.count(ANCHOR)
    s = s.replace(ANCHOR, NEW, 1)
    s = s.replace("mock 分流字样保留）全过",
                  "mock 分流字样保留 · 运行期拼接正确）全过", 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 运行期断言已加；smoke_test.py 行数 %d" % out.count(b"\n"))


main()

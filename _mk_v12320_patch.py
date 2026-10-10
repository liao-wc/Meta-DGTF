# -*- coding: utf-8 -*-
"""生成 元DGTF-V1.23.20.py：给「全量留痕」加独立开关 + 版本号。

为什么：留痕（dump_round / dump_final）与进度共用 `self.verbose` 一个闸，
关 verbose 会连每圈进度一起关掉，于是「要进度」就只能忍受满屏留痕。
本版把留痕拆到独立键 `output.dump_rounds`（**默认 False**），
进度仍归 verbose；想看留痕改 yaml / 传配置即可。

改动 6 处（每处断言命中 == 1）：
  A. docstring 标题  v1.23.19 → v1.23.20
  B. __version__     1.23.19 → 1.23.20
  C. DGTF.__init__   加 self.dump_rounds（默认 False）
  D. DGTF.dump_round 守卫 verbose → (verbose and dump_rounds)
  E. DGTF.dump_final 守卫 同上
  F. DEFAULT_CONFIG.output 加 "dump_rounds": False
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.20.py"


def main() -> None:
    b = SRC.read_bytes()
    s = b.decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "源文件不是纯 CRLF"
    assert "\r\r\n" not in s, "源文件有 CRCRLF"
    s = s.replace("\r\n", "\n")

    if '元 DGTF · v1.23.20' in s and '__version__ = "1.23.20"' in s:
        print("已是 v1.23.20，跳过（幂等）")
        return

    def sub(old: str, new: str, tag: str) -> str:
        n = s.count(old)
        assert n == 1, f"[{tag}] 锚点命中 {n} 次（期望 1）"
        return s.replace(old, new)

    # A/B 版本号两处
    s = sub("元 DGTF · v1.23.19", "元 DGTF · v1.23.20", "A 标题")
    s = sub('__version__ = "1.23.19"', '__version__ = "1.23.20"', "B __version__")

    # C DGTF.__init__：加独立开关
    s = sub(
        '        self.verbose = config["output"].get("verbose", True)\n'
        '        self.show_dual = config["output"].get("show_dual_judge", True)\n',
        '        self.verbose = config["output"].get("verbose", True)\n'
        '        # 全量留痕（dump_round / dump_final）的**独立开关**，默认关：\n'
        '        #   verbose 同时管进度与留痕，关它会连每圈进度一起关；留痕只用于调试，\n'
        '        #   产物 md 的「全量字段」附录已承担其职责。要看留痕：output.dump_rounds=true。\n'
        '        self.dump_rounds = config["output"].get("dump_rounds", False)\n'
        '        self.show_dual = config["output"].get("show_dual_judge", True)\n',
        "C __init__",
    )

    # D dump_round 守卫
    s = sub(
        '        if not self.verbose:\n'
        '            return\n'
        '        _rnd = getattr(inp, "round_no", 0) or 0\n',
        '        if not (self.verbose and self.dump_rounds):\n'
        '            return\n'
        '        _rnd = getattr(inp, "round_no", 0) or 0\n',
        "D dump_round",
    )

    # E dump_final 守卫
    s = sub(
        '        if not self.verbose:\n'
        '            return\n'
        '        _rounds = int(getattr(view, "rounds_run", 0) or 0) or int(\n',
        '        if not (self.verbose and self.dump_rounds):\n'
        '            return\n'
        '        _rounds = int(getattr(view, "rounds_run", 0) or 0) or int(\n',
        "E dump_final",
    )

    # F DEFAULT_CONFIG.output 加键（锚点取紧邻的 save_dir + verbose 两行）
    s = sub(
        '        "save_dir": "outputs",\n'
        '        "verbose": True,\n',
        '        "save_dir": "outputs",\n'
        '        "verbose": True,\n'
        '        "dump_rounds": False,\n',
        "F DEFAULT_CONFIG",
    )

    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n"), "转回 CRLF 后不一致"
    assert out.count("\r") == out.count("\r\n"), "存在裸 CR"
    SRC.write_bytes(out.encode("utf-8"))
    print("OK：6 处替换完成，共", len(out.encode("utf-8")), "字节")


if __name__ == "__main__":
    main()

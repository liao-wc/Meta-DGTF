# -*- coding: utf-8 -*-
"""Step9d：补上四处 `stop_floor` 定义（Step9 重写时漏掉的）。

现象：`✗ [P3-10 修] 失败: NameError: name 'stop_floor' is not defined`
根因：Step9 的 `_e6_note_stop(..., min_gain, stop_floor)` 调用了 `stop_floor`，
      但**四处 min_gain 之后的 stop_floor 定义整段被漏掉**（我重写补丁时删了
      那 4 个 sub 块，只留了 collect/cnt/note）——补丁自身没报错，因为那些
      块**根本没在补丁里**。这正是「有接线 ≠ 这跑走得到」。
修法：在四处 `min_gain = ...` 之后补 `stop_floor = ...`（读 `probe.stop_floor`，
      默认 `_GAIN_STOP_FLOOR`）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.27.py"

NEW = ('        # [E6] 停止阈值：与 min_gain 两把尺子（见常量注释）\n'
       '        stop_floor = float(self.config.get("probe", {}).get(\n'
       '            "stop_floor", _GAIN_STOP_FLOOR))\n')


def sub(text, anchor, new, tag, count=1):
    n = text.count(anchor)
    assert n == count, (
        f"[{tag}] 锚点命中 {n} 次（期望 {count}）\n锚点={anchor[:160]!r}")
    return text.replace(anchor, new, count)


def main():
    raw = SRC.read_bytes()
    txt = raw.decode("utf-8")
    assert txt.count("\r\n") == txt.count("\n"), "主文件不是纯 CRLF"
    assert "\r\r\n" not in txt, "主文件含 \\r\\r\\n"
    t = txt.replace("\r\n", "\n")

    # research（多行 min_gain）
    t = sub(
        t,
        '        min_gain = float(\n'
        '            self.config.get("probe", {}).get("min_gain", 0.3))\n'
        '\n'
        '        system = (\n'
        '            "你是【探针 · 自问】阶段（研究层）。\\n"',
        '        min_gain = float(\n'
        '            self.config.get("probe", {}).get("min_gain", 0.3))\n' + NEW +
        '\n'
        '        system = (\n'
        '            "你是【探针 · 自问】阶段（研究层）。\\n"',
        "research.stop_floor", 1)

    # duel
    t = sub(
        t,
        '        min_gain = float(self.config.get("probe", {}).get("min_gain", 0.3))\n'
        '\n'
        '        system = (\n'
        '            "你是【探针 · 自问】阶段（对撞层）。',
        '        min_gain = float(self.config.get("probe", {}).get("min_gain", 0.3))\n'
        + NEW +
        '\n'
        '        system = (\n'
        '            "你是【探针 · 自问】阶段（对撞层）。',
        "duel.stop_floor", 1)

    # meta
    t = sub(
        t,
        '        min_gain = float(self.config.get("probe", {}).get("min_gain", 0.3))\n'
        '\n'
        '        system = (\n'
        '            "你是【探针 · 自问】阶段（元层）。',
        '        min_gain = float(self.config.get("probe", {}).get("min_gain", 0.3))\n'
        + NEW +
        '\n'
        '        system = (\n'
        '            "你是【探针 · 自问】阶段（元层）。',
        "meta.stop_floor", 1)

    # phase
    t = sub(
        t,
        '        min_gain = float(self.config.get("probe", {}).get("min_gain", 0.3))\n'
        '\n'
        '        system = (\n'
        '            "你是【探针 · 自问】阶段。\\n"',
        '        min_gain = float(self.config.get("probe", {}).get("min_gain", 0.3))\n'
        + NEW +
        '\n'
        '        system = (\n'
        '            "你是【探针 · 自问】阶段。\\n"',
        "phase.stop_floor", 1)

    out = t.replace("\n", "\r\n")
    SRC.write_bytes(out.encode("utf-8"))
    print("STEP9D PATCH OK")


if __name__ == "__main__":
    main()

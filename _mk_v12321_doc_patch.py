# -*- coding: utf-8 -*-
"""v1.23.21 的文档与测试同步（保纯 CRLF、幂等）。

- `dgtf_config.yaml` 头部版本 → v1.23.21（键无增删）
- `CHANGELOG.md` 顶部插入 v1.23.21 段
- `smoke_test.py`：SRC → v1.23.21；新增 `check_v12321_tok_line`；main 接线
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
CHG = HERE / "CHANGELOG.md"
ST = HERE / "smoke_test.py"

NEW_SEG = """v1.23.21 相对 v1.23.20

【要解决的问题】工作台要「运行时实时显示消耗 token」，而引擎只在**结束**时打一次
  `完成 | N 次 LLM | M tokens`（`:18081`）—— 运行中拿不到读数。

【改了哪几处】
  1. LLM 调用点（`total_calls` 累加处）补一行
     `logger.info("[tok] calls=%d tokens=%d", …)`：每次调用后打**累计**。
     走 logging 不走 `vp` —— `vp` 受 `output.verbose` 控制，而这是「运行状态」
     不是「调试细节」，关 verbose（v1.23.20 的默认姿态）也必须看得到。

【影响面】纯**新增输出**：产物 md / packed.json 一字不变；旧行为不受影响
  （多出来的只是 stderr 上的 INFO 行，应用层解析后从卡片日志里滤掉）。"""

NEW_CHECK = '''def check_v12321_tok_line():
    """[v1.23.21] LLM 调用点必须打一行 `[tok] calls=N tokens=M`（且走 logging 不走 vp）。

    ① 该行在 LLM 调用点出现**恰好 1 次**；
    ② 接线：它排在 `self.total_calls += 1` **之后**（打的是累计值）；
    ③ 负对照：不许写成 `vp(...)` —— vp 受 verbose 控制，关了就看不见。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    if src.count('logger.info("[tok] calls=%d tokens=%d"') != 1:
        bad.append("LLM 调用点没打 [tok] 行（或不止一处）")
    i_tot = src.find("self.total_calls += 1")
    i_tok = src.find("[tok] calls=%d")
    if not (0 <= i_tot < i_tok):
        bad.append("[tok] 行不在 total_calls 累加之后（打不到累计值）")
    if 'vp("[tok]' in src or "vp('[tok]" in src:
        bad.append("[tok] 用了 vp —— 关 verbose 就看不见了")
    if bad:
        for _x in bad:
            print("  \\u2717 [v12321] %s" % _x)
        return False
    print("  \\u2713 [v12321] LLM 调用后打 [tok] 累计行（logging、非 vp）")
    return True


'''


def patch_yaml() -> None:
    s = YAML.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "yaml 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "# 元 DGTF · v1.23.21 配置文件" in s:
        print("yaml 已改，跳过（幂等）")
        return
    old = "# 元 DGTF · v1.23.20 配置文件"
    n = s.count(old)
    assert n == 1, f"[yaml] 头部锚点命中 {n} 次"
    s = s.replace(old, "# 元 DGTF · v1.23.21 配置文件")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    YAML.write_bytes(out.encode("utf-8"))
    print("yaml OK")


def patch_changelog() -> None:
    s = CHG.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "CHANGELOG 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "v1.23.21 相对 v1.23.20" in s:
        print("CHANGELOG 已改，跳过（幂等）")
        return
    anchor = "---\n\nv1.23.20 相对 v1.23.19"
    n = s.count(anchor)
    assert n == 1, f"[CHANGELOG] 锚点命中 {n} 次"
    s = s.replace(anchor, "---\n\n" + NEW_SEG + "\n\nv1.23.20 相对 v1.23.19")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    CHG.write_bytes(out.encode("utf-8"))
    print("CHANGELOG OK")


def patch_smoke() -> None:
    s = ST.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n") and "\r\r\n" not in s, "smoke_test 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "check_v12321_tok_line" in s:
        print("smoke_test 已改，跳过（幂等）")
        return

    def sub(old: str, new: str, tag: str) -> str:
        n = s.count(old)
        assert n == 1, f"[smoke {tag}] 锚点命中 {n} 次"
        return s.replace(old, new)

    s = sub('SRC = HERE / "元DGTF-V1.23.20.py"', 'SRC = HERE / "元DGTF-V1.23.21.py"', "SRC")
    s = sub("\n\ndef check_p23_units():\n",
            "\n\n" + NEW_CHECK + "def check_p23_units():\n", "插入 check")
    s = sub("    if not check_v12320_quiet_output():\n        return 1\n",
            "    if not check_v12320_quiet_output():\n        return 1\n"
            "    if not check_v12321_tok_line():\n        return 1\n", "main 接线")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    ST.write_bytes(out.encode("utf-8"))
    print("smoke_test OK")


if __name__ == "__main__":
    patch_yaml()
    patch_changelog()
    patch_smoke()

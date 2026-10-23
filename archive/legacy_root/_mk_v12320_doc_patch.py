# -*- coding: utf-8 -*-
"""v1.23.20 的 yaml 与 CHANGELOG 同步（保纯 CRLF、幂等）。

yaml：
  1. 头部版本 v1.23.19 → v1.23.20
  2. output.show_ing / show_manifest → false（注释里写的就是「建议默认 false」）
  3. output 新增 dump_rounds: false
CHANGELOG.md：在 v1.23.19 段之前插入 v1.23.20 段（最新在最前）。
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
YAML = HERE / "dgtf_config.yaml"
CHG = HERE / "CHANGELOG.md"

NEW_SEG = """v1.23.20 相对 v1.23.19

【要解决的问题】终端跑起来被两类大块刷屏，混得看不清进度：
  ①`【ing 全文】` / `【view 全文】`（对撞/显形的全文框）—— 与产物略读重复；
  ②`圈全量留痕` / `收尾留痕`（每层每圈把 view 的全部字段逐条打出来）。
  结果是「想看进度就得忍受满屏留痕」。

【改了哪几处】
  1. 留痕（`dump_round` / `dump_final`）从 `verbose` 里拆出**独立开关**
     `output.dump_rounds`，**默认 false**。`verbose` 仍管进度，
     于是「有进度、无留痕」第一次能同时成立。
  2. `DEFAULT_CONFIG.output` 新增键 `"dump_rounds": False`。
  3. 出厂 `dgtf_config.yaml` 把 `output.show_ing` / `output.show_manifest`
     改回 `false`（这两键注释里写的就是「【建议】默认：false」，
     实际值在某轮调试里留成了 true）。

【影响面】纯输出层：产物 md / packed.json 一字不变。要看留痕时把
  `output.dump_rounds` 改 true 即恢复；留痕内容在产物 md 的
  「全量字段」附录里本来就有副本。"""


def patch_yaml() -> None:
    s = YAML.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "yaml 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "  dump_rounds: false\n" in s:
        print("yaml 已改，跳过（幂等）")
        return

    def sub(old: str, new: str, tag: str) -> str:
        n = s.count(old)
        assert n == 1, f"[yaml {tag}] 锚点命中 {n} 次（期望 1）"
        return s.replace(old, new)

    s = sub("# 元 DGTF · v1.23.19 配置文件", "# 元 DGTF · v1.23.20 配置文件", "头部版本")
    # 锚点带换行前缀：yaml 注释块里也有「show_ing: true」这类子串（缩进不同）
    s = sub("\n  show_ing: true\n", "\n  show_ing: false\n", "show_ing")
    s = sub("\n  show_manifest: true\n", "\n  show_manifest: false\n", "show_manifest")
    s = sub("\n  verbose: true\n", "\n  verbose: true\n  dump_rounds: false\n", "dump_rounds")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    YAML.write_bytes(out.encode("utf-8"))
    print("yaml OK")


def patch_changelog() -> None:
    s = CHG.read_bytes().decode("utf-8")
    assert s.count("\r\n") == s.count("\n"), "CHANGELOG 不是纯 CRLF"
    s = s.replace("\r\n", "\n")
    if "v1.23.20 相对 v1.23.19" in s:
        print("CHANGELOG 已改，跳过（幂等）")
        return
    anchor = "---\n\nv1.23.19 相对 v1.23.18"
    n = s.count(anchor)
    assert n == 1, f"[CHANGELOG] 锚点命中 {n} 次（期望 1）"
    s = s.replace(anchor, "---\n\n" + NEW_SEG + "\n\nv1.23.19 相对 v1.23.18")
    out = s.replace("\n", "\r\n")
    assert out.count("\n") == out.count("\r\n") and out.count("\r") == out.count("\r\n")
    CHG.write_bytes(out.encode("utf-8"))
    print("CHANGELOG OK")


if __name__ == "__main__":
    patch_yaml()
    patch_changelog()

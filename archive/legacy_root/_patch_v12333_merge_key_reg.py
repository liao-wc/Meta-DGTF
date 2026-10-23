# -*- coding: utf-8 -*-
"""[第六期收尾] 把 `merge_expand` 登记进 `DEFAULT_CONFIG["actions"]` + 出厂 yaml。

## 为什么要补
  `_action_on(config, "merge_expand", False)` 是**读取端**：
  `actions` 段有该键就用它，没有就落**调用点给的那个默认 false**。
  ⇒ 行为上「默认关」是对的，但 **配置层看不见这个键** ⇒
    ① 用户无法在 yaml 里打开它（**有开关但没登记 = 配置写了也没用**）；
    ② 审计 J 类（「每个键都要有读点」）的另一面 —— 这里是「有读点但没键」。

## 锚点纪律
  · 主文件纯 CRLF：read_bytes → 断言 → 转 LF → 替换（命中 == 1）→ 转回 → write_bytes；
  · 出厂 yaml 同步：头部版本已有；这里只加**一行键**（放在 `parallel_expand` 旁）。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"
YML = HERE / "dgtf_config.yaml"

# ── 主文件：DEFAULT_CONFIG["actions"] 里，紧挨 parallel_expand 加一行 ──
MAIN_ANCHOR = '''        "parallel_expand": True,
        "input_sanity": True,'''
MAIN_NEW = '''        "parallel_expand": True,
        # ★ [第六期 · 降本 L1] 阴阳合并成一次调用（省 1 次往返 + 1 份重复 user token）。
        #   **默认 false** ⇒ 与历史行为逐字一致（零行为差）；打开需显式 opt-in。
        "merge_expand": False,
        "input_sanity": True,'''

# ── 出厂 yaml：同段里加同名的键 ──
YML_ANCHOR = "  parallel_expand: true"
YML_NEW = ("  parallel_expand: true\n"
           "  # ★ [第六期 · 降本 L1] 阴阳合并成一次调用（默认 false ⇒ 零行为差）。\n"
           "  #   打开后：阴阳两臂共用一次 LLM 调用（省 1 次往返 + 1 份重复 user 输入）。\n"
           "  merge_expand: false")


def _rw(p: Path, fn):
    raw = p.read_bytes()
    txt = raw.decode("utf-8")
    crlf = txt.count("\r\n")
    lf = txt.count("\n") - crlf
    assert lf == 0, "%s 非纯 CRLF（LF-only=%d）" % (p.name, lf)
    assert b"\r\r\n" not in raw
    s = txt.replace("\r\n", "\n")
    s2 = fn(s)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    p.write_bytes(out)
    back = p.read_bytes().decode("utf-8")
    assert back.count("\n") - back.count("\r\n") == 0
    return back


def main() -> int:
    for p, a, label in ((SRC, MAIN_ANCHOR, "主文件"), (YML, YML_ANCHOR, "出厂 yaml")):
        # 幂等
        cur = p.read_bytes().decode("utf-8")
        if "merge_expand" in cur:
            print("[%s] 已有 merge_expand（幂等跳过）" % label)
            continue

    def mk(a, b, what):
        def fn(s):
            n = s.count(a)
            assert n == 1, "[%s] 锚点命中 %d 次（应 1）" % (what, n)
            return s.replace(a, b, 1)
        return fn

    t1 = _rw(SRC, mk(MAIN_ANCHOR, MAIN_NEW, "主文件"))
    n1 = t1.count('"merge_expand": False')
    assert n1 == 1, "主文件里 merge_expand 键数 = %d（应 1）" % n1
    print("OK 主文件已登记 merge_expand（%d 行 / 纯 CRLF）" % (t1.count("\n") + 1))

    t2 = _rw(YML, mk(YML_ANCHOR, YML_NEW, "出厂 yaml"))
    n2 = t2.count("merge_expand: false")
    assert n2 == 1, "yaml 里 merge_expand 键数 = %d（应 1）" % n2
    print("OK 出厂 yaml 已登记 merge_expand")
    return 0


if __name__ == "__main__":
    sys.exit(main())

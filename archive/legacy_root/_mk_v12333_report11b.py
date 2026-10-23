# -*- coding: utf-8 -*-
"""报告补 11.9（键登记）+ 记忆补记。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
RP = HERE / "v12333_报告.md"

A = """  本次的代价：一次 59.3 min / 136 calls 的真跑 + 一轮根因定位。
  若第六期落地时就配了这条判据，缺陷会在**第一秒**被拦下。
"""

NEW = """  本次的代价：一次 59.3 min / 136 calls 的真跑 + 一轮根因定位。
  若第六期落地时就配了这条判据，缺陷会在**第一秒**被拦下。

### 11.9 ★ 收尾时又逮到一处同族问题：`merge_expand` 有读点、没登记

  · 核查「修复是否完整」时顺手查配置：`_action_on(config, "merge_expand", False)`
    是**读取端**（`actions` 段有键就用、没有就落调用点给的默认 false）
    ⇒ 行为上「默认关」**是对的**。
  · 但它**没登记进 `DEFAULT_CONFIG["actions"]`**（AST + flat 展开实测 192 键里没有），
    出厂 `dgtf_config.yaml` 也没有 ⇒
    ① **用户在 yaml 里打不开它**（有开关但没登记 = 配置写了也没用）；
    ② 它正好是审计 **J 类**（「每个键都要有读点」）的**反面** ——
       这次是「有读点、没键」，而 J 类判据只查「有键、没读点」⇒ **两个方向都要有**。
  · 修（`_patch_v12333_merge_key_reg.py`）：`DEFAULT_CONFIG["actions"]` +
    出厂 yaml 各登记一行（**默认 false ⇒ 零行为差**）。
  · 验收：配置键 **192 → 193**；冒烟配置判据「键已列全（193 项）/ 手调 29 项全部已登记」
    ⇒ 两向对账仍 **0 差**。
  · ★ 通则：**新增任何开关，必须同时登记「读取端默认值」与「配置声明」** ——
    只做前者，开关是隐形的；只做后者，是「写了没生效」。
"""


def main() -> int:
    b = RP.read_bytes()
    txt = b.decode("utf-8")
    assert b"\r\r\n" not in b
    crlf = (txt.count("\r\n") > 0 and txt.count("\r\n") == txt.count("\n"))
    flat = txt.replace("\r\n", "\n")
    assert flat.count(A) == 1, "锚点命中 %d 次" % flat.count(A)
    assert "11.9" not in flat, "已补过"
    out = flat.replace(A, NEW, 1)
    res = out.replace("\n", "\r\n") if crlf else out
    data = res.encode("utf-8")
    assert b"\r\r\n" not in data
    RP.write_bytes(data)
    print("OK 报告已补 11.9")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

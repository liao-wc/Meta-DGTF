# -*- coding: utf-8 -*-
"""CHANGELOG 补「merge_expand 键登记」一小段（接在真缺陷段之后）。"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"

A = """【验收（第六期）】判据 **㉗~㉛**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +"""

NEW = """【★ 收尾补漏：`merge_expand` 有读点、没登记】
  · `_action_on(config, "merge_expand", False)` 是**读取端**：`actions` 段有该键就用它，
    没有就落**调用点给的默认 false** ⇒ 行为上「默认关」是对的。
  · 但它**没登记进 `DEFAULT_CONFIG["actions"]`** ⇒
    ① 用户在 yaml 里**打不开**（有开关但没登记 = 配置写了也没用）；
    ② 与审计 J 类（「每个键都要有读点」）**互为反面** —— 这次是「有读点、没键」。
  · 修（`_patch_v12333_merge_key_reg.py`）：`DEFAULT_CONFIG["actions"]` 与出厂 yaml
    各登记一行（**默认 false ⇒ 零行为差**）。配置键 **192 → 193**，两向对账仍 **0 差**。
  · ★ 通则：**新增任何开关，必须同时登记「读取端默认值」与「配置声明」** ——
    只做前者，开关是隐形的；只做后者，是「写了没生效」。

【验收（第六期）】判据 **㉗~㉛**：㉗ 合并开关默认关 + 已接线 / ㉘ 分歧度方向 +"""


def main() -> int:
    b = CL.read_bytes()
    assert b"\r\r\n" not in b
    flat = b.decode("utf-8").replace("\r\n", "\n")
    assert flat.count(A) == 1, "锚点命中 %d 次" % flat.count(A)
    assert "收尾补漏" not in flat, "已补过"
    out = flat.replace(A, NEW, 1)
    data = out.encode("utf-8")
    assert b"\r\r\n" not in data
    CL.write_bytes(data)
    print("OK CHANGELOG 已补键登记段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

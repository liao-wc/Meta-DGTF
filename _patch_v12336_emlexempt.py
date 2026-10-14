# -*- coding: utf-8 -*-
"""修 EML 的 3 类「学而不做」：加**显式豁免表**，配**两向对账**。

## 问题（本版实测逮到）
`eml_candidates_from_result` 会生成 4 种 `action.key`，而 `_eml_apply` 只有
2 个分支（`rounds_delta` / `duty_floor`）⇒
  · `carve_first` / `tri_advisory_only` / `note_cost_no_gain`
  **生成 → 过闸 → 存库 → 召回**，但**永不生效**，且**无判据可见**
  （召回日志只说「用了几条」，不说「几条真生效」）。

## 修法（两条腿）
① **显式豁免表** `_EML_RECORD_ONLY`：把「只记录、不应用」**写明**并写清原因
   —— 「不在 `_eml_apply` 里」从「像是忘了」变成「**显式的决定**」；
② **两向对账**（另一处补判据）：候选**生成得出**的每个 key，必须
   **要么**在 `_eml_apply` 有分支、**要么**在豁免表里登记。

## 为什么 `carve_first` 不直接接线
它要求的是「**下一跑**这些层优先雕」—— 而本引擎**没有「下一跑的调度接口」**
（跨跑建议走 AutoTune 的**建议文件**，红线：建议与执行分开）。
⇒ 强行接线会变成「在一次跑的中途改另一件事的优先级」，语义不对。
**诚实登记比硬接好**（并把原因写清，将来有跨跑调度接口时再升级）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "元DGTF-V1.23.36.py"

ANCHOR = '''#: [联网全接] 30 个环节的开关名'''

NEW = '''#: [EML] **只记录、不应用**的动作 key（显式豁免 + 原因）。
#: ★ 为什么要有它：EML 候选里有些 key 是**证据类**（记账），本来就不该落到
#:   `_eml_apply` 的执行面；但「不在 `_eml_apply` 里」这件事**必须显式登记**，
#:   否则它看起来像「忘了接」—— 而且**没有任何判据会发现**（本版实测：
#:   这 3 个 key 各只出现 1 次，生成→存库→召回却永不生效）。
#: ★ 判据（两向对账）：候选生成得出的每个 key，必须**要么**在 `_eml_apply`
#:   有分支、**要么**在这张表里。
_EML_RECORD_ONLY = {
    "tri_advisory_only":
        "证据类：记「三态只做建议」这个事实，本身不是动作（无可执行面）",
    "note_cost_no_gain":
        "证据类：成本账（花了钱没增益），供人/AutoTune 读，不自动调参",
    "carve_first":
        "跨跑类：它要的是「**下一跑**这些层优先雕」，而本引擎没有跨跑调度"
        "接口（跨跑建议走 AutoTune 的建议文件，红线：建议与执行分开）"
        "⇒ 硬接会变成「在一次跑中途改另一件事的优先级」，语义不对",
}


#: [联网全接] 30 个环节的开关名'''


def main():
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "主文件应为纯 CRLF"
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    assert s.count(ANCHOR) == 1, "锚点命中 %d 次" % s.count(ANCHOR)
    s = s.replace(ANCHOR, NEW, 1)
    assert "_EML_RECORD_ONLY" in s
    # ★ 三个 key 必须在表里
    for _k in ("carve_first", "tri_advisory_only", "note_cost_no_gain"):
        assert '"%s"' % _k in s, "缺 %s" % _k
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK `_EML_RECORD_ONLY` 豁免表已加；行数 %d" % out.count(b"\n"))


main()

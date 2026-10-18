# -*- coding: utf-8 -*-
"""补线后同步三处文档里的冒烟数（260 → 261），避免文档漂移。

涉及：
  · `CHANGELOG.md` 里 v1.23.61 收束摘要
  · `README.md` 五道门说明与基线表
  · `v12361_报告.md` 速览表与验证段

★ 为什么必须同步：这三处都写着"260 ✓"，补线后真实值是 261。
  数字漂移比写错更坏 —— 后来的人拿 260 去核对会以为冒烟掉了一项。
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
EDITS = {
    "CHANGELOG.md": [
        ("**验收**：冒烟 260 ✓ / 0 ✗；",
         "**验收**：冒烟 261 ✓ / 0 ✗（含补线的 `check_p0_156_units`）；"),
    ],
    "README.md": [
        ("# 1) 全套冒烟（260 项）", "# 1) 全套冒烟（261 项）"),
        ("| 冒烟 | **260 ✓ / 0 ✗** |", "| 冒烟 | **261 ✓ / 0 ✗** |"),
    ],
    "v12361_报告.md": [
        ("| 冒烟 | **260 ✓ / 0 ✗**（上版 259，+1 = 新判据） |",
         "| 冒烟 | **261 ✓ / 0 ✗**（上版 259：+1 新判据 +1 补线的历史判据） |"),
    ],
}

for name, pairs in EDITS.items():
    p = HERE / name
    raw = p.read_bytes()
    crlf = raw.count(b"\r\n") == raw.count(b"\n")
    s = raw.decode("utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, "%s：锚点命中 %d 次（%s）" % (name, s.count(old), old[:30])
        s = s.replace(old, new)
    p.write_bytes(s.encode("utf-8"))
    print("  [OK] %-18s 已同步（%s）" % (name, "CRLF" if crlf else "LF"))

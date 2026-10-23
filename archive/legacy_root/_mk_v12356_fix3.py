# -*- coding: utf-8 -*-
"""修 v1.23.56 撞版次批注红线的那一行注释（`v1.23.50 立命的…`）。

★ 红线：代码里的注释/docstring **不写版次标签**（版本信息只进 CHANGELOG）。
  我这次又在注释里写了 `v1.23.50` ⇒ `check_v1236_no_version_tags` 判红，
  而且它**中止了整个冒烟**（只跑了 179 项就停）—— 这条红线有牙。
"""
import ast
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
p = HERE / "元DGTF-V1.23.56.py"
raw = p.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
s = raw.decode("utf-8").replace("\r\n", "\n")

OLD = '        #   v1.23.50 立命的「被杀跑次也能结算成本」要求**按 run_id 累计**。\n'
NEW = '        #   「被杀跑次也能结算成本」这条立命要求**按 run_id 累计**。\n'

assert s.count(OLD) == 1, "锚点命中 %d 次" % s.count(OLD)
s = s.replace(OLD, NEW)
ast.parse(s)

# 自检：新增段里不再出现版次标签（只允许第 4 行标题与 __version__）
_bad = [ln for i, ln in enumerate(s.split("\n"), 1)
        if "v1." in ln and i not in (4,) and "__version__" not in ln
        and not ln.lstrip().startswith(("★", "[", "·")) is False]
_lines_with_tag = [i for i, ln in enumerate(s.split("\n"), 1)
                   if "v1.2" in ln and i != 4 and "__version__" not in ln]
assert 13905 not in _lines_with_tag, "13905 还有标签"

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\n") == out.count(b"\n") and out.count(b"\r\r\n") == 0
p.write_bytes(out)
print("已改掉注释里的版次标签（13905）")

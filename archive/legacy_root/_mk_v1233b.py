#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[v1.23.3] 主文件补丁 B：三票的 `voter` 记**真票号**（不随弃票重编号）。

发现路径：写 id 归一化的端到端判据时，`B3`（越界票弃票）的期望值算不出来 ——
因为原实现是：

    s["votes"] = [{"voter": vi, "label": v} for vi, v in enumerate(vs)]

`vi` 是**位置**，不是票号。只要有一张票被丢（失败 / 空票 / 越界），
剩下的票就被**重新编号** ⇒ 产物里 `voter=0,1` 其实是「第 2、3 张票」。
而配对类指标（`agree13` = 第 1 与第 3 张票的一致率）是**按票号**配的
⇒ 比的是**别的 prompt 对**，且读者看不出。

修法：`votes` 存 `(票号, 标签)`，产物写 `{"voter": 真票号, "label": ...}`。
无弃票时与改前**逐字相同**（票号 == 位置），只有弃票时才出现差别 ——
而那时改前的值是**错的**。
"""
from pathlib import Path
import ast

P = Path(__file__).resolve().parent / "元DGTF-V1.23.3.py"
raw = P.read_bytes().decode("utf-8")
assert raw.count("\r\n") == raw.count("\n"), "主文件不是纯 CRLF"
s = raw.replace("\r\n", "\n")


def sub_once(old, new, tag):
    global s
    assert s.count(old) == 1, "%s：锚点命中 %d 次" % (tag, s.count(old))
    s = s.replace(old, new)
    print("  · %s" % tag)


sub_once("        votes: Dict[int, List[str]] = {}",
         "        # [v1.23.3] 存 **(票号, 标签)** 而不是只存标签：丢弃一张票时\n"
         "        #   位置会被**重新编号** ⇒ 产物里的 `voter` 变成「第几个还在的」，\n"
         "        #   而 `agree13` 等配对指标是按**票号**配的 ⇒ 比的是别的 prompt 对。\n"
         "        votes: Dict[int, List[Tuple[int, str]]] = {}",
         "B1 votes 改存 (票号, 标签)")

sub_once("            for _sid2, _st2 in (_jb or {}).items():\n"
         "                votes.setdefault(_sid2, []).append(_st2)",
         "            for _sid2, _st2 in (_jb or {}).items():\n"
         "                votes.setdefault(_sid2, []).append((_vi, _st2))",
         "B2 入票带票号")

sub_once("            n += 1\n"
         "            cnt: Dict[str, int] = {}\n"
         "            for v in vs:\n"
         "                cnt[v] = cnt.get(v, 0) + 1",
         "            n += 1\n"
         "            _vl = [lb for _bi, lb in vs]\n"
         "            cnt: Dict[str, int] = {}\n"
         "            for v in _vl:\n"
         "                cnt[v] = cnt.get(v, 0) + 1",
         "B3 计数只看标签")

sub_once('            s["_tri_votes"] = list(vs)',
         '            s["_tri_votes"] = list(_vl)', "B4 _tri_votes")

sub_once("                if top == len(vs):",
         "                if top == len(_vl):", "B5 top == 票数")

sub_once('                s["label_disagreed"] = [old] + list(vs)',
         '                s["label_disagreed"] = [old] + list(_vl)',
         "B6 label_disagreed")

sub_once('            s["votes"] = [{"voter": vi, "label": v}\n'
         '                          for vi, v in enumerate(vs)]\n'
         '            s["agreement"] = round(top / len(vs), 2)',
         '            # ★ 记**真票号**：丢一张票时不再把剩余票重编号 ——\n'
         '            #   配对类指标必须比同一个 prompt 对（v1.23.3 抓到）。\n'
         '            s["votes"] = [{"voter": _bi, "label": lb}\n'
         '                          for _bi, lb in vs]\n'
         '            s["agreement"] = round(top / len(_vl), 2)',
         "B7 votes 写真票号")

# changelog 补一句
sub_once("""    ★ 只归一、不猜：越界一律弃票而不是硬塞。
""",
         """    ★ 只归一、不猜：越界一律弃票而不是硬塞。
    ★ 连带修掉同一族的第二处：产物里的 `votes[].voter` 原先记的是
      **位置**（`enumerate(vs)`），只要有一张票被丢，剩余票就被重新编号
      ⇒ `agree13`（第 1 与第 3 张票）实际比的是**别的 prompt 对**。
      改为记**真票号**（无弃票时与改前逐字相同，只有弃票时才不同 ——
      而那时改前的值是错的）。
""", "B8 changelog")

out = s.replace("\n", "\r\n").encode("utf-8")
assert out.count(b"\r\r\n") == 0
ast.parse(s)
P.write_bytes(out)
print("  · 已写 %s" % P.name)

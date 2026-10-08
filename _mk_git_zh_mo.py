# -*- coding: utf-8 -*-
"""把 git 的 zh_CN.po 编译成 git.mo（纯 Python，不依赖 msgfmt/polib）。

为什么需要这个：Git for Windows **不附带** git 的消息语言包；而且从
v2.44.0.windows.1 起，上游把 gettext 工具包（msgfmt 等）也从安装包里删了。
所以「让 git 说中文」必须自己把 .po 编译成 .mo。

用法：
    python _mk_git_zh_mo.py <zh_CN.po> <输出 git.mo>

MO 格式（小端 32 位）：
    magic=0x950412de, revision=0, N, 原文表偏移, 译文表偏移, 哈希表大小=0, 哈希表偏移=0
    原文表 N×(长度, 偏移)，译文表 N×(长度, 偏移)，随后是字符串数据。两个表按**原文排序**。

★ 中文的 Plural-Forms 是 nplurals=1（plural=0），所以只需取 msgstr[0]；
  其余复数形式忽略。带 msgctxt 的条目按 GNU 约定拼成 "msgctxt\\x04msgid"。
★ 默认跳过 fuzzy 与 obsolete（#~）条目 —— 与 msgfmt 的默认行为一致。
"""
import re
import struct
import sys
from pathlib import Path

EOT = "\x04"


def parse_po(text):
    """→ [(key, value)]，key 已按需要拼好 msgctxt。顺序随后会按 key 排序。"""
    lines = text.split("\n")
    entries = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        ctx = mid = mstr = None
        plurals = {}
        fuzzy = False
        obsolete = False
        # 收集注释
        while i < n and lines[i].startswith("#"):
            if lines[i].startswith("#~"):
                obsolete = True
            if "fuzzy" in lines[i]:
                fuzzy = True
            i += 1
        # 收集字段，直到空行
        while i < n and lines[i].strip():
            raw = lines[i]
            m = re.match(r'^(msgctxt|msgid|msgid_plural|msgstr(?:\[(\d+)\])?)\s+"(.*)"\s*$',
                         raw)
            if not m:
                break
            field, idx, frag = m.group(1), m.group(2), m.group(3)
            parts = [frag]
            i += 1
            # 续行
            while i < n:
                m2 = re.match(r'^"(.*)"\s*$', lines[i])
                if not m2:
                    break
                parts.append(m2.group(1))
                i += 1
            val = "".join(parts)
            val = (val.replace('\\n', "\n").replace('\\t', "\t")
                      .replace('\\"', '"').replace("\\\\", "\\"))
            if field == "msgctxt":
                ctx = val
            elif field == "msgid":
                mid = val
            elif field == "msgid_plural":
                plurals["__plural__"] = val
            elif field.startswith("msgstr"):
                plurals[int(idx) if idx is not None else 0] = val
        if obsolete or fuzzy or mid is None or mid == "":
            continue
        key = (ctx + EOT + mid) if ctx else mid
        val = plurals.get(0, "")
        if val == "":
            continue
        entries.append((key, val))
    return entries


def write_mo(entries, out_path):
    entries = sorted(set(entries), key=lambda kv: kv[0].encode("utf-8"))
    keys = [k.encode("utf-8") for k, _ in entries]
    vals = [v.encode("utf-8") for _, v in entries]
    n = len(entries)
    header = struct.pack("<7I", 0x950412DE, 0, n, 28, 28 + 8 * n, 0, 0)
    off = 28 + 16 * n
    ktab, kdata = [], []
    for k in keys:
        ktab.append(struct.pack("<2I", len(k), off))
        kdata.append(k)
        off += len(k) + 1
    vtab, vdata = [], []
    for v in vals:
        vtab.append(struct.pack("<2I", len(v), off))
        vdata.append(v)
        off += len(v) + 1
    blob = (header + b"".join(ktab) + b"".join(vtab)
            + b"".join(x + b"\x00" for x in kdata)
            + b"".join(x + b"\x00" for x in vdata))
    Path(out_path).write_bytes(blob)
    return n, len(blob)


def read_mo(path):
    """独立读回（自检用）：不共享写侧的排序/偏移假设。"""
    b = Path(path).read_bytes()
    magic, rev, n, o_off, t_off, hs, ho = struct.unpack("<7I", b[:28])
    assert magic == 0x950412DE, "magic 不对"
    out = {}
    for i in range(n):
        kl, ko = struct.unpack("<2I", b[o_off + 8 * i: o_off + 8 * i + 8])
        vl, vo = struct.unpack("<2I", b[t_off + 8 * i: t_off + 8 * i + 8])
        k = b[ko:ko + kl].decode("utf-8")
        v = b[vo:vo + vl].decode("utf-8")
        out[k] = v
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = Path(src).read_bytes().decode("utf-8")
    ent = parse_po(text)
    n, size = write_mo(ent, dst)
    back = read_mo(dst)
    print("条目 %d（写入 %d 字节）" % (n, size))
    print("读回 %d 条" % len(back))
    # 抽三条真实 git 消息核对
    probes = [
        "fatal: not a git repository (or any of the parent directories): %s",
        "Changes to be committed:",
        "nothing to commit, working tree clean",
    ]
    hit = 0
    for p in probes:
        v = back.get(p)
        print("  %-62s -> %s" % (p[:60], (v or "★ 未命中")[:40]))
        if v:
            hit += 1
    print("抽检命中 %d/3" % hit)
    return 0 if n > 1000 and hit >= 1 else 1


if __name__ == "__main__":
    sys.exit(main())

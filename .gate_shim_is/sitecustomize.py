# -*- coding: utf-8 -*-
"""仅用于本机 fast_gate 的临时目录兼容垫片。

Windows + DSH 受限令牌下，tempfile.mkdtemp() 用 0o700 建的目录
再写入会被拒绝（目录 ACL 只给了包外不可见的 SID）。这里改为
0o777 建目录，语义仍是“新建唯一临时目录”，只影响本次门禁进程。
"""
import os
import tempfile
import uuid


def _mkdtemp(suffix=None, prefix=None, dir=None):
    suffix = suffix or ""
    prefix = prefix or "tmp"
    base = dir or tempfile.gettempdir()
    for _ in range(1000):
        path = os.path.join(base, prefix + uuid.uuid4().hex + suffix)
        try:
            os.mkdir(path, 0o777)
        except FileExistsError:
            continue
        return path
    raise FileExistsError("could not create temp dir under %r" % (base,))


tempfile.mkdtemp = _mkdtemp

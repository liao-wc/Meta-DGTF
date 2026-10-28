# -*- coding: utf-8 -*-
"""溯源指纹判据（Round 132）。"""
from dgtf_v2.provenance import (artifact_provenance, config_hash,
                                question_fingerprint)

P, F = [], []


def ck(n, ok, info=""):
    (P if ok else F).append(n)
    print(("PASS " if ok else "FAIL ") + n + (" :: " + str(info) if not ok else ""))


def main() -> int:
    prov = artifact_provenance({"b": 2, "a": 1})
    need = ("schema", "engine_file", "engine_version", "git_sha",
            "app_version", "config_hash")
    ck("P1 provenance 必填键", all(k in prov for k in need), prov)
    ck("P2 git_sha 形状（hex 或 unknown）",
       prov["git_sha"] == "unknown"
       or (len(prov["git_sha"]) >= 7
           and all(c in "0123456789abcdef" for c in prov["git_sha"])),
       prov["git_sha"])
    ck("P3 config_hash 稳定且区分",
       config_hash({"a": 1, "b": 2}) == config_hash({"b": 2, "a": 1})
       and config_hash({"a": 1}) != config_hash({"a": 2}),
       (config_hash({"a": 1}), config_hash({"a": 2})))
    ck("P4 问题指纹忽略空白/标点",
       question_fingerprint("2+2等于几？") == question_fingerprint(" 2+2 等于几 ")
       and question_fingerprint("2+2等于几") != question_fingerprint("3+3等于几"))

    # ── 版本指纹不再自相矛盾（此前 file 与 version 各写各的，且都过期） ──
    import re as _re
    import sys as _sys
    import pathlib as _pl
    import dgtf_v2.provenance as _pv

    _ef, _ev = prov["engine_file"], prov["engine_version"]
    _m = _re.search(r"V(\d+\.\d+\.\d+)", str(_ef))
    ck("P5 ★ engine_version 与 engine_file 文件名里的版本一致（不再各写各的）",
       bool(_m) and _ev == "V" + _m.group(1), f"{_ev} vs {_ef}")
    ck("P6 engine_file 指向真实存在的文件（不是过期的字面量）",
       _ef == "unknown" or (_pv.ROOT / _ef).is_file(), _ef)
    _psrc = _pl.Path(_pv.__file__).read_text(encoding="utf-8", errors="replace")
    ck("P7 静态：provenance.py 源码里没有硬编码版本字面量（否则下次还会漂）",
       not _re.search(r"V\d+\.\d+\.\d+", _psrc), "版本号只能从文件名推导")

    # ★ 构造性证明「版本号是动态解析的，不是常量」：换掉主程序文件 ⇒ 跟着变。
    _main = _sys.modules.get("__main__")
    _old = getattr(_main, "__file__", None)
    try:
        _main.__file__ = str(_pv.ROOT / "dgtf_engine" / "dgtf_v2" / "engine"
                             / "Meta-DGTF-V9.9.9.py")
        _pv._CACHE.pop("engine_path", None)
        ck("P8 ★ 动态解析（不是常量）：换掉主程序文件 ⇒ 版本号跟着变",
           _pv.engine_version() == "V9.9.9"
           and _pv.engine_file().endswith("Meta-DGTF-V9.9.9.py"),
           f"{_pv.engine_version()} / {_pv.engine_file()}")
    finally:
        if _old is not None:
            _main.__file__ = _old
        _pv._CACHE.pop("engine_path", None)
    ck("P9 ★ 恢复后回到真实最高版本（不残留假路径）",
       _pv.engine_version() == "V" + ".".join(
           str(x) for x in sorted(
               (tuple(int(y) for y in m.groups())
                for f in (_pv.ROOT / "dgtf_engine" / "dgtf_v2" / "engine")
                .glob("Meta-DGTF-V*.py")
                for m in [_re.search(r"V(\d+)\.(\d+)\.(\d+)", f.name)] if m)
           )[-1]), _pv.engine_version())

    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())

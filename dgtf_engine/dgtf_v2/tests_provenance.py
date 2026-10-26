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
    print("\nTOTAL PASS %d / FAIL %d" % (len(P), len(F)))
    return 0 if not F else 1


if __name__ == "__main__":
    raise SystemExit(main())

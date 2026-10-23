#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R44 第 5 条：本地资料库**导入**（多格式 + 上限 + 自动解析成可读入的锚点）。

用户报「导入文件没反应」+ 要求「支持各类型文档和图片、最多 50 个、每个 100M，
并自动解析成支持运行时可读入的信息」。

改动分两处：
  ① `library.import_files`：收 **base64 二进制**（原来只收文本 ⇒ PDF/图片抠出来是乱码），
     强制上限（50 个 / 单文件 100MB），逐个走 `docparse.extract` 解析，
     原始文件留档到 `anchors/_raw/`（**解析失败也不丢原件**），逐文件回报结果。
     ★ 同时保留老的 `{name, content}` 文本入参 —— `dgtf_app/selftest.py` 在用。
  ② `_rebuild_anchor`：长文档**分块**进锚点（原来只取前 2000 字），
     让「可读入」对长文档也成立。

`library.py` 是**纯 LF**。

    python _mk_r44_import.py
"""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE / "dgtf_app" / "library.py"

IMP_OLD = """import json
import re
from pathlib import Path

import outputs_index as oi"""
IMP_NEW = """import base64
import json
import re
from pathlib import Path

import docparse
import outputs_index as oi"""

CONST_ANCHOR = 'ANCHOR_FILE = ANCHORS_DIR / "external_anchor.json"'
CONST_NEW = CONST_ANCHOR + '''
RAW_DIR = ANCHORS_DIR / "_raw"                      # 原始文件留档（解析失败也不丢原件）

# ★ R44：用户定的上限 —— 单次最多 50 个、单文件 100MB。
MAX_FILES = 50
MAX_FILE_BYTES = 100 * 1024 * 1024
# 长文档按块进锚点（引擎一次能读的量有限；分块后长文的覆盖面才够）
CHUNK_CHARS = 2000
MAX_CHUNKS_PER_FILE = 40'''

REBUILD_OLD = '''def _rebuild_anchor() -> None:
    """扫导入目录 → 重建合并的锚点快照（引擎认这个格式）。"""
    items = []
    if ANCHORS_DIR.is_dir():
        for i, p in enumerate(sorted(ANCHORS_DIR.iterdir()), 1):
            if not p.is_file() or p.name == ANCHOR_FILE.name:
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            items.append({"id": f"L{i}", "claim": txt[:400].strip(),
                          "content": txt[:2000], "source": p.name,
                          "kind": "local", "tier": 2})'''

REBUILD_NEW = '''def _rebuild_anchor() -> None:
    """扫导入目录 → 重建合并的锚点快照（引擎认这个格式）。

    ★ R44：**长文档分块**（原来每份只取前 2000 字）—— 一份 5 万字的资料，
    原来进锚点的只有开头那一屏；现在按 `CHUNK_CHARS` 切成多块（每份最多
    `MAX_CHUNKS_PER_FILE` 块），`id` 形如 `L3-2`、`part` 标明第几块，
    「运行时可读入」对长文才真的成立。`_raw/` 是目录，`is_file()` 天然跳过。
    """
    items = []
    if ANCHORS_DIR.is_dir():
        for i, p in enumerate(sorted(ANCHORS_DIR.iterdir()), 1):
            if not p.is_file() or p.name == ANCHOR_FILE.name:
                continue
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            chunks = [txt[j:j + CHUNK_CHARS] for j in range(0, len(txt), CHUNK_CHARS)] \\
                or [""]
            chunks = chunks[:MAX_CHUNKS_PER_FILE]
            for k, ch in enumerate(chunks, 1):
                items.append({
                    "id": f"L{i}-{k}" if len(chunks) > 1 else f"L{i}",
                    "claim": ch.strip()[:400],
                    "content": ch,
                    "source": p.name,
                    "part": k,
                    "parts": len(chunks),
                    "kind": "local",
                    "tier": 2,
                })'''

IMPORT_OLD = '''def import_files(files: list[dict]) -> dict:
    """导入本地文件：存原文 + 重建合并锚点快照。files=[{name, content}]。"""
    ANCHORS_DIR.mkdir(exist_ok=True)
    saved, skipped = [], []
    for f in files or []:
        n = Path(str((f or {}).get("name") or "")).name
        if not n or n == ANCHOR_FILE.name:
            skipped.append(n or "(无名)")
            continue
        try:
            (ANCHORS_DIR / n).write_text(str((f or {}).get("content") or ""),
                                         encoding="utf-8", newline="")
            saved.append(n)
        except OSError:
            skipped.append(n)
    _rebuild_anchor()
    return {
        "saved": saved,
        "skipped": skipped,
        "anchor_file": str(ANCHOR_FILE.relative_to(oi.PROJECT_ROOT)).replace("\\\\", "/"),
    }'''

IMPORT_NEW = '''def _decode_entry(f: dict) -> tuple[bytes, str]:
    """把一条入参还原成**原始字节**。

    两种形态都收：
      · `{name, b64}`   ← 前端现在这么发（二进制安全，PDF / 图片必须走这条）
      · `{name, content}` ← 老的文本入参（`selftest.py` 在用，保持兼容）
    """
    if isinstance(f.get("b64"), str) and f["b64"]:
        return base64.b64decode(f["b64"], validate=False), ""
    if isinstance(f.get("content"), str):
        return f["content"].encode("utf-8"), ""
    return b"", "既没给 b64 也没给 content"


def import_files(files: list[dict]) -> dict:
    """导入本地资料：**解析成文本** → 存进锚点目录 → 重建合并快照。

    参数：`files=[{name, b64} | {name, content}, …]`（见 `_decode_entry`）。
    返回：`{saved, skipped, results, anchor_file}` ——
      `saved/skipped` 是老字段（兼容），`results` 是**逐文件**的明细：
      `{name, ok, kind, chars, error, saved_as}`（失败也留痕，绝不静默）。

    ★ 上限：单次 ≤ `MAX_FILES` 个、单文件 ≤ `MAX_FILE_BYTES`（100MB）。
    ★ 原始文件一律留档到 `anchors/_raw/`：解析失败时**原件还在**，用户能换工具再试。
    ★ 纯文本类直接按原名存（人看着舒服）；富格式存 `<原名>.txt`（解析稿）+ `_raw/<原名>`。
    """
    ANCHORS_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)
    saved: list[str] = []
    skipped: list[str] = []
    results: list[dict] = []

    for f in (files or [])[:MAX_FILES]:
        f = f or {}
        n = Path(str(f.get("name") or "")).name
        if not n or n == ANCHOR_FILE.name or n.startswith("."):
            skipped.append(n or "(无名)")
            results.append({"name": n or "(无名)", "ok": False, "kind": "", "chars": 0,
                            "error": "文件名非法", "saved_as": ""})
            continue
        data, why = _decode_entry(f)
        if why:
            skipped.append(n)
            results.append({"name": n, "ok": False, "kind": "", "chars": 0,
                            "error": why, "saved_as": ""})
            continue
        if len(data) > MAX_FILE_BYTES:
            skipped.append(n)
            results.append({"name": n, "ok": False, "kind": "", "chars": 0,
                            "error": "文件 %.1fMB 超过单文件上限 100MB"
                                     % (len(data) / 1048576.0), "saved_as": ""})
            continue

        ext = Path(n).suffix.lower()
        textish = ext in docparse.TEXT_EXT or not ext
        parsed = docparse.extract(n, data)
        # 原件留档（解析失败也留 —— 「失败留痕」且可回退）
        try:
            (RAW_DIR / n).write_bytes(data)
        except OSError:
            pass
        if not parsed["ok"]:
            skipped.append(n)
            results.append({"name": n, "ok": False, "kind": parsed["kind"],
                            "chars": 0, "error": parsed["error"],
                            "saved_as": ""})
            continue
        saved_as = n if textish else n + ".txt"
        try:
            (ANCHORS_DIR / saved_as).write_text(parsed["text"], encoding="utf-8",
                                                newline="")
        except OSError as e:
            skipped.append(n)
            results.append({"name": n, "ok": False, "kind": parsed["kind"], "chars": 0,
                            "error": "写盘失败：%s" % e, "saved_as": ""})
            continue
        saved.append(saved_as)
        results.append({"name": n, "ok": True, "kind": parsed["kind"],
                        "chars": parsed["chars"], "error": "",
                        "saved_as": saved_as})

    _rebuild_anchor()
    return {
        "saved": saved,
        "skipped": skipped,
        "results": results,
        "limits": {"max_files": MAX_FILES, "max_file_mb": 100},
        "anchor_file": str(ANCHOR_FILE.relative_to(oi.PROJECT_ROOT)).replace("\\\\", "/"),
    }'''


def read_lf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r") == 0, "%s 不是纯 LF" % p.name
    return b.decode("utf-8")


def write_lf(p: Path, s: str) -> None:
    b = s.encode("utf-8")
    assert b.count(b"\r") == 0
    p.write_bytes(b)


def main() -> int:
    s = read_lf(LIB)
    for old, new, what in [
        (IMP_OLD, IMP_NEW, "① 引入 base64 / docparse"),
        (CONST_ANCHOR, CONST_NEW, "② 上限常量 + `_raw` 留档目录"),
        (REBUILD_OLD, REBUILD_NEW, "③ 锚点重建：长文档分块"),
        (IMPORT_OLD, IMPORT_NEW, "④ 导入主流程：b64 + 解析 + 上限 + 逐文件结果"),
    ]:
        if new in s:
            print("  · %s：已是新版，跳过" % what)
            continue
        n = s.count(old)
        assert n == 1, "%s：旧块命中 %d 次（要求 1）" % (what, n)
        s = s.replace(old, new)
        print("  ✓ %s" % what)
    write_lf(LIB, s)

    s2 = read_lf(LIB)
    ast.parse(s2)
    bad = []
    for k in ("import base64", "import docparse", "RAW_DIR = ANCHORS_DIR", "MAX_FILES = 50",
              "MAX_FILE_BYTES = 100 * 1024 * 1024", "def _decode_entry(", "CHUNK_CHARS = 2000"):
        if k not in s2:
            bad.append("缺：" + k)
    if '"part": k,' not in s2:
        bad.append("锚点没分块")
    if "old2 = " in s2:
        bad.append("有残留占位")
    if bad:
        print("★ 自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("  ✓ 自检：AST 通过 / b64+content 双入参 / 上限 / 分块 / _raw 留档 都在")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

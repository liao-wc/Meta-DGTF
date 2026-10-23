#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R44 的 selftest 判据（6 条里 1~6 全都有份；解析器的**行为**判据在 `_r44_parse.py` 里）。

抽成模块级 `check_r44_frontend(app_dir, css, js, html, srv_src)` —— 变异体可直接喂坏输入驱动。
`selftest.py` 纯 CRLF。

    python _mk_r44_selftest.py
"""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "dgtf_app" / "selftest.py"

DEF_ANCHOR = "def main() -> int:\n    ap = argparse.ArgumentParser()"
CALL_ANCHOR = "    # ── 参数往返：列表型键不能被写成字符串 ─────────────────────────"
DEFLINE = ("def check_r44_frontend(css: str, js: str, html: str, srv_src: str,\n"
           "                       lib_src: str, dp_src: str) -> None:")

BODY = '''    """★R44 的界面 / 导入判据（用户 6 图 / 6 条）。"""

    _lib, _dp = lib_src or "", dp_src or ""

    # ── ① 读数台实时更新 ────────────────────────────────────────────────────
    check("★R44 读数台**自动刷新**（5s 一轮，且只在「读数台」这页可见时拉）",
          "setInterval(() => {" in js and "classList.contains('active')" in js
          and "loadDash();" in js and "5000" in js, "")
    check("★R44 切到「读数台」时**立刻**拉一次（不等下一个周期）",
          "if (key === 'dash-stats') loadDash();" in js, "")

    # ── ② 点对话框 / 发送键 / 首屏空白 ⇒ 抽屉自动收起 ──────────────────────
    check("★R44 点**对话框**（含胶囊 / 回形针 / 发送键）⇒ 收起抽屉",
          "document.body.classList.contains('drawer-open')" in js
          and "e.target.closest('.composer')" in js and "closeDrawer();" in js, "")
    check("★R44 点**首屏空白区**也收起（只在空态判定，不动运行态）",
          "stage-empty" in js and "e.target.closest('main.stage')" in js, "")

    # ── ③ 首屏文案 + 字号 ───────────────────────────────────────────────────
    _ph = "此刻 你又想到了什么？ 可以发给元DGTF 我们一起去探索吧"
    check("★R44 首屏文案两处同步（index.html 的 placeholder + app.js 的 Q_PLACEHOLDER）",
          _ph in html and _ph in js, "")
    check("★R44 输入框字号**调小一档**（≤14px）",
          re.search(r"font-size:\\s*(1[0-4](\\.\\d+)?)px", _rule(css, "textarea#question")) is not None,
          (_rule(css, "textarea#question") or "").strip()[:48])

    # ── ④ 首屏不出现滚动点 ──────────────────────────────────────────────────
    check("★R44 `updateRlBar()` 里判「日志窗口自己是否可见」（隐藏就一律不画点）",
          "_box.classList.contains('hidden')" in js
          and "const _box = $('#runlog');" in js, "")
    check("★R44 空态那条**早返回**路径也会收一次点（否则点会留在上次的位置）",
          "updateRlBar();   // ★ R44" in js, "")

    # ── ⑥ 首屏以对话框为基准居中 + 上移 ────────────────────────────────────
    check("★R44 首屏以**对话框**为基准居中并整体上移（下内边距顶高一半）",
          "padding-bottom:calc(20px + 88px)" in css, "")

    # ── ⑤ 导入：前端管线 ────────────────────────────────────────────────────
    check("★R44 导入控件是**真按钮**点隐藏 input（不再靠 label 转发）",
          'id="anchor-pick"' in html
          and "if (_ap && _af) _ap.addEventListener('click', () => _af.click());" in js
          and '<label class="chk"><input type="file"' not in html, "")
    check("★R44 前端按**字节**读（`ArrayBuffer` + base64），不再 `File.text()`",
          "function fileToB64(" in js and "readAsArrayBuffer" in js and "btoa(s)" in js
          and "content: await f.text()" not in js, "")
    check("★R44 前端有上限与分批（50 个 / 单文件 100MB / 每批 48MB）",
          "LIB_MAX_FILES = 50, LIB_MAX_MB = 100" in js and "LIB_BATCH_MB = 48" in js
          and "超过单文件上限" in js, "")
    check("★R44 逐文件结果摆出来（成功 / 失败原因），不再「点了没反应」",
          "function importPaint(" in js and ".import-detail" in css
          and "r.results" in js and "importRows" in js, "")

    # ── ⑤ 导入：服务端上限 + 解析 + 留档 ────────────────────────────────────
    check("★R44 服务端上限：单次 50 个 / 单文件 100MB",
          "MAX_FILES = 50" in _lib and "MAX_FILE_BYTES = 100 * 1024 * 1024" in _lib, "")
    check("★R44 上传体积闸（超过就 413，别把内存吃光）",
          "MAX_UPLOAD_BYTES" in srv_src and "413" in srv_src, "")
    check("★R44 入参**双形态**：`{name,b64}`（二进制）与 `{name,content}`（老的文本）都收",
          "def _decode_entry(" in _lib and 'f.get("b64")' in _lib
          and 'f.get("content")' in _lib, "")
    check("★R44 原始文件留档 `anchors/_raw/`（解析失败也不丢原件）",
          "RAW_DIR = ANCHORS_DIR" in _lib and "(RAW_DIR / n).write_bytes(data)" in _lib, "")
    check("★R44 删除时**原件一起删**（不留孤儿）",
          "_extras = [RAW_DIR / n]" in _lib, "")
    check("★R44 长文档**分块**进锚点（原来只取前 2000 字）",
          "CHUNK_CHARS = 2000" in _lib and '"part": k,' in _lib
          and "chunks[:MAX_CHUNKS_PER_FILE]" in _lib, "")
    check("★R44 解析器只依赖标准库（本机没有 pypdf/python-docx/PIL/tesseract）",
          _dp != "" and "import zipfile" in _dp and "import zlib" in _dp
          and not re.search(r"^import (pypdf|PyPDF2|docx|openpyxl|pptx|fitz|PIL|pytesseract)",
                            _dp, re.M), "")
    check("★R44 解析器覆盖 docx/xlsx/pptx/pdf/图片/OLE/纯文本",
          all(k in _dp for k in ("def parse_docx", "def parse_xlsx", "def parse_pptx",
                                 "def parse_pdf", "def parse_image", "def parse_ole")), "")
    check("★R44 解析失败**不静默**：返回 ok=False + 原因（不抛异常）",
          '"ok": False' in _dp and 'return {"ok": False' in _dp, "")
'''


def read_crlf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") == b.count(b"\r"), "%s 不是纯 CRLF" % p.name
    return b.decode("utf-8")


def write_crlf(p: Path, s: str) -> None:
    b = s.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    assert b.count(b"\r\r\n") == 0 and b.count(b"\r") == b.count(b"\r\n")
    p.write_bytes(b)


def main() -> int:
    cur = read_crlf(ST).replace("\r\n", "\n")
    if DEFLINE in cur:
        print("  · R44 判据函数已存在，跳过")
    else:
        assert cur.count(DEF_ANCHOR) == 1, "函数锚点命中 %d 次" % cur.count(DEF_ANCHOR)
        block = DEFLINE + "\n" + BODY + "\n\n"
        ast.parse(block)
        cur = cur.replace(DEF_ANCHOR, block + DEF_ANCHOR)
        assert cur.count(CALL_ANCHOR) == 1, "调用锚点命中 %d 次" % cur.count(CALL_ANCHOR)
        cur = cur.replace(CALL_ANCHOR,
                          "    check_r44_frontend(css, js, html, srv_src, lib_src, dp_src)\n"
                          + CALL_ANCHOR)
        print("  ✓ 注入 `check_r44_frontend`（定义 + 调用）")
    write_crlf(ST, cur)

    back = read_crlf(ST).replace("\r\n", "\n")
    ast.parse(back)
    n = back.count('check("★R44')
    assert n == 22, "★R44 判据 %d 条（期望 22）" % n
    assert back.count("check_r44_frontend(css, js, html, srv_src, lib_src, dp_src)") == 1
    # ★ 注意：R43（启动横幅）**没有**源码判据 —— 那几条判据在
    #   `_audit_tmp/_r42_lan.py` 的 E 组里直接读**真实 stdout 横幅**，所以这里不查 ★R43。
    for keep in ('check("★R42', 'check("★R41', 'check("★R40', 'check("★R39'):
        assert keep in back, "老判据不该被抹：" + keep
    print("  ✓ 自检：AST 通过 / ★R44 判据 %d 条 / 调用 1 处 / R39-R43 判据仍在" % n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

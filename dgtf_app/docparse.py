# -*- coding: utf-8 -*-
"""元DGTF 应用层 · 本地资料**格式解析**（纯标准库）。

给「本地资料库」用：把用户拖进来的文档 / 表格 / 演示 / 图片 / PDF 里的**文字**抠出来，
变成运行时可读入的锚点文本（见 `library._rebuild_anchor`）。

★ 本机没有 `pypdf` / `python-docx` / `openpyxl` / `PIL` / `tesseract`（实测全无），
  所以这里**只依赖标准库**，并且对做不到的事**明说**：
    · `docx / xlsx / pptx` 本身是 zip + XML ⇒ 能完整抠（这三类是最好的）
    · `pdf` ⇒ 尽力而为：解 FlateDecode 流 + 抽 `Tj/TJ` 文本算子；
              字体是 CID/子集编码时抠出来可能是乱码 ⇒ 用「可打印字符占比」判一下，
              不行就**如实报错**，不塞垃圾进锚点。
    · 图片 ⇒ 本机**无 OCR**：抠尺寸 + 图里内嵌的文字块（PNG tEXt/iTXt、JPEG EXIF、GIF 注释）；
              允许挂一个外部 OCR：`.env` 里 `DGTF_OCR_CMD=tesseract {path} stdout -l chi_sim+eng`
              （命令模板，`{path}` 会被替换）。
    · `.doc/.xls/.ppt`（老的 OLE 二进制）⇒ 尽力而为：抽可读的 UTF-16LE / GBK 文本段，**可能不全**。

对外只有一个入口：`extract(name, data) -> dict`。
"""

from __future__ import annotations

import re
import shlex
import shutil
import struct
import subprocess
import tempfile
import zlib
import zipfile
from pathlib import Path

# ── 分类 ────────────────────────────────────────────────────────────────────
TEXT_EXT = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml",
    ".py", ".js", ".mjs", ".ts", ".tsx", ".jsx", ".css", ".scss", ".html", ".htm",
    ".xml", ".toml", ".ini", ".cfg", ".conf", ".log", ".sql", ".sh", ".bat", ".ps1",
    ".c", ".h", ".cpp", ".hpp", ".java", ".go", ".rs", ".rb", ".php", ".vue", ".srt",
}
ZIP_DOC_EXT = {".docx": "docx", ".xlsx": "xlsx", ".pptx": "pptx",
               ".docm": "docx", ".xlsm": "xlsx", ".pptm": "pptx"}
OLE_EXT = {".doc", ".xls", ".ppt"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
PDF_EXT = {".pdf"}

MAX_CHARS = 4_000_000          # 单个文件最多留这么多字（防超长日志撑爆锚点）
MIN_GOOD_RATIO = 0.55          # PDF 抠出来的「可打印占比」低于此值就判失败


# ── 文本解码 ────────────────────────────────────────────────────────────────
def decode_text(data: bytes) -> str:
    """按 BOM → UTF-8 → GB18030 → Latin-1 的顺序解码（中文资料里 GBK 很常见）。"""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16")
        except UnicodeError:
            pass
    if data[:3] == b"\xef\xbb\xbf":
        return data[3:].decode("utf-8", "replace")
    for enc in ("utf-8", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", "replace")


def _printable_ratio(s: str) -> float:
    if not s:
        return 0.0
    ok = sum(1 for c in s if c.isprintable() or c in "\n\t ")
    return ok / len(s)


def _clean(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{4,}", "\n\n\n", s)
    return s.strip()[:MAX_CHARS]


# ── zip 型文档（docx / xlsx / pptx）─────────────────────────────────────────
def _xml_text(xml: bytes) -> str:
    """把一段 OOXML 里的文字抠出来：段落 <w:p>/<a:p> 之间换行，其余标签去掉。"""
    s = xml.decode("utf-8", "replace")
    s = re.sub(r"<(?:w|a):(?:br|cr)\s*/>", "\n", s)              # 手动换行
    s = re.sub(r"</(?:w|a):p>", "\n", s)                        # 段落结束
    s = re.sub(r"</(?:w|a):tr>", "\n", s)                       # 表格行
    s = re.sub(r"</(?:w|a):tc>", "\t", s)                       # 单元格
    s = re.sub(r"<[^>]+>", "", s)                               # 其余标签
    s = (s.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
          .replace("&apos;", "'").replace("&amp;", "&"))
    return s


def parse_docx(data: bytes) -> tuple[str, str]:
    with zipfile.ZipFile(_bio(data)) as z:
        names = [n for n in z.namelist()
                 if re.fullmatch(r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml", n)]
        if "word/document.xml" not in names:
            raise ValueError("zip 里没有 word/document.xml（不是 docx？）")
        parts = [_xml_text(z.read(n)) for n in sorted(names)]
    return _clean("\n".join(parts)), "docx（段落 / 表格文本）"


def parse_xlsx(data: bytes) -> tuple[str, str]:
    with zipfile.ZipFile(_bio(data)) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
            for si in re.findall(r"<si>(.*?)</si>", sst, re.S):
                shared.append(re.sub(r"<[^>]+>", "", si))
        sheets = sorted(n for n in z.namelist()
                        if re.fullmatch(r"xl/worksheets/sheet\d*\.xml", n))
        out: list[str] = []
        for name in sheets:
            xml = z.read(name).decode("utf-8", "replace")
            out.append(f"【{Path(name).stem}】")
            for row in re.findall(r"<row[^>]*>(.*?)</row>", xml, re.S):
                cells = []
                # ★ 必须把 `<c …>` 的**属性**一起拿到：共享串标记 `t="s"` 在属性里，
                #   只取标签之间的内容会拿到索引数字（第一版就是这么把单元格读成 0/1/2 的）。
                for cxml in re.findall(r"<c\b[^>]*>.*?</c>|<c\b[^>]*/>", row, re.S):
                    attrs = cxml[:cxml.find(">") + 1]
                    tm = re.search(r't="([^"]+)"', attrs)
                    vt = re.search(r"<v>(.*?)</v>", cxml, re.S)
                    if tm and tm.group(1) == "s" and vt and vt.group(1).strip().isdigit():
                        idx = int(vt.group(1))
                        cells.append(shared[idx] if idx < len(shared) else "")
                    elif tm and tm.group(1) == "inlineStr":
                        cells.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", cxml, re.S)))
                    elif vt:
                        cells.append(vt.group(1))
                    else:
                        cells.append("")
                out.append("\t".join(x.strip() for x in cells))
    return _clean("\n".join(out)), "xlsx（按行制表符分隔）"


def parse_pptx(data: bytes) -> tuple[str, str]:
    with zipfile.ZipFile(_bio(data)) as z:
        slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                        key=lambda s: int(re.findall(r"\d+", Path(s).stem)[0]))
        out = []
        for i, n in enumerate(slides, 1):
            out.append(f"【第 {i} 页】")
            out.append(_xml_text(z.read(n)))
    return _clean("\n".join(out)), "pptx（按页）"


def _bio(data: bytes):
    import io
    return io.BytesIO(data)


# ── PDF（尽力而为）──────────────────────────────────────────────────────────
_PDF_STR = re.compile(rb"\((?:\\.|[^\\()])*\)")


def _pdf_unescape(b: bytes) -> str:
    s = b[1:-1]
    s = re.sub(rb"\\([nrtbf()\\])", lambda m: {b"n": b"\n", b"r": b"\r", b"t": b"\t",
                                               b"b": b"\b", b"f": b"\f"}.get(m.group(1), m.group(1)), s)
    s = re.sub(rb"\\([0-7]{1,3})", lambda m: bytes([int(m.group(1), 8) & 0xFF]), s)
    return s.decode("latin-1", "replace")


def parse_pdf(data: bytes) -> tuple[str, str]:
    chunks: list[str] = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        raw = data[start:end]
        if raw.endswith(b"\r\n"):
            raw = raw[:-2]
        elif raw.endswith(b"\n"):
            raw = raw[:-1]
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass                              # 没压缩 / 别的滤镜：就当明文试试
        body = []
        for tm in re.finditer(rb"((?:\((?:\\.|[^\\()])*\)\s*)|(?:\[[^\]]*\]\s*TJ)|(?:T\*)|(?:Td|TD|ET|BT))",
                              raw):
            tok = tm.group(1)
            if tok in (b"T*", b"Td", b"TD", b"ET"):
                body.append("\n")
            elif tok.endswith(b"TJ"):
                inner = re.findall(rb"\((?:\\.|[^\\()])*\)", tok)
                body.append("".join(_pdf_unescape(x) for x in inner))
            else:
                body.append(_pdf_unescape(tok.rstrip()))
            body.append(" ")
        if body:
            chunks.append("".join(body))
    text = _clean("\n".join(chunks))
    ratio = _printable_ratio(text)
    if len(text) < 40 or ratio < MIN_GOOD_RATIO:
        raise ValueError(
            "PDF 里没抠出可读文本（可打印占比 %.0f%%，%d 字）——"
            "多半是扫描件或 CID 子集字体，本机无 OCR，请另存为文本 / 截图后用外部工具转换"
            % (ratio * 100, len(text)))
    return text, "pdf（抽取文本层，可能不含排版）"


# ── 图片 ────────────────────────────────────────────────────────────────────
def _png_info(data: bytes) -> tuple[str, list[str]]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG")
    w, h = struct.unpack(">II", data[16:24])
    texts = []
    i = 8
    while i + 8 <= len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        payload = data[i + 8:i + 8 + ln]
        if typ in (b"tEXt", b"iTXt", b"zTXt") and payload:
            txt = payload.replace(b"\x00", b": ").decode("utf-8", "replace")
            texts.append(txt.strip())
        if typ == b"IEND":
            break
        i += 12 + ln
    return f"{w}x{h}", texts


def _jpeg_info(data: bytes) -> tuple[str, list[str]]:
    if data[:2] != b"\xff\xd8":
        raise ValueError("不是 JPEG")
    i, w, h, texts = 2, 0, 0, []
    while i + 4 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        ln = struct.unpack(">H", data[i + 2:i + 4])[0]
        seg = data[i + 4:i + 2 + ln]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            h, w = struct.unpack(">HH", seg[1:5])
        if marker == 0xFE:                                  # 注释段
            texts.append(seg.decode("utf-8", "replace").strip())
        if marker == 0xE1 and seg[:6] == b"Exif\x00\x00":     # EXIF：抽里面的可读字符串
            txt = re.findall(rb"[\x20-\x7e]{6,}", seg)
            texts += [t.decode("ascii", "replace").strip() for t in txt]
        i += 2 + ln
    return f"{w}x{h}", texts


def _gif_info(data: bytes) -> tuple[str, list[str]]:
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("不是 GIF")
    w, h = struct.unpack("<HH", data[6:10])
    texts = []
    for m in re.finditer(rb"\x21\xfe(.)(.*?)\x00", data, re.S):
        try:
            texts.append(m.group(2)[:m.group(1)[0]].decode("utf-8", "replace").strip())
        except Exception:  # noqa: BLE001
            pass
    return f"{w}x{h}", texts


def _external_ocr(path: Path) -> str:
    """`.env` 里配了 `DGTF_OCR_CMD` 就能用外部 OCR（模板里 `{path}` 会替换成临时文件路径）。"""
    import os
    tpl = os.environ.get("DGTF_OCR_CMD", "").strip()
    if not tpl:
        return ""
    cmd = [c.replace("{path}", str(path)) for c in shlex.split(tpl)]
    if not shutil.which(cmd[0]):
        return ""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "replace").strip()
    except Exception:  # noqa: BLE001
        return ""


def parse_image(name: str, data: bytes) -> tuple[str, str]:
    ext = Path(name).suffix.lower()
    info, texts = "", []
    try:
        if ext == ".png":
            info, texts = _png_info(data)
        elif ext in (".jpg", ".jpeg"):
            info, texts = _jpeg_info(data)
        elif ext == ".gif":
            info, texts = _gif_info(data)
    except Exception:  # noqa: BLE001
        info, texts = "", []
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(data)
        tmp = Path(f.name)
    try:
        ocr = _external_ocr(tmp)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    head = f"［图片 {name}］尺寸 {info or '未知'}，{len(data)} 字节。"
    if ocr:
        return _clean(head + "\n" + ocr), "图片（外部 OCR 识别）"
    if texts:
        return _clean(head + "\n图内文字块：" + "\n".join(t for t in texts if t)), \
            "图片（抽取内嵌文字块）"
    return _clean(head + "\n（本机没装 OCR：正文未抽取；如需识别，"
                          "在 .env 里配 DGTF_OCR_CMD 指定一个命令行 OCR）"), \
        "图片（仅元信息：本机无 OCR）"


# ── OLE 老格式（.doc/.xls/.ppt）：尽力而为 ─────────────────────────────────
_OLE_SCAN_LIMIT = 8 * 1024 * 1024       # 只扫前 8MB（够抽正文，且不会被大文件拖死）


def _utf16_runs(data: bytes, limit: int) -> list[str]:
    """按 UTF-16LE **逐 2 字节**扫出可读串（小端：低字节在前，高字节在后）。

    ★ 不能只找「隔一个 0 字节」的那种：那只能命中 ASCII / 拉丁字母；
      中文的 UTF-16LE 是 `\\x87\\x65` 这种**两个字节都非 0** 的，得按码位判。
      判据：可打印，且落在 ASCII / 中日韩 / 全角标点这些范围里。
    """
    runs: list[str] = []
    i = 0
    n = min(len(data) - 1, limit)
    while i < n:
        j, buf = i, []
        while j < n:
            ch = data[j] | (data[j + 1] << 8)
            if ch < 128 or 0x2E80 <= ch <= 0x9FFF or 0x3000 <= ch <= 0x303F \
                    or 0xFF00 <= ch <= 0xFFEF or ch in (0x2018, 0x2019, 0x201C, 0x201D):
                buf.append(chr(ch))
                j += 2
            else:
                break
        if len(buf) >= 4:
            runs.append("".join(buf))
            i = j
        else:
            i += 1
    return runs


def parse_ole(name: str, data: bytes) -> tuple[str, str]:
    runs: list[str] = []
    runs += _utf16_runs(data, _OLE_SCAN_LIMIT)
    for m in re.finditer(rb"[\x20-\x7e]{6,}", data[:_OLE_SCAN_LIMIT]):     # 普通 ASCII 串
        runs.append(m.group(0).decode("ascii", "replace"))
    text = _clean("\n".join(dict.fromkeys(runs)))
    if len(text) < 20:
        raise ValueError("%s 是老的 OLE 二进制格式，本机没有解析器，"
                         "也抽不到可读文本段；请另存为 .docx / .xlsx / .pptx 再导入"
                         % Path(name).suffix)
    return text, "OLE 二进制（尽力而为，可能不全）"


# ── 对外入口 ────────────────────────────────────────────────────────────────
def extract(name: str, data: bytes) -> dict:
    """把一份文件解析成可读文本。

    → {"ok": bool, "text": str, "kind": str, "chars": int, "error": str}
    **不抛异常**：解析失败也返回字典（失败留痕，交给上层显示 / 落盘）。
    """
    ext = Path(name).suffix.lower()
    if not data:
        return {"ok": False, "text": "", "kind": "", "chars": 0, "error": "空文件"}
    try:
        if ext in TEXT_EXT or (not ext and _printable_ratio(decode_text(data[:4096])) > 0.9):
            return _wrap(decode_text(data), "纯文本")
        if ext in ZIP_DOC_EXT:
            fn = {"docx": parse_docx, "xlsx": parse_xlsx, "pptx": parse_pptx}[ZIP_DOC_EXT[ext]]
            return _wrap(*fn(data))
        if ext in PDF_EXT:
            return _wrap(*parse_pdf(data))
        if ext in IMAGE_EXT:
            return _wrap(*parse_image(name, data))
        if ext in OLE_EXT:
            return _wrap(*parse_ole(name, data))
        if ext in (".zip", ".7z", ".rar", ".gz", ".tar"):
            return {"ok": False, "text": "", "kind": "压缩包", "chars": 0,
                    "error": "压缩包不解析（请解压后逐个导入）"}
        # 未知后缀：先当文本试试，不行就明确说
        txt = decode_text(data)
        if _printable_ratio(txt) >= 0.9:
            return _wrap(txt, "纯文本（按文本读）")
        return {"ok": False, "text": "", "kind": "未知", "chars": 0,
                "error": "认不出这个格式（本机只有标准库；文档请用 "
                         "docx/xlsx/pptx/pdf，图片请用 png/jpg/gif）"}
    except zipfile.BadZipFile:
        return {"ok": False, "text": "", "kind": "损坏", "chars": 0,
                "error": "文件不是有效的 zip/OOXML（可能没下完或已损坏）"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "text": "", "kind": "", "chars": 0,
                "error": "%s: %s" % (type(e).__name__, e)}


def _wrap(text: str, kind: str) -> dict:
    text = _clean(text)
    if not text:
        return {"ok": False, "text": "", "kind": kind, "chars": 0, "error": "解析出来是空的"}
    return {"ok": True, "text": text, "kind": kind, "chars": len(text), "error": ""}

# -*- coding: utf-8 -*-
import subprocess
from pathlib import Path
p = Path("dgtf_app/static/app.js")
cur = p.read_bytes()
orig = subprocess.check_output(["git", "show", "HEAD:dgtf_app/static/app.js"])
print("orig crlf", b"\r\n" in orig, "cur crlf", b"\r\n" in cur,
      "orig bytes", len(orig), "cur bytes", len(cur))
if (b"\r\n" in orig) and (b"\r\n" not in cur):
    p.write_bytes(cur.replace(b"\n", b"\r\n"))
    print("converted to CRLF, bytes", p.stat().st_size)
t = p.read_text(encoding="utf-8")
print("safeUrl", "const safeUrl" in t, "used", "safeUrl(h.url)" in t)

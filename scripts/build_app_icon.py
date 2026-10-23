#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把用户桌面快捷方式的 256px 图标 PNG 打包成 dgtf.ico（无第三方依赖）。"""
from pathlib import Path
import struct
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / 'dgtf_app' / 'static'
png = (STATIC / 'desktop-icon-256.png').read_bytes()
if not png.startswith(b'\x89PNG\r\n\x1a\n'):
    raise SystemExit('desktop-icon-256.png is not a PNG')
ico = struct.pack('<HHH', 0, 1, 1)
ico += struct.pack('<BBBBHHII', 0, 0, 0, 0, 1, 32, len(png), 22)
ico += png
(STATIC / 'dgtf.ico').write_bytes(ico)
print('WROTE', STATIC / 'dgtf.ico', len(ico), 'bytes')

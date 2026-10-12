#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R42 的 selftest 判据：**默认不暴露 / `--lan` 才暴露 / 口令真的挡得住**。

行为层由 `_audit_tmp/_r42_lan.py`（真起服务 + 真 HTTP）负责；
这里补**源码/接口层**的几条，好让「以后谁把默认地址改了 / 把闸拆了」当场翻红。

判据抽成模块级 `check_r42_server(srv_src)`（变异体可直接喂坏源码驱动），由 `main()` 调一次。

`selftest.py` 纯 CRLF。

    python _mk_r42_selftest.py
"""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
ST = HERE / "dgtf_app" / "selftest.py"

DEF_ANCHOR = "def main() -> int:\n    ap = argparse.ArgumentParser()"
CALL_ANCHOR = "    # ── 参数往返：列表型键不能被写成字符串 ─────────────────────────"
DEFLINE = "def check_r42_server(srv_src: str) -> None:"

BODY = '''    """★R42：局域网访问（`--lan`）与访问口令（`--token`）—— 默认必须**不暴露**。"""

    check("★R42 默认仍**只监听 127.0.0.1**（`--host` 的默认值没被改掉）",
          'ap.add_argument("--host", default="127.0.0.1"' in srv_src, "")
    check("★R42 `--lan` ⇒ 绑 `0.0.0.0`（语义化写法，不是让用户自己记 IP）",
          'ap.add_argument("--lan", action="store_true"' in srv_src
          and 'host = "0.0.0.0" if args.lan else args.host' in srv_src, "")
    check("★R42 启动时**打印局域网网址**（自己探本机内网 IP，省得去 ipconfig）",
          "def lan_ipv4()" in srv_src and "局域网已打开" in srv_src
          and "socket.AF_INET" in srv_src, "")
    check("★R42 口令闸在 `do_GET` / `do_POST` **各一处**（两处都不漏）",
          srv_src.count("if not self._guard():") == 2
          and "def _guard(self)" in srv_src, "")
    check("★R42 口令**默认为空即全放行** ⇒ 不改默认行为（只在 `--token` 时生效）",
          '_TOKEN = ""' in srv_src
          and 'if not _TOKEN:\\n            return True' in srv_src, "")
    check("★R42 首次带 `?t=` 进来就**种 cookie**（手机上存书签即可，不用做登录页）",
          "dgtf_token=" in srv_src and "SameSite=Lax" in srv_src
          and srv_src.count("self._auth_note()") >= 4 - 1   # 1 定义 + 3 个响应助手
          , "auth_note 出现 " + str(srv_src.count("self._auth_note()")) + " 次")
    check("★R42 口令太短**拒绝启动**（不留一个没保护的监听）",
          "口令太短" in srv_src and "return 2" in srv_src, "")
    check("★R42 抽 `make_server()`：验收能在**同一个进程**里起服务（sandbox 会清子进程）",
          "def make_server(" in srv_src
          and "srv = make_server(host, args.port, token=token" in srv_src, "")
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
        print("  · R42 判据函数已存在，跳过")
    else:
        assert cur.count(DEF_ANCHOR) == 1, "函数锚点命中 %d 次" % cur.count(DEF_ANCHOR)
        block = DEFLINE + "\n" + BODY + "\n\n"
        ast.parse(block)
        cur = cur.replace(DEF_ANCHOR, block + DEF_ANCHOR)
        assert cur.count(CALL_ANCHOR) == 1, "调用锚点命中 %d 次" % cur.count(CALL_ANCHOR)
        cur = cur.replace(CALL_ANCHOR, "    check_r42_server(srv_src)\n" + CALL_ANCHOR)
        print("  ✓ 注入 `check_r42_server`（定义 + 调用）")
    write_crlf(ST, cur)

    back = read_crlf(ST).replace("\r\n", "\n")
    ast.parse(back)
    assert back.count('check("★R42') == 8, "★R42 判据 %d 条（期望 8）" % back.count('check("★R42')
    assert back.count("check_r42_server(srv_src)") == 1
    for keep in ('check("★R41', 'check("★R40', 'check("★R39'):
        assert keep in back, "老判据不该被抹：" + keep
    print("  ✓ 自检：AST 通过 / ★R42 判据 8 条 / 调用 1 处 / R39-R41 判据仍在")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

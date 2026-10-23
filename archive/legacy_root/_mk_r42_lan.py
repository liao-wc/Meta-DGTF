#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R42：把工作台放开到**同一局域网**（用户要求），并给一个可选的访问口令。

两件事：
  ① `--lan`  → 绑 `0.0.0.0`（默认仍是 `127.0.0.1`，**不动默认行为**），
     并在启动时打印「另一台设备该开哪个网址」（自己探测本机内网 IP，不用去 ipconfig）。
  ② `--token [口令]` → 开启后所有请求都要带 `?t=<口令>`；首次带口令进来就种 cookie，
     之后同源 fetch 自动带上 ⇒ 手机上只要把那条网址存成书签。
     默认**关闭**（一开 `--lan` 就等于把「跑任务花额度 / 删本地资料库」的能力交给同网段所有人）。

顺手把 `main()` 里的建服务抽成 `make_server(host, port, token, verbose)` ——
本机 sandbox 会在命令结束时清掉子进程，验收必须能在**同一个进程**里起服务。

`server.py` 是**纯 LF**。

    python _mk_r42_lan.py
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRV = HERE / "dgtf_app" / "server.py"

DOC_OLD = '"""元DGTF 应用层 · 本地 HTTP 服务（仅监听 127.0.0.1）。'
DOC_NEW = ('"""元DGTF 应用层 · 本地 HTTP 服务（默认只监听 127.0.0.1；`--lan` 放开到同一局域网）。')

USAGE_OLD = "启动： python dgtf_app/server.py [--port 8765] [--verbose]"
USAGE_NEW = """启动： python dgtf_app/server.py [--port 8765] [--verbose]
       python dgtf_app/server.py --lan                 # 同一局域网可访问（**无口令**，谁都能操作）
       python dgtf_app/server.py --lan --token 口令     # 带访问口令（启动时会打印带 ?t= 的网址）"""

IMP_OLD = "import os\nimport re\nimport sys"
IMP_NEW = "import os\nimport re\nimport secrets\nimport socket\nimport sys"

MOD_ANCHOR = '_FACETS = ("decidability", "orientation", "parallel", "stop", "kind", "layer")'
MOD_NEW = MOD_ANCHOR + '''


# ══ ★ R42：局域网访问（--lan）+ 可选访问口令（--token）═══════════════════════
# 默认仍然是**只监听 127.0.0.1**（最安全）；只有显式 `--lan` 才绑 0.0.0.0。
# 口令默认**关闭** —— 一开 `--lan`，同一网段里任何人都能跑任务（花 API 额度）、
# 删本地资料库导入的文件、翻全部产物。要收紧就 `--token <口令>`。
_TOKEN = ""


def lan_ipv4() -> list:
    """本机所有非回环 IPv4 —— 用来打印「另一台设备该开哪个网址」。

    不依赖外网：UDP `connect` 只让内核按路由表选一个出口地址，**不发包**。
    拿不到就退回 `getaddrinfo(hostname)`，再拿不到就返回空（调用方给占位提示）。
    """
    ips: list = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            ips.append(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips


def make_server(host: str, port: int, token: str = "", verbose: bool = False):
    """建好（**不启动**）服务。

    ★ 为什么抽出来：本机 sandbox 在命令结束时会把子进程全清掉 —— 验收只能在
      **同一个进程**里起服务（`_audit_tmp/_r42_lan.py` 就是这么用的）。
    """
    global _TOKEN
    _TOKEN = token
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.verbose = verbose
    srv.daemon_threads = True
    return srv'''

AUTH_ANCHOR = """    def _read_json(self) -> dict:"""
AUTH_NEW = '''    # ── ★ R42：访问口令（只在 `--token` 时生效；默认 _TOKEN 为空 ⇒ 全部放行）──
    def _auth_note(self):
        """首次带 `?t=<口令>` 进来时，把口令种进 cookie。

        之后同源 `fetch` 会自动带上 ⇒ **手机上只要把那条带口令的网址存成书签**，
        不用在界面里做登录页。`SameSite=Lax` 够用（本站全部同源）。
        """
        if not _TOKEN:
            return None
        q = parse_qs(urlparse(self.path).query)
        if q.get("t", [""])[0] == _TOKEN:
            return ("dgtf_token=%s; Path=/; SameSite=Lax; Max-Age=2592000"
                    % _TOKEN)
        return None

    def _granted(self) -> bool:
        if not _TOKEN:
            return True
        q = parse_qs(urlparse(self.path).query)
        if q.get("t", [""])[0] == _TOKEN:
            return True
        return ("dgtf_token=" + _TOKEN) in (self.headers.get("Cookie") or "")

    def _guard(self) -> bool:
        """口令闸：不通过就 401（**不泄露**任何业务信息）。"""
        if self._granted():
            return True
        self._json({"error": "未授权：本服务启用了访问口令，请用启动时打印的带 ?t= 的网址打开"}, 401)
        return False

    def _read_json(self) -> dict:'''

JSON_ANCHOR = """    def _json(self, obj, code: int = 200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")"""
JSON_NEW = """    def _json(self, obj, code: int = 200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        _ck = self._auth_note()
        if _ck:
            self.send_header("Set-Cookie", _ck)
        self.send_header("Content-Type", "application/json; charset=utf-8")"""

DL_ANCHOR = """        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        ascii_name = filename.encode("ascii", "ignore").decode() or "export\""""
DL_NEW = """        self.send_response(code)
        _ck = self._auth_note()
        if _ck:
            self.send_header("Set-Cookie", _ck)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        ascii_name = filename.encode("ascii", "ignore").decode() or "export\""""

ST_ANCHOR = """        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)"""
ST_NEW = """        data = target.read_bytes()
        self.send_response(200)
        _ck = self._auth_note()
        if _ck:
            self.send_header("Set-Cookie", _ck)
        self.send_header("Content-Type", ctype)"""

GET_ANCHOR = """    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)"""
GET_NEW = """    def do_GET(self):
        if not self._guard():          # ★ R42：口令开启时先过闸（默认关闭 ⇒ 恒真）
            return
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)"""

POST_ANCHOR = """    def do_POST(self):
        u = urlparse(self.path)
        p = u.path"""
POST_NEW = """    def do_POST(self):
        if not self._guard():          # ★ R42：口令开启时先过闸（默认关闭 ⇒ 恒真）
            return
        u = urlparse(self.path)
        p = u.path"""

MAIN_OLD = '''def main() -> int:
    ap = argparse.ArgumentParser(description="元DGTF 本地 Web 应用")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
'''

MAIN_NEW = '''def main() -> int:
    ap = argparse.ArgumentParser(description="元DGTF 本地 Web 应用")
    ap.add_argument("--host", default="127.0.0.1",
                    help="监听地址（默认只监听本机回环）")
    ap.add_argument("--lan", action="store_true",
                    help="绑 0.0.0.0：同一局域网内的其它设备也能访问（默认只监听 127.0.0.1）")
    ap.add_argument("--token", nargs="?", const="@gen", default="",
                    help="访问口令（不带值时自动生成）。开启后所有请求都要带它；"
                         "启动时会打印带 ?t= 的网址")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    # ★ R42：`--lan` 是 `--host 0.0.0.0` 的语义化写法；两者都给时以 `--lan` 为准。
    host = "0.0.0.0" if args.lan else args.host
    token = ""
    if args.token:
        token = args.token
        if token == "@gen":
            token = secrets.token_urlsafe(9)
        token = re.sub(r"[^A-Za-z0-9_-]", "", token)
        if len(token) < 6:
            print("口令太短（至少 6 位，只允许字母 / 数字 / _ / -）—— 换一个再试。")
            return 2
'''

MAIN_SRV_OLD = """    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.verbose = args.verbose
    srv.daemon_threads = True
    mock = "开" if os.environ.get("DGTF_APP_MOCK") == "1" else "关"
    print(f"元DGTF 应用已启动： http://{args.host}:{args.port}")
    print(f"  引擎：{runner.find_engine().name}")"""

MAIN_SRV_NEW = """    srv = make_server(host, args.port, token=token, verbose=args.verbose)
    mock = "开" if os.environ.get("DGTF_APP_MOCK") == "1" else "关"
    print(f"元DGTF 应用已启动： http://127.0.0.1:{args.port}")
    if host == "0.0.0.0":
        print("  局域网已打开（同一 WiFi / 同网段的设备可以访问）：")
        for _ip in (lan_ipv4() or ["<本机内网 IP，用 ipconfig 查>"]):
            print("    http://%s:%d%s" % (_ip, args.port,
                                          ("/?t=" + token) if token else ""))
        if not token:
            print("  ⚠ 没设口令：同一网络里任何人都能操作这个应用"
                  "（跑任务花 API 额度、删本地资料库导入的文件）。")
            print("    要收紧就加 `--token <你定的口令>`；只是临时用一下，用完 Ctrl+C 关掉即可。")
    else:
        print("  （只监听本机；要让同一局域网访问，加 --lan）")
    if token:
        print("  访问口令已启用：网址要带 ?t=<口令>（首次打开会自动记进 cookie）")
    print(f"  引擎：{runner.find_engine().name}")"""


def read_lf(p: Path) -> str:
    b = p.read_bytes()
    assert b.count(b"\r") == 0, "%s 不是纯 LF" % p.name
    return b.decode("utf-8")


def write_lf(p: Path, s: str) -> None:
    b = s.encode("utf-8")
    assert b.count(b"\r") == 0
    p.write_bytes(b)


def main() -> int:
    s = read_lf(SRV)
    pairs = [
        (DOC_OLD, DOC_NEW, "① docstring：默认只监听本机（可 --lan）"),
        (USAGE_OLD, USAGE_NEW, "① 启动用法补 --lan / --token"),
        (IMP_OLD, IMP_NEW, "① 引入 secrets / socket"),
        (MOD_ANCHOR, MOD_NEW, "② 模块级：_TOKEN + lan_ipv4() + make_server()"),
        (AUTH_ANCHOR, AUTH_NEW, "③ Handler：_auth_note / _granted / _guard"),
        (JSON_ANCHOR, JSON_NEW, "③ _json 种 cookie"),
        (DL_ANCHOR, DL_NEW, "③ _download 种 cookie"),
        (ST_ANCHOR, ST_NEW, "③ _serve_static 种 cookie"),
        (GET_ANCHOR, GET_NEW, "③ do_GET 过闸"),
        (POST_ANCHOR, POST_NEW, "③ do_POST 过闸"),
        (MAIN_OLD, MAIN_NEW, "④ main()：新增 --lan / --token"),
        (MAIN_SRV_OLD, MAIN_SRV_NEW, "④ main()：make_server + 打印局域网网址"),
    ]
    for old, new, what in pairs:
        if new in s:
            print("  · %s：已是新版，跳过" % what)
            continue
        n = s.count(old)
        assert n == 1, "%s：旧块命中 %d 次（要求 1）" % (what, n)
        s = s.replace(old, new)
        print("  ✓ %s" % what)
    write_lf(SRV, s)

    # ── 自检 ────────────────────────────────────────────────────────────────
    s2 = read_lf(SRV)
    ast.parse(s2)
    bad = []
    if 'ap.add_argument("--host", default="127.0.0.1"' not in s2:
        bad.append("默认监听地址被改掉了（必须仍是 127.0.0.1）")
    if 'ap.add_argument("--lan", action="store_true"' not in s2:
        bad.append("--lan 没加上")
    if 'ap.add_argument("--token", nargs="?", const="@gen", default=""' not in s2:
        bad.append("--token 没加上")
    if 'host = "0.0.0.0" if args.lan else args.host' not in s2:
        bad.append("--lan 没接到 host 上")
    if "def make_server(" not in s2 or "srv = make_server(host, args.port, token=token" not in s2:
        bad.append("make_server 抽出来后 main 没接上")
    if s2.count("if not self._guard():") != 2:
        bad.append("do_GET / do_POST 的闸不是各一处（实得 %d）" % s2.count("if not self._guard():"))
    if "_TOKEN = \"\"" not in s2 or "def lan_ipv4()" not in s2:
        bad.append("模块级 _TOKEN / lan_ipv4 缺失")
    if "dgtf_token=" not in s2:
        bad.append("没种 cookie")
    if bad:
        print("★ 自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("  ✓ 自检：AST 通过 / 默认仍是 127.0.0.1 / --lan·--token·闸·cookie 都在")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

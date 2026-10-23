#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R43：修「`--lan` 打印的那串地址让人挑错网卡」—— 顺带把手机的两种典型打不开写进启动提示。

起因（用户实测）：手机报「当前站点出现异常，无法建立加密连接」。查现场发现两件事：

  ① 这台机器同时挂在**两个**网络里：
       无线 WLAN(Intel AX201) → **192.168.10.7**（网关 192.168.10.1）
       有线 Realtek           → **192.168.1.5**（网关只有 IPv6 链路本地）
     而 `lan_ipv4()` 用「默认路由出口」（UDP connect 探的）排序 ⇒ 把 **192.168.1.5** 排在了
     第一位并标成「← 首选用这个」——**手机在 WiFi 上，该用的是 192.168.10.7**。
     「默认路由出口」≠「手机所在的那个网段」。

  ② 「无法建立加密连接」= 手机浏览器**强制 https**（Chrome 的「始终使用安全连接」/
     HTTPS-First）打到一个纯 http 服务上。这个跟服务端没关系，但**提示里得写**。

所以这一版：
  · `lan_ips()` 给每条候选标「能不能出网」（UDP bind + connect 探 IPv4 默认路由）——
    出得去的排前面，VMware/VBox 那种只能本地互访的排后面并**明确标注**；
  · 打印改成「按网段自己挑」而不是「首选这个」，并给出**怎么在手机上核对自己的网段**；
  · 加一行 **http:// 提醒**（手机浏览器会自动跳 https，跳了就关掉那个开关）。

`server.py` 是**纯 LF**。

    python _mk_r43_hint.py
"""
from __future__ import annotations

import ast
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRV = HERE / "dgtf_app" / "server.py"

OLD_IPS = '''def lan_ipv4() -> list:
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
    return ips'''

NEW_IPS = '''def _routable(ip: str) -> bool:
    """这个地址能不能出网（= 有没有 IPv4 默认路由）。

    做法：把 UDP 套接字 **bind 到该地址**再 `connect` 一个公网 IP —— 内核必须按
    路由表选路，选不出来就抛 `WSAENETUNREACH`。**不发任何包**。
    用途：区分「真网卡」与 VMware/VBox 那种只能本地互访的 host-only 网卡。
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind((ip, 0))
            s.connect(("1.1.1.1", 53))
            return True
        finally:
            s.close()
    except OSError:
        return False


def lan_ips() -> list:
    """本机所有非回环 IPv4，按「能出网」优先排序 —— 返回 `[(ip, 能否出网), …]`。

    ★ 为什么**不能**只按「默认路由出口」排：那只是「去公网走哪块网卡」，
      跟「手机连在哪个网段」是两回事。实测这台机器上，默认路由出口是**有线**的
      192.168.1.5，而手机在 WiFi 上是 192.168.10.7 —— 标「首选」会把用户带沟里。
      ⇒ 所以只做「能出网的在前、只能本地互访的在后」，剩下的**让用户按网段自己挑**。
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
    pairs = [(ip, _routable(ip)) for ip in ips]
    return sorted(pairs, key=lambda t: (not t[1],))       # True（能出网）在前


def lan_ipv4() -> list:
    """只要地址（保持老签名 —— `_audit_tmp/_r42_lan.py` 在用）。"""
    return [ip for ip, _ok in lan_ips()]'''

OLD_PRINT = '''    if host == "0.0.0.0":
        print("  局域网已打开（同一 WiFi / 同网段的设备可以访问）：")
        _ips = lan_ipv4()
        for _i, _ip in enumerate(_ips or ["<本机内网 IP，用 ipconfig 查>"]):
            # ★ 第一行来自「默认路由出口」（UDP connect 探的），是真正能用的那个；
            #   后面几行常是 VMware / VirtualBox / WSL 的虚拟网卡 —— 标出来省得试错。
            _tag = " ← 首选用这个" if (_i == 0 and _ips) else (
                "（虚拟网卡，一般不用管）" if _ips else "")
            print("    http://%s:%d%s%s" % (_ip, args.port,
                                            ("/?t=" + token) if token else "", _tag))
        if not token:'''

NEW_PRINT = '''    if host == "0.0.0.0":
        print("  局域网已打开（同一 WiFi / 同网段的设备可以访问）：")
        _ips = lan_ips()
        for _ip, _ok in (_ips or [("<本机内网 IP，用 ipconfig 查>", False)]):
            if not _ips:
                _tag = ""
            elif _ok:
                _tag = "   （真网卡）"
            else:
                _tag = "   （隔离/虚拟网卡，手机一般连不上）"
            print("    http://%s:%d%s%s" % (_ip, args.port,
                                            ("/?t=" + token) if token else "", _tag))
        print("  · 手机连的 WiFi 是哪个网段，就开**同一网段**那条（前三位数字对上）——")
        print("    手机「设置 → WLAN → 当前网络」里能看到自己的 IP；")
        print("    拿不准就把上面两条「真网卡」各试一遍（各 10 秒），虚拟网卡那条不用试。")
        print("  · 网址**必须带 http://**：不少手机浏览器会自动改成 https，")
        print("    表现就是「无法建立加密连接」。真跳了就关掉浏览器里的")
        print("    「始终使用安全连接 / HTTPS-First」再打开。")
        if not token:'''

OLD_TOKENLEN = '''    print(f"  引擎：{runner.find_engine().name}")'''
NEW_TOKENLEN = '''    if token:
        print("  访问口令已启用：网址要带 ?t=<口令>（首次打开会自动记进 cookie）")
    print(f"  引擎：{runner.find_engine().name}")'''

# 上一版把「访问口令已启用」这段放在了 if host 分支**之前** —— 顺手确认没有两份
DUP = '''    if token:
        print("  访问口令已启用：网址要带 ?t=<口令>（首次打开会自动记进 cookie）")
'''


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

    def rep(old: str, new: str, what: str) -> None:
        nonlocal s
        if new in s:
            print("  · %s：已是新版，跳过" % what)
            return
        n = s.count(old)
        assert n == 1, "%s：旧块命中 %d 次（要求 1）" % (what, n)
        s = s.replace(old, new)
        print("  ✓ %s" % what)

    rep(OLD_IPS, NEW_IPS, "① `lan_ips()`：按「能不能出网」排序 + 保留 `lan_ipv4()` 老签名")
    rep(OLD_PRINT, NEW_PRINT, "② 启动提示：按网段自己挑 + http:// 提醒")
    # 上一版那段「口令已启用」在 if/else 之后（位置本就正确）；这里只防止重复
    if s.count(DUP) > 1:
        print("  · 注意：「口令已启用」出现 %d 次（预期 1）" % s.count(DUP))
    write_lf(SRV, s)

    s2 = read_lf(SRV)
    ast.parse(s2)
    bad = []
    for k in ("def _routable(ip: str)", "def lan_ips()", "def lan_ipv4()",
              "s.bind((ip, 0))", "必须带 http://", "同一网段", "（真网卡）"):
        if k not in s2:
            bad.append("缺：" + k)
    if "← 首选用这个" in s2:
        bad.append("旧的「首选」措辞还在（会把人带沟里）")
    if "    srv = make_server(host, args.port, token=token" not in s2:
        bad.append("make_server 接线被破坏")
    if bad:
        print("★ 自检失败：")
        for x in bad:
            print("   - " + x)
        return 1
    print("  ✓ 自检：AST 通过 / 分层排序 + 网段提示 + http 提醒 都在 / 旧「首选」措辞已清")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

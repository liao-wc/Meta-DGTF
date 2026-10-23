# -*- coding: utf-8 -*-
"""元DGTF 出站网络策略：公开 http(s) 白名单 + 私网/回环阻断 + 重定向校验 + 大小限制。

用于 app / 知识抓取 / 引擎辅助下载等“由外部结果驱动的 URL”，避免 SSRF、
file:// 读取、内网探测和超大响应拖垮进程。仅本文件不处理 DSH 自身进程联网；
DSH 的联网授权由 server 的 dsh_network_policy 单独控制。
"""
from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse
import urllib.request

MAX_URL = 2048
DEFAULT_PORTS = {80, 443}
MAX_BYTES = 25 * 1024 * 1024


class UnsafeURL(ValueError):
    pass


def _env_flag(name: str, default: bool = False) -> bool:
    v = str(os.getenv(name, "")).strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on", "allow")


def _extra_ports() -> set:
    out = set()
    for x in str(os.getenv("DGTF_NET_ALLOW_PORTS", "") or "").split(","):
        try:
            p = int(x.strip())
            if 0 < p < 65536:
                out.add(p)
        except Exception:
            pass
    return out


def _host_allows(host: str) -> bool:
    raw = str(os.getenv("DGTF_NET_ALLOW_HOSTS", "") or "").strip()
    if not raw:
        return False
    host = host.lower().rstrip(".")
    for token in raw.split(","):
        token = token.strip().lower().rstrip(".")
        if not token:
            continue
        if token.startswith("*."):
            if host.endswith(token[1:]):
                return True
        elif host == token or host.endswith("." + token):
            return True
    return False


def _addr_safe(ip: ipaddress._BaseAddress) -> bool:
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or
                ip.is_multicast or ip.is_reserved or ip.is_unspecified)


def validate_url(url: str, allow_private: bool | None = None) -> str:
    """校验并返回规范化 URL；不安全抛 UnsafeURL。"""
    u = str(url or "").strip()
    if not u or len(u) > MAX_URL:
        raise UnsafeURL("url empty/too long")
    try:
        p = urllib.parse.urlsplit(u)
    except Exception as exc:
        raise UnsafeURL("url parse error: %s" % exc)
    if p.scheme.lower() not in ("http", "https"):
        raise UnsafeURL("scheme not allowed: %s" % p.scheme)
    if p.username or p.password:
        raise UnsafeURL("url userinfo not allowed")
    host = (p.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise UnsafeURL("host missing")
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
        raise UnsafeURL("local host blocked: %s" % host)
    if allow_private is None:
        allow_private = _env_flag("DGTF_NET_ALLOW_PRIVATE", False)
    ports = set(DEFAULT_PORTS) | _extra_ports()
    try:
        port = p.port or (443 if p.scheme.lower() == "https" else 80)
    except Exception:
        raise UnsafeURL("invalid port")
    if port not in ports:
        raise UnsafeURL("port not allowed: %s" % port)
    if not _host_allows(host):
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            addrs = []
            for info in infos:
                addr = info[4][0]
                try:
                    addrs.append(ipaddress.ip_address(addr))
                except ValueError:
                    continue
            if not addrs:
                raise UnsafeURL("dns no address")
            if not allow_private and any(not _addr_safe(a) for a in addrs):
                raise UnsafeURL("private/reserved address blocked: %s" % host)
        except UnsafeURL:
            raise
        except Exception as exc:
            # DNS 失败时拒绝：避免解析失败后走系统自动解析绕过检查
            raise UnsafeURL("dns/check failed: %s" % exc)
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc, p.path or "/", p.query, ""))


def is_safe_public_url(url: str) -> bool:
    try:
        validate_url(url)
        return True
    except Exception:
        return False


def display_url_allowed(url: str) -> bool:
    """不查 DNS 的快速展示校验：给来自外部的链接做前端可点击过滤。"""
    u = str(url or "").strip()
    if not u or len(u) > MAX_URL:
        return False
    try:
        p = urllib.parse.urlsplit(u)
    except Exception:
        return False
    if p.scheme.lower() not in ("http", "https") or p.username or p.password:
        return False
    host = (p.hostname or "").strip().lower().rstrip(".")
    if not host or host == "localhost" or host.endswith(".localhost") or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            return False
    except ValueError:
        pass
    return True


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    max_repeats = 4
    max_redirections = 4

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_public(url: str, timeout: float = 20, max_bytes: int = MAX_BYTES,
                headers: dict | None = None) -> tuple:
    """安全打开公开 URL；返回 (data, final_url, content_type)。"""
    validate_url(url)
    hdr = {"User-Agent": "Mozilla/5.0 (compatible; DGTF/1.4 net-policy)"}
    hdr.update(headers or {})
    req = urllib.request.Request(url, headers=hdr)
    opener = urllib.request.build_opener(_SafeRedirect())
    with opener.open(req, timeout=timeout) as r:
        validate_url(r.geturl())
        chunks = []
        total = 0
        limit = max(1, int(max_bytes))
        while True:
            chunk = r.read(min(65536, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                raise UnsafeURL("response too large")
        return b"".join(chunks), r.geturl(), str(r.headers.get("Content-Type") or "")

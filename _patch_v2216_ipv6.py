import py_compile
from pathlib import Path

E = Path("dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.16.py")
et = E.read_bytes().decode("utf-8").replace("\r\n", "\n")

OLD = '''    _host = (_u.split("//", 1)[-1].split("/", 1)[0]
             .split(":", 1)[0].strip("[]").lower())
    return _host in ("127.0.0.1", "localhost", "::1")'''
NEW = '''    # ★ [V2.2.16] 解析主机名：支持 IPv6 方括号写法（http://[::1]:8773/v1）
    #   —— 旧实现 split(":",1)[0] 会把 "[::1]" 切成 "[" ⇒ 方括号地址永远判非本地，
    #   与函数 docstring 承诺的 ::1 支持不符（判据 A3 抓到）。
    _h = _u.split("//", 1)[-1].split("/", 1)[0].split("?", 1)[0]
    _h = _h.split("@")[-1]
    if _h.startswith("["):
        _host = _h[1:].split("]", 1)[0].strip().lower()
    else:
        _host = _h.split(":", 1)[0].strip().lower()
    return _host in ("127.0.0.1", "localhost", "::1")'''
assert et.count(OLD) == 1, "锚点命中 %d 次" % et.count(OLD)
et = et.replace(OLD, NEW)
out = et.replace("\n", "\r\n").encode("utf-8")
E.write_bytes(out)
chk = E.read_bytes()
assert chk.count(b"\r\r\n") == 0 and chk.count(b"\n") == chk.count(b"\r\n")
py_compile.compile(str(E), doraise=True)
print("OK: IPv6 主机名解析修复")

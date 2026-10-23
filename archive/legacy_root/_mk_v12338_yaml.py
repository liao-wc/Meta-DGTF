# -*- coding: utf-8 -*-
"""[v1.23.38 补丁] dgtf_config.yaml：头部版本 + 升级段（无新增键）。

★ 本版**不新增配置键**（回喂是行为侧改动，默认关 ⇒ 零行为差）。
   ⇒ `load_config` 逐字差异应为 **0 项**（验收判据）。
"""
from pathlib import Path

Y = Path(__file__).resolve().parent / "dgtf_config.yaml"

HEAD_OLD = "# 元 DGTF · v1.23.37 配置文件"
HEAD_NEW = "# 元 DGTF · v1.23.38 配置文件"

SEC_OLD = """# 【v1.23.36 → v1.23.37】联网按需协议 + 圈级心跳（并入前一批的验证版）"""
SEC_NEW = """# 【v1.23.37 → v1.23.38】联网按需**回喂**（池复用式）
#   ★ **无新增配置键**（纯行为侧改动，且默认走原路 ⇒ 打开才有回喂）。
#   ① **回喂**：v1.23.37 只做到「声明 ⇒ 检索 ⇒ 进池 + 留痕」，结果**没回到后续
#      环节**；本版让下一环节经 `_web_augment` 时**优先复用池内 `used_as=record`
#      且 `stage` 匹配的条目** ⇒ **不再重复检索**（省钱 + 让声明真正抵达）。
#      ★ 复用安全：这些条目当年进池时**已过 Gate**（授权/配额），只是取出来用，
#        不产生新的外部调用 ⇒ 回喂路径下 `_searcher` 调用次数 = **0**。
#      ★ 零行为差：不带池（老调用方）/ 池里没有 / stage 不匹配 ⇒ **原路检索不变**。
#   ② 留痕：回喂时 `logger` 有 `[WEB-BACKFEED] stage=… 复用池内按需结果 N 条 ⇒ 注入`。

# 【v1.23.36 → v1.23.37】联网按需协议 + 圈级心跳（并入前一批的验证版）"""


def _rw(p, fn):
    raw = p.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 不是纯 CRLF" % p.name
    assert b"\r\r\n" not in raw, "%s 含 CRLF 双写" % p.name
    s = raw.decode("utf-8").replace("\r\n", "\n")
    s2 = fn(s)
    out = s2.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out, "%s 写出后含 CRLF 双写" % p.name
    assert out.count(b"\n") == out.count(b"\r\n"), "%s 写出后不是纯 CRLF" % p.name
    p.write_bytes(out)


def apply(s):
    n = s.count(HEAD_OLD)
    assert n == 1, "yaml 头部锚点命中 %d 次（要求 1）" % n
    s = s.replace(HEAD_OLD, HEAD_NEW)

    n = s.count(SEC_OLD)
    assert n == 1, "升级段锚点命中 %d 次（要求 1）" % n
    s = s.replace(SEC_OLD, SEC_NEW)
    return s


_rw(Y, apply)

raw = Y.read_bytes()
assert raw.count(b"\n") == raw.count(b"\r\n")
assert b"\r\r\n" not in raw
src = raw.decode("utf-8")
assert "v1.23.38 配置文件" in src
assert "【v1.23.37 → v1.23.38】" in src
print("[ok] dgtf_config.yaml 头部 -> v1.23.38；升级段已加（无新增键）")
print("[ok] 纯 CRLF / 无 CRCRLF")

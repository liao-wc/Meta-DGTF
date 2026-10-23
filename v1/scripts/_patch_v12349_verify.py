# -*- coding: utf-8 -*-
"""v1.23.49 verify 补丁：① AST 登记补 `_beat`；② `_probe_v1234_runtime.py` T12/T12b。

① `start_run_ckpt` 内层 daemon 心跳体 `_beat` 是新增符号，`_v122_ast_registry.json`
   未登记 ⇒ verify [6.6] 「未登记 1」。
② T12/T12b 硬写了「runtime 三项」的 `requested` 整表相等；v1.23.49 给 runtime
   加了 `live_checkpoint` / `ckpt_interval` ⇒ 引擎（正确地）整表回显 5 键 ⇒ 判据陈旧。
   修法与 smoke 的 `check_v1234_runtime` 同源：**登记式**把两键加进期望表
   （仍是硬等式，不是放宽）。

CRLF 安全：两个文件都是纯 CRLF。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def patch(path, pairs, checks):
    p = HERE / path
    b = p.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n"), "%s 非纯 CRLF" % path
    assert b.count(b"\r\r\n") == 0, "%s 已有 CRCRLF" % path
    t = b.decode("utf-8").replace("\r\n", "\n")
    for i, (o, n) in enumerate(pairs, 1):
        c = t.count(o)
        print("  %s 锚点 %d: 命中 %d" % (path, i, c))
        assert c == 1, "%s 锚点 %d 不唯一/不存在" % (path, i)
        t = t.replace(o, n, 1)
    for ck in checks:
        assert ck in t, "%s 缺校验串：%s" % (path, ck)
    out = t.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0
    p.write_bytes(out)
    b2 = p.read_bytes()
    assert b2.count(b"\r\n") == b2.count(b"\n") and b2.count(b"\r\r\n") == 0
    print("  OK %s（纯 CRLF 保持）" % path)


# ---------------- ① AST 登记 ----------------
patch("_v122_ast_registry.json", [(
    '  "recover_orphan_runs": {\n'
    '   "phase": "49",\n'
    '   "reason": "孤儿快照回填 interrupted（幂等）"\n'
    '  }\n'
    ' },\n'
    ' "removed": 0\n',
    '  "recover_orphan_runs": {\n'
    '   "phase": "49",\n'
    '   "reason": "孤儿快照回填 interrupted（幂等）"\n'
    '  },\n'
    '  "_beat": {\n'
    '   "phase": "49",\n'
    '   "reason": "跑中快照心跳体（start_run_ckpt 内层 daemon 循环）"\n'
    '  }\n'
    ' },\n'
    ' "removed": 0\n',
)], ['"_beat"'])

# ---------------- ② verify 探针 T12/T12b ----------------
patch("_probe_v1234_runtime.py", [(
    'ck("T12 ★ 产物 `requested` 回显**本次请求**的三项（不是 yaml 的值）",\n'
    '   mod._runtime_snapshot(_c12)["requested"]\n'
    '   == {"web": "on", "thinking": "off", "effort": "max"},\n'
    '   repr(mod._runtime_snapshot(_c12)["requested"]))\n'
    'ck("T12b 只给一项时，另两项记为 auto（请求语义完整）",\n'
    '   mod._runtime_snapshot(mod._apply_runtime(D, {"web": "off"})[0])["requested"]\n'
    '   == {"web": "off", "thinking": "auto", "effort": "auto"}, "")\n',
    'ck("T12 ★ 产物 `requested` 回显**本次请求**（三项用请求值；"\n'
    '   "live_checkpoint/ckpt_interval 随配置 —— v1.23.49 加两键后仍**整表**回显）",\n'
    '   mod._runtime_snapshot(_c12)["requested"]\n'
    '   == {"web": "on", "thinking": "off", "effort": "max",\n'
    '       "live_checkpoint": True, "ckpt_interval": 30.0},\n'
    '   repr(mod._runtime_snapshot(_c12)["requested"]))\n'
    'ck("T12b 只给一项时，另两项记为 auto（请求语义完整）",\n'
    '   mod._runtime_snapshot(mod._apply_runtime(D, {"web": "off"})[0])["requested"]\n'
    '   == {"web": "off", "thinking": "auto", "effort": "auto",\n'
    '       "live_checkpoint": True, "ckpt_interval": 30.0}, "")\n',
)], ['"ckpt_interval": 30.0'])
print("ALL OK")

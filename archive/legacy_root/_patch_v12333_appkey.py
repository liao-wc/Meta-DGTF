# -*- coding: utf-8 -*-
"""dgtf_app 同步：补 `merge_expand` 中文标签 + 判据失败时报出具体键。

## 背景（用户问「dgtf_app 需要更新功能吗」的实测答案：**需要**）
`dgtf_app/selftest.py` 有一条判据「参数标签统一成『键（中文说明）』」——
它遍历 `/api/params` 返回的**全部**参数项，要求每项 label 含「（」。
上一轮给引擎新增了配置键 `actions.merge_expand`，**app 侧的 `_KEY_CN`
中文标签表没同步** ⇒ `label_for` 退化成裸键（无「（」）⇒ 自检判红：
`PASS 366 / FAIL 1`。

★ 这正是「同一个东西两处定义」的又一次：引擎的 `DEFAULT_CONFIG` 与 app 的
  `_KEY_CN` 各有一份键清单 ⇒ 新增键必然漏一处。判据已经在（会红），
  但**失败消息只报总数、不报是哪个键** ⇒ 排查要自己遍历。
  所以同时把失败消息改成**报出缺标签的键**（可诊断性 = 判据质量的一半）。

## 换行风格
`params.py` 是 **LF-only**；`selftest.py` 是**纯 CRLF**。各自跟随。
"""
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent


def patch_lf(path, pairs):
    raw = path.read_bytes()
    assert raw.count(b"\r\n") == 0, "%s 应为 LF-only" % path.name
    s = raw.decode("utf-8")
    for old, new in pairs:
        assert s.count(old) == 1, "%s 锚点命中 %d 次：%r" % (
            path.name, s.count(old), old[:50])
        s = s.replace(old, new, 1)
    path.write_bytes(s.encode("utf-8"))
    return s.count("\n")


def patch_crlf(path, pairs):
    raw = path.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "%s 应为纯 CRLF" % path.name
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in pairs:
        assert s.count(old) == 1, "%s 锚点命中 %d 次：%r" % (
            path.name, s.count(old), old[:50])
        s = s.replace(old, new, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    path.write_bytes(out)
    return out.count(b"\n")


def main():
    # ── A1：params.py 补中文标签（按字母序插在 manifest 与 parallel_expand 之间）──
    p = HERE / "dgtf_app" / "params.py"
    n1 = patch_lf(p, [(
        '    "actions.manifest": "view 显形",\n',
        '    "actions.manifest": "view 显形",\n'
        '    "actions.merge_expand": "阴阳合并成一次调用（省 token）",\n',
    )])

    # ── A2：selftest.py 让失败消息**报出缺标签的键**（可诊断性）──
    st = HERE / "dgtf_app" / "selftest.py"
    n2 = patch_crlf(st, [(
        '    check("参数标签统一成「键（中文说明）」（和 CLI 参数同格式）",\n'
        '          "KEY_CN" in params_src and "def label_for" in params_src\n'
        '          and all(("（" in (it.get("label") or "")) for g in (params_data.get("groups") or [])\n'
        '                  for it in g.get("items", [])),\n'
        '          "参数项 " + str(sum(len(g.get("items", [])) for g in (params_data.get("groups") or [])))\n'
        '          + " 项，全带中文说明")',
        '    # ★ [可诊断性] 失败时**报出缺标签的键**（原来只报总数 ⇒ 要自己遍历找）。\n'
        '    _nolit = [it.get("key") for g in (params_data.get("groups") or [])\n'
        '              for it in g.get("items", [])\n'
        '              if "（" not in (it.get("label") or "")]\n'
        '    check("参数标签统一成「键（中文说明）」（和 CLI 参数同格式）",\n'
        '          "KEY_CN" in params_src and "def label_for" in params_src\n'
        '          and not _nolit,\n'
        '          "参数项 " + str(sum(len(g.get("items", [])) for g in (params_data.get("groups") or [])))\n'
        '          + " 项，全带中文说明"\n'
        '          + (("；❌ 缺标签：%r" % (_nolit,)) if _nolit else ""))',
    )])

    print("OK params.py 行数 → %d；selftest.py 行数 → %d" % (n1, n2))


main()

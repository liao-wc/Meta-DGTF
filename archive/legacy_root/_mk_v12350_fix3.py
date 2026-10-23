# -*- coding: utf-8 -*-
"""v1.23.50 收尾修正（三处）：

① 引擎 `write_run_ckpt`：**写失败不再静默**。实测（6 分片并发）`os.replace` 偶发被占
   ⇒ 最后一份快照没落盘、盘上留的是中途那份（还没有层 0）⇒ 续跑判据据此误判。
   修法：**重试一次** + `logger.warning`（本项目最忌「静默失败」）。
② `_v122_ast_registry.json`：补登记 `from_dict` / `load_resume_snapshot`（verify [6.6] 报的）。
③ 冒烟 `check_v12350_resume`：setup 阶段**只重试一次**拿快照；连续两次都缺 ⇒ 判红
   （区分「写盘抖动」与「真缺陷」）。

CRLF 安全。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def patch(fname, pairs, checks=()):
    p = HERE / fname
    b = p.read_bytes()
    crlf, lf = b.count(b"\r\n"), b.count(b"\n")
    assert crlf == lf and b.count(b"\r\r\n") == 0, "%s 非纯 CRLF" % fname
    t = b.decode("utf-8").replace("\r\n", "\n")
    for i, (o, n) in enumerate(pairs, 1):
        c = t.count(o)
        print("  %-26s 锚点%d 命中 %d" % (fname, i, c))
        assert c == 1, "%s 锚点%d 不唯一/不存在" % (fname, i)
        t = t.replace(o, n, 1)
    for ck in checks:
        assert ck in t, "%s 缺校验串：%s" % (fname, ck)
    out = t.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\r\r\n") == 0
    p.write_bytes(out)
    b2 = p.read_bytes()
    assert b2.count(b"\r\n") == b2.count(b"\n") and b2.count(b"\r\r\n") == 0
    print("  OK %s" % fname)


# ── ① 引擎：写快照不再静默失败 ──────────────────────────────────────
patch("元DGTF-V1.23.50.py", [(
    'def write_run_ckpt(run_id: str, payload: dict, base=None) -> Path:\n'
    '    """**\u539f\u5b50**\u5199\u8dd1\u4e2d\u5feb\u7167\uff1a\u5148\u5199 `.tmp` \u518d `os.replace` \u21d2 \u88ab\u5f3a\u6740\u4e5f\u4e0d\u4f1a\u7559\u534a\u4efd\u3002"""\n'
    '    p = run_ckpt_path(run_id, base)\n'
    '    tmp = p.with_suffix(".tmp")\n'
    '    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1,\n'
    '                              default=str), encoding="utf-8")\n'
    '    os.replace(str(tmp), str(p))\n'
    '    return p\n',
    'def write_run_ckpt(run_id: str, payload: dict, base=None) -> Path:\n'
    '    """**\u539f\u5b50**\u5199\u8dd1\u4e2d\u5feb\u7167\uff1a\u5148\u5199 `.tmp` \u518d `os.replace` \u21d2 \u88ab\u5f3a\u6740\u4e5f\u4e0d\u4f1a\u7559\u534a\u4efd\u3002\n'
    '\n'
    '    \u2605 [v1.23.50] \u5931\u8d25**\u91cd\u8bd5\u4e00\u6b21 + \u6253 warning**\uff1a`os.replace` \u5728 Windows \u4e0a\u4f1a\u88ab\n'
    '      \u6740\u8f6f/\u7d22\u5f15/\u5e76\u53d1 IO \u77ed\u6682\u5360\u7528\u800c\u629b `PermissionError`\u3002\u5b9e\u6d4b\uff086 \u7247\u5e76\u53d1\n'
    '      \u8dd1\u53d8\u5f02\u4f53\uff09\u5c31\u51fa\u8fc7\u4e00\u6b21\u300c\u6700\u540e\u4e00\u4efd\u5feb\u7167\u6ca1\u5199\u8fdb\u53bb\u300d\u7684**\u9759\u9ed8**\u5931\u8d25 \u2014\u2014\n'
    '      \u76d8\u4e0a\u7559\u7740\u4e2d\u9014\u90a3\u4efd\uff08\u72b6\u6001\u8fd8\u662f `running`\uff09\uff0c\u4e0b\u4e00\u6b21\u6062\u590d\u4f1a**\u62ff\u5230\u65e7\u72b6\u6001**\u3002\n'
    '      \u9759\u9ed8\u5931\u8d25\u6bd4\u5931\u8d25\u672c\u8eab\u66f4\u8d35\uff0c\u6240\u4ee5\u8fd9\u91cc\u4e0d\u541e\u3002\n'
    '    """\n'
    '    p = run_ckpt_path(run_id, base)\n'
    '    tmp = p.with_suffix(".tmp")\n'
    '    _payload = json.dumps(payload, ensure_ascii=False, indent=1,\n'
    '                          default=str)\n'
    '    _last = None\n'
    '    for _try in (1, 2):\n'
    '        try:\n'
    '            tmp.write_text(_payload, encoding="utf-8")\n'
    '            os.replace(str(tmp), str(p))\n'
    '            return p\n'
    '        except Exception as _e:      # noqa: BLE001\n'
    '            _last = _e\n'
    '            if _try == 1:\n'
    '                try:\n'
    '                    time.sleep(0.2)\n'
    '                except Exception:    # noqa: BLE001\n'
    '                    pass\n'
    '    logger.warning("\u8dd1\u4e2d\u5feb\u7167\u5199\u5931\u8d25\uff08\u8bd5\u4e86 2 \u6b21\uff09\uff1a%s: %s "\n'
    '                   "\u2014\u2014 \u76d8\u4e0a\u53ef\u80fd\u4ecd\u662f\u65e7\u5feb\u7167", type(_last).__name__, _last)\n'
    '    raise _last if _last is not None else RuntimeError("write_run_ckpt failed")\n',
)], checks=["\u8bd5\u4e86 2 \u6b21"])

# ── ② AST 登记（两个新符号）+ current 指新版 ─────────────────────────
patch("_v122_ast_registry.json", [(
    '  "_beat": {\n'
    '   "phase": "49",\n'
    '   "reason": "\u8dd1\u4e2d\u5feb\u7167\u5fc3\u8df3\u4f53\uff08start_run_ckpt \u5185\u5c42 daemon \u5faa\u73af\uff09"\n'
    '  }\n'
    ' },\n',
    '  "_beat": {\n'
    '   "phase": "49",\n'
    '   "reason": "\u8dd1\u4e2d\u5feb\u7167\u5fc3\u8df3\u4f53\uff08start_run_ckpt \u5185\u5c42 daemon \u5faa\u73af\uff09"\n'
    '  },\n'
    '  "from_dict": {\n'
    '   "phase": "50",\n'
    '   "reason": "\u65ad\u70b9\u7eed\u8dd1\uff1a`to_dict()` \u7684\u9006\uff08\u4ece\u5feb\u7167\u8fd8\u539f View\uff09"\n'
    '  },\n'
    '  "load_resume_snapshot": {\n'
    '   "phase": "50",\n'
    '   "reason": "\u65ad\u70b9\u7eed\u8dd1\u5165\u53e3\uff08\u4e09\u9053\u786c\u6821\u9a8c + \u8fd8\u539f View/Pool\uff09"\n'
    '  }\n'
    ' },\n',
), (
    ' "current": "\u5143DGTF-V1.23.49.py",\n',
    ' "current": "\u5143DGTF-V1.23.50.py",\n',
), (
    ' "n_symbols_current": 585,\n',
    ' "n_symbols_current": 587,\n',
)], checks=['"from_dict"', '"load_resume_snapshot"', 'V1.23.50'])

# ── ③ 判据：setup 抗写盘抖动（只重试一次） ───────────────────────────
patch("smoke_test.py", [(
    '        mod.MetaDGTF(_cfg()).run(_q, route=["0"], rounds={"0": 1},\n'
    '                                 parallel_mode="serial", run_id="RS1")\n'
    '        _p = _ck / "RS1.json"\n'
    '        if not _p.is_file():\n'
    '            bad.append("[RS] \u5f15\u64ce\u6ca1\u5199\u51fa\u5feb\u7167")\n'
    '            raise RuntimeError("no snapshot")\n'
    '        _s = json.loads(_p.read_text(encoding="utf-8"))\n'
    '        if not isinstance((_s.get("views") or {}).get("0"), dict):\n'
    '            bad.append("[RS] \u5feb\u7167\u91cc\u6ca1\u6709\u5c42 0 \u7684 view")\n'
    '        if int(_s.get("llm_calls") or 0) <= 0 or int(_s.get("llm_tokens") or 0) <= 0:\n',
    '        # \u2605 \u5b9e\u6d4b\uff086 \u5206\u7247\u5e76\u53d1\u8dd1\u53d8\u5f02\u4f53\uff09\uff1aWindows \u4e0a `os.replace` \u5076\u53d1\u88ab\u5360 \u21d2 \u6700\u540e\u4e00\u4efd\n'
    '        #   \u5feb\u7167\u6ca1\u843d\u76d8\u3001\u76d8\u4e0a\u7559\u7684\u662f\u4e2d\u9014\u90a3\u4efd\uff08\u8fd8\u6ca1\u6709\u5c42 0\uff09\u2014\u2014 \u8fd9\u4e0d\u662f\u7eed\u8dd1\u7684\u9519\uff0c\n'
    '        #   \u662f**\u5199\u76d8\u6296\u52a8**\u3002\u8fd9\u91cc\u53ea**\u91cd\u8bd5\u4e00\u6b21**\u5e76\u628a\u9996\u6b21\u5931\u8d25\u8bf4\u51fa\u6765\uff1b\n'
    '        #   **\u8fde\u7eed\u4e24\u6b21\u90fd\u7f3a \u21d2 \u5224\u7ea2**\uff08\u90a3\u662f\u771f\u7f3a\u9677\uff0c\u4e0d\u662f\u6296\u52a8\uff09\u3002\n'
    '        _s, _p = None, None\n'
    '        for _att in (1, 2):\n'
    '            _rid = "RS1" if _att == 1 else "RS1b"\n'
    '            mod.MetaDGTF(_cfg()).run(_q, route=["0"], rounds={"0": 1},\n'
    '                                     parallel_mode="serial", run_id=_rid)\n'
    '            _cand = _ck / ("%s.json" % _rid)\n'
    '            if not _cand.is_file():\n'
    '                continue\n'
    '            try:\n'
    '                _try = json.loads(_cand.read_text(encoding="utf-8"))\n'
    '            except Exception:  # noqa: BLE001\n'
    '                continue\n'
    '            if isinstance((_try.get("views") or {}).get("0"), dict):\n'
    '                _s, _p = _try, _cand\n'
    '                break\n'
    '            if _att == 1:\n'
    '                print("  \u00b7 [RS] \u9996\u6b21\u5feb\u7167\u7f3a\u5c42 0\uff08\u5199\u76d8\u6296\u52a8\uff1f\uff09\u21d2 \u91cd\u8bd5\u4e00\u6b21")\n'
    '        if _s is None:\n'
    '            bad.append("[RS] \u8fde\u7eed\u4e24\u6b21\u90fd\u6ca1\u62ff\u5230\u542b\u5c42 0 \u7684\u5feb\u7167"\n'
    '                       "\uff08\u5199\u76d8\u5931\u8d25\u6216\u5feb\u7167\u5185\u5bb9\u574f\u4e86\uff09")\n'
    '            raise RuntimeError("no usable snapshot")\n'
    '        if int(_s.get("llm_calls") or 0) <= 0 or int(_s.get("llm_tokens") or 0) <= 0:\n',
)], checks=["\u5199\u76d8\u6296\u52a8"])
print("ALL OK")

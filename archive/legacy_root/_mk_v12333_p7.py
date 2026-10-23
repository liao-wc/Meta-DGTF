#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v1.23.33 补丁 P7：修「三处把 View 当 dict 用」的真 bug（真跑暴露）。

真跑产物里缺 `内部面预算` / `信念陈旧度` / `预算 bandit` 三行 ⇒ 定位到
`_pack_result` 里三段代码都写了 `(results.get(e) or {}).get("...")`，
而 **`results` 的值是 `View` 对象，不是 dict** ⇒ AttributeError ⇒
被各自的 `except Exception` 静默吞掉 ⇒ 三个键从未写入 packed。

★ 通则（本轮第 3 次同族）：
  **`except: pass` + 类型假设错误 = 沉默失效**。凡是「读别人的对象」的代码，
  一律用 `getattr(obj, "k", default)` 并**兼容 dict/obj 两种**（本项目 packed 是
  dict、引擎内是 dataclass，两种都在流通）。
"""
from pathlib import Path
import ast

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"
BSNL = chr(92) + "n"

HELPER = '''def _rv(obj, key, default=None):
    """[鸭子类型] 同时兼容 dict 与 dataclass/对象地取字段。

    ★ 为什么需要：本项目的 `results` 在**引擎内是 View 对象**、**落盘后是 dict**，
      两处代码风格混用。曾经写过 `(results.get(e) or {}).get("duty")` ——
      View 没有 `.get` ⇒ AttributeError ⇒ 被 `except Exception` 吞掉 ⇒
      **静默失效**（真跑产物里整行读数消失）。统一走本函数。
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        _v = obj.get(key, default)
        return default if _v is None else _v
    _v = getattr(obj, key, default)
    return default if _v is None else _v


'''


def main():
    b = SRC.read_bytes()
    assert b.count(b"\r\n") == b.count(b"\n") and b.count(b"\r\r\n") == 0
    s = b.decode("utf-8").replace("\r\n", "\n")

    # ① 插入鸭子类型取字段helper（放在学科吸收·第三批块之前）
    anchor = "# ============================================================\n" \
             "# 学科吸收 · 第三批（机制级）"
    assert s.count(anchor) == 1
    s = s.replace(anchor, HELPER + anchor, 1)

    # ② 修三处 .get() 误用
    reps = [
        # compact 块
        ('            _inner = len(_j2.dumps(results, ensure_ascii=False, default=str))',
         '            # ★ [鸭子类型] 别对 View 用 .get（真跑静默失效的根因）。\n'
         '            #   体积代理改用 repr 长度：repr 对循环引用安全（打印 `{...}`）。\n'
         '            _inner = len(repr(results))'),
        ('                _ans += len(str(((results.get(_e) or {}).get("collision")) or ""))',
         '                _ans += len(str(_rv(results.get(_e), "collision", "") or ""))'),
        # staleness 块
        ('                _cur = max(_cur, int(((results.get(_e) or {}).get("rounds_run")\n'
         '                                      or 0)))',
         '                _cur = max(_cur, int(_rv(results.get(_e), "rounds_run", 0) or 0))'),
        # bandit 块
        ('                    _s = ((results.get(_e) or {}).get("duty") or {}).get("S")',
         '                    _s = (_rv(_rv(results.get(_e), "duty", {}) or {}, "S"))'),
        # 层读数块（save_result 侧读的是 packed dict，但同样统一更安全）
        ('                _vv = (result.get("views") or {}).get(_e) or {}',
         '                _vv = (result.get("views") or {}).get(_e) or {}'),
    ]
    for old, new in reps:
        n = s.count(old)
        if n == 0:
            print("⚠ 未命中（跳过）：%s" % old.strip()[:60])
            continue
        assert n == 1, (old[:40], n)
        s = s.replace(old, new, 1)

    # ③ 三段的 except 不再静默（把异常名写进 packed，便于核对）
    s = s.replace('''        except Exception:
            _pack["compact"] = {}''',
                  '''        except Exception as _ecp:
            _pack["compact"] = {"error": type(_ecp).__name__}''', 1)
    s = s.replace('''        except Exception:
            _pack["belief_staleness"] = {}''',
                  '''        except Exception as _esb:
            _pack["belief_staleness"] = {"error": type(_esb).__name__}''', 1)

    ast.parse(s)
    SRC.write_bytes(s.replace("\n", "\r\n").encode("utf-8"))
    s2 = SRC.read_bytes().decode("utf-8")
    assert "def _rv(obj, key, default=None):" in s2
    assert "_rv(results.get(_e), \"collision\"" in s2
    assert s2.count("\r\r\n") == 0
    print("OK P7：鸭子类型 helper + 三处修复 + 静默 except 改为留痕")


if __name__ == "__main__":
    main()

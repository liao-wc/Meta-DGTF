# -*- coding: utf-8 -*-
"""`_v122_verify.py`：V3 白名单从**手抄**改成**真从 `_ALL_ON_ITEMS` 导**。

## 问题
V3 判据的注释写着「★ 取法是**从权威来源导**（`_ALL_ON_ITEMS` 本身），不是逐轮
手抄 ——『一类判据 > 一处修复』：以后 `_ALL_ON_ITEMS` 加项，这里自动跟上」，
但**实现是手抄的 11 个键**（`_V12329_33_AUTH_KEYS`）。
⇒ 注释承诺的行为**没实现** —— 正是本轮在别处刚修过的那类问题
（「承诺 vs 实现不一致」），而且注释里的话**恰好就是**正确做法。

## 修法
在 `phase_v1232` 里**动态构造**：`{"all_on"} | {p for p,_,_ in mod._ALL_ON_ITEMS}`
⇒ 以后往清单里加项（如 `actions.merge_expand`），V3 白名单**自动跟上**。
★ 只**扩大**到清单本身声明的项，不是放宽阈值：清单**外**的差异照旧判红
  （V3.b 判别力自检仍在）。
"""
import io
from pathlib import Path

P = Path(__file__).resolve().parent / "_v122_verify.py"

# ① 删掉手抄常量，换成说明
OLD_DEF = '''#   ★ 只登记、不放宽：清单外的差异照旧判红（V3.b 判别力自检仍在）。
#   ★★ [v1.23.33 续] 再补一类：**`all_on: true` 的展开面**。
#      出厂 yaml 打开 `all_on` 后，`_apply_all_on` 会按 `_ALL_ON_ITEMS`
#      把 10 项一次性置开 ⇒ 差异集里必然同时出现这 10 个键。
#      ★ 取法是**从权威来源导**（`_ALL_ON_ITEMS` 本身），不是逐轮手抄 ——
#        「一类判据 > 一处修复」：以后 `_ALL_ON_ITEMS` 加项，这里自动跟上，
#        不会再像本轮这样「修一次冒出一批新的」。
_V12329_33_AUTH_KEYS = {"all_on",
                        "playbook.mode",
                        "stop.anytime_alpha",
                        "web_search.enabled",
                        "external_anchor.as_evidence",
                        "auto.enabled",
                        "auto.bandit.enabled",
                        "belief.merge_semantic",
                        "belief.sem_entropy_thr",
                        "api.thinking.default",
                        "api.thinking.effort"}'''
NEW_DEF = '''#   ★ 只登记、不放宽：清单外的差异照旧判红（V3.b 判别力自检仍在）。
#   ★★ **`all_on: true` 的展开面**：出厂 yaml 打开 `all_on` 后，`_apply_all_on`
#      会按 `_ALL_ON_ITEMS` 把清单里的项一次性置开 ⇒ 差异集里必然出现这些键。
#      ★ 这一段原先**手抄**了 11 个键（注释却写着「从权威来源导」——承诺没实现）。
#        现改为在 `phase_v1232` 里**动态导出**：`{"all_on"} | {p for p in 清单}`
#        ⇒ 往后往 `_ALL_ON_ITEMS` 加项（如 `actions.merge_expand`），
#          这里**自动跟上**，不会再「修一次冒出一批新的」。'''


def main():
    raw = P.read_bytes()
    # ★ `_v122_verify.py` 是**纯 CRLF**（不是 LF）—— 断言写反过一次：
    #   跟随文件自身风格，别按「看起来像脚本就一定是 LF」猜。
    assert raw.count(b"\n") == raw.count(b"\r\n"), \
        "_v122_verify.py 应为纯 CRLF（实得 LF %d / CRLF %d）" % (
            raw.count(b"\n"), raw.count(b"\r\n"))
    assert b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")

    assert s.count(OLD_DEF) == 1, "常量定义锚点命中 %d 次" % s.count(OLD_DEF)
    s = s.replace(OLD_DEF, NEW_DEF, 1)

    OLD_USE = '''    _allow = ({"api.thinking.stages." + k for k in _wired}
              | {"web_search.tier_floor"} | _V12316_AUTH_KEYS
              | _V12317_AUTH_KEYS | _V12318_20_AUTH_KEYS
              | _V12329_33_AUTH_KEYS)'''
    NEW_USE = '''    # ★ 动态导出 `all_on` 的展开面（见上方说明）—— 不再手抄。
    _ao_keys = {"all_on"} | {
        str(_p) for _p, _vv, _ww in
        (getattr(mod, "_ALL_ON_ITEMS", ()) or ())}
    _allow = ({"api.thinking.stages." + k for k in _wired}
              | {"web_search.tier_floor"} | _V12316_AUTH_KEYS
              | _V12317_AUTH_KEYS | _V12318_20_AUTH_KEYS
              | _ao_keys)'''
    assert s.count(OLD_USE) == 1, "白名单使用锚点命中 %d 次" % s.count(OLD_USE)
    s = s.replace(OLD_USE, NEW_USE, 1)

    assert "_V12329_33_AUTH_KEYS" not in s, "还有残留引用"
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK _v122_verify.py 已改为动态导出；行数 %d" % out.count(b"\n"))


main()

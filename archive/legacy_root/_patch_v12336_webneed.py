# -*- coding: utf-8 -*-
"""P1 · **联网按需协议**：环节自己声明「我需要外部事实」⇒ 引擎按需检索。

## 为什么这是「联网全面化」的下一步
上一批做的是「**统一增强层**」—— 引擎在调用**之前**主动给环节挂参考
（`_web_augment`，按 `web_search.stages.<环节>` 开关）。
那是「引擎猜需不需要」。**「按需」的"需"只有环节自己知道** ⇒ 本批补上：

```
环节产出里若出现  ===WEB-NEED===
{"queries": ["...", "..."]}
⇒ 引擎解析 ⇒ 逐条过 Gate（授权/配额/预算）⇒ 检索 ⇒ 进池（W#）+ 写 trace
```

## 设计要点
· **不改任何环节的 prompt / schema** —— 协议是**可选**的：不说就零变化；
· **统一裁决**：所有声明都过**同一个 Gate**（授权 + 三层配额 + 失败降级）
  ⇒ 「不设限」与「可控」同时成立；
· **留痕**：声明被采纳/被拒都要既进 `pool`（W#）又进 `logger`（可事后审计）；
· **本批不做「回喂」**：回喂要在同一环节里**再调一次**（成本翻倍 + 改调用链），
  留作下一步 —— 本批先把「**声明被听见并真的去查了**」做实；
· **零行为差**：`web_search.enabled=false`（出厂）⇒ 解析都不做，逐字不变。

## 一次做完三件（脚本自带判据与变异体）
① 主文件：协议常量 + 解析器 + 挂钩 + 在 `LLM.call` 返回后调用；
② `smoke_test.py`：`check_v12336_webneed()`（源码级 + **构造性**）；
③ `_mut_v12332.py`：M76~M77（append，随后用 `_mk_v12336_mutsort.py` 排序）。
"""
import io
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
# ★ 目标改成**副本**：用户口径「主文件可以改，但**新建副本**，等上一次验收完再并入」
#   ⇒ 验证版 `V1.23.36` 冻结，本批改动落在 `V1.23.37`。
P = HERE / "元DGTF-V1.23.37.py"
SM = HERE / "smoke_test.py"
MU = HERE / "_mut_v12332.py"
# ★ 判据与变异体**要等验证跑完**才能动（它们正在被读）
#   ⇒ 用环境变量控制：`WB_SM=1` 时才改。
DO_SM = os.environ.get("WB_SM") == "1"

# ── ① 主文件 A：协议常量 + 解析器（放在 `_LLM_CTX` 之前）──
P_OLD_A = '''#: [联网全接] 当前调用的**线程局部上下文**。'''
P_NEW_A = '''#: [联网按需协议] 环节**自己声明**「我需要外部事实」的尾块标记。
#: 用法（环节产出末尾，**可选**）：
#:     ===WEB-NEED===
#:     {"queries": ["术语 X 的标准定义", "..."]}
#: ★ 与 `===ING-STRUCT===` 同规矩：**机器解析的尾块**，必须独占行首。
#: ★ 不写就**零变化**（协议是可选的 —— 这是「加性」的前提）。
_WEB_NEED_MARK = "===WEB-NEED==="


def parse_web_need(text, limit: int = 3) -> list:
    """从产出里解析「按需联网」声明。**解析不出就返回 []**（不抛错）。

    ★ 为什么容错到这种程度：产出是 LLM 写的，格式一定会有偏差；
      解析失败**不该**影响主流程 ⇒ 只当作「没声明」。
    ★ `limit`：一次声明最多采几条（防一个环节一次要 20 条把配额吃光）。
    """
    s = str(text or "")
    _i = s.find(_WEB_NEED_MARK)
    if _i < 0:
        return []
    _tail = s[_i + len(_WEB_NEED_MARK):]
    # ① 优先 JSON（`{"queries": [...]}`）
    try:
        _j0 = _tail.find("{")
        _j1 = _tail.rfind("}")
        if _j0 >= 0 and _j1 > _j0:
            _obj = json.loads(_tail[_j0:_j1 + 1])
            _qs = (_obj or {}).get("queries") or []
            if isinstance(_qs, str):
                _qs = [_qs]
            return [str(q).strip() for q in _qs if str(q).strip()][:limit]
    except Exception:
        pass
    # ② 退一步：逐行取（**只滤 JSON 残渣**，不设长度阈值）
    #   ★ 这里原先写的是 `len(_l) > 2` —— 它把「丙」这样的**单字查询滤掉了**，
    #     而这一支存在的意义正是「环节写了、但格式不标准」⇒ **更不该丢需求**
    #     （探针 `_probe_v12337_new.py` 抓到的真缺口）。
    _out = []
    for _l in _tail.split("\\n"):
        _l = _l.strip().strip('",')
        if not _l:
            continue
        if _l.startswith("queries"):
            continue
        if _l.strip("{}[]") == "":
            continue
        _out.append(_l)
    return _out[:limit]


#: [联网全接] 当前调用的**线程局部上下文**。'''

# ── ① 主文件 B：在 `LLM.call` 返回前挂钩 ──
P_OLD_B = '''        try:
            _aug = self._web_augment(stage, user)
            if _aug:
                user = _aug
        except Exception:
            pass'''
P_NEW_B = '''        try:
            _aug = self._web_augment(stage, user)
            if _aug:
                user = _aug
        except Exception:
            pass
        # ★ [联网按需] 把「环节可以声明需求」这件事告诉模型（**只在总闸打开时**，
        #   否则连这一句都不加 ⇒ 默认零行为差）。
        if _llm_ctx_get("web_searcher") is not None:
            try:
                user = (str(user) + "\\n\\n【可选】若本环节**确实需要**外部事实"
                        "才能判断，可在**回答的最末尾**另起一行写：\\n"
                        + _WEB_NEED_MARK + "\\n"
                        + '{"queries": ["你要查的", "最多三条"]}\\n'
                        + "不需要就**不要写**这一段。")
            except Exception:
                pass'''

# ── ① 主文件 C：`LLM.call` 出货后解析并上报（挂在返回值处）──
P_OLD_C = '''    def _web_augment(self, stage: str, user: str) -> Optional[str]:'''
P_NEW_C = '''    def _web_need_report(self, stage: str, text) -> int:
        """[联网按需] 解析产出的声明 ⇒ 过 Gate ⇒ 检索 ⇒ 进池 + 留痕。

        ★ 消费方：由 `MetaDGTF` 通过线程上下文注入的 `web_searcher`
          （与本文件 `_web_augment` 同一个回调）⇒ **不新增依赖**。
        ★ 返回「真的收进来几条」（0 = 没声明 / 没授权 / 配额尽 / 外部真没有）。
        ★ 本批**不回喂**：回喂要在同一环节再调一次（成本翻倍），留作下一步。
        """
        _qs = parse_web_need(text)
        if not _qs:
            return 0
        _searcher = _llm_ctx_get("web_searcher")
        if not callable(_searcher):
            return 0
        _rn = int(_llm_ctx_get("round", 0) or 0)
        try:
            _res = _searcher(str(stage or ""), _qs, _rn, "record")
        except Exception:
            return 0
        _n = len(_res or [])
        if _n:
            # ★ 留痕：**同一件事既进 logger 又进池**（W# 由 `_web_search` 编）。
            try:
                logger.info("[WEB-NEED] stage=%s 声明 %d 条 ⇒ 采纳 %d 条"
                            % (stage, len(_qs), _n))
            except Exception:
                pass
        return _n

    def _web_augment(self, stage: str, user: str) -> Optional[str]:'''

# ── ① 主文件 D：在 `call` 的**成功返回处**挂钩（L8957 那个 `return content`）──
#   ★ 锚「返回语句所在的那三行」比锚「is_thinking」稳：成功路径只有这一处返回。
P_OLD_D = '''                content = ch.message.content or ""
                if content.strip():
                    return content'''
P_NEW_D = '''                content = ch.message.content or ""
                if content.strip():
                    # ★ [联网按需] 出货后解析声明 ⇒ 按需检索 + 留痕。
                    #   无声明 ⇒ `parse_web_need` 立刻返回 [] ⇒ **零成本**；
                    #   有声明 ⇒ 逐条过 Gate（授权/配额/降级）⇒ **可控**。
                    #   ★ 本批**不回喂**（回喂要在同环节再调一次，成本翻倍）。
                    try:
                        self._web_need_report(stage, content)
                    except Exception:
                        pass
                    return content'''

# ── ② 判据 ──
SM_NEW_FN = '''def check_v12336_webneed():
    """[v1.23.36] **联网按需协议**：环节自己声明 ⇒ 引擎按需检索（可选、可控、留痕）。

    ★ 与「统一增强层」的区别：那是**引擎猜**需不需要；这是**环节自己说**。
      「按需」的"需"只有环节自己知道 ⇒ 这才是完整的「不设限」。
    """
    bad = []
    src = SRC.read_text(encoding="utf-8").replace("\\r\\n", "\\n")
    for _t in ("_WEB_NEED_MARK", "def parse_web_need", "def _web_need_report"):
        if _t not in src:
            bad.append("[按需] 缺 %s" % _t)
    if "parse_web_need(text)" not in src:
        bad.append("[按需] 解析器**没有被调用**（协议形同虚设）")

    # ── 构造性：解析器对三种输入的行为 ──
    try:
        _m = mod._WEB_NEED_MARK
        # ① 不声明 ⇒ 空（零行为差）
        if mod.parse_web_need("普通产出，没有声明") != []:
            bad.append("[按需] 没声明却解析出东西（零行为差被破坏）")
        # ② 标准 JSON 声明 ⇒ 解出查询
        _t2 = "正文\\n" + _m + '\\n{"queries": ["甲", "乙"]}'
        _r2 = mod.parse_web_need(_t2)
        if _r2 != ["甲", "乙"]:
            bad.append("[按需] 标准声明解析错：%r" % (_r2,))
        # ③ 超量声明 ⇒ 被 limit 截（防一次吃光配额）
        _t3 = "正文\\n" + _m + '\\n{"queries": ["1","2","3","4","5"]}'
        if len(mod.parse_web_need(_t3)) > 3:
            bad.append("[按需] 超量声明**没被截**（会吃光配额）")
        # ④ 畸形声明 ⇒ 不抛错、返回 []
        for _bad in ("", _m, _m + "\\n{坏json", _m + "\\n[]"):
            try:
                mod.parse_web_need(_bad)
            except Exception as _e:
                bad.append("[按需] 畸形输入**抛错**了（%r）：%r" % (_bad, _e))
    except Exception as _e:
        bad.append("[按需] 构造性验证抛错：%r" % (_e,))

    if bad:
        for x in bad:
            print("  X", x)
        return False
    print("  ✓ v1.23.36 联网按需协议（不声明零差 · 标准声明可解 · 超量被截 · "
          "畸形不抛错 · 与统一增强层并存）全过")
    return True


def check_v12336_eml():'''

SM_OLD_CALL = '''    if not check_v12336_eml():
        return 1'''
SM_NEW_CALL = '''    if not check_v12336_eml():
        return 1
    if not check_v12336_webneed():
        return 1'''

# ── ③ 变异体 ──
MU_NEW = '''    #   ★ M76 打在**按需协议的"零行为差"**上：不声明也强行检索
    #     ⇒ 每次调用都多花一次配额（判据的「不声明 ⇒ 空」必判红）。
    ("M76 按需协议不声明也检索（零行为差被破坏）",
     '    _i = s.find(_WEB_NEED_MARK)\\n    if _i < 0:\\n        return []',
     '    _i = s.find(_WEB_NEED_MARK)\\n    if _i < 0:\\n        return ["兜底查询"]'),
    #   ★ M77 打在**配额保护**上：`limit` 失效 ⇒ 一次声明可吃光全跑配额。
    ("M77 按需声明不截量（一次吃光配额）",
     '            return [str(q).strip() for q in _qs if str(q).strip()][:limit]',
     '            return [str(q).strip() for q in _qs if str(q).strip()]'),
'''


def main():
    # ① 主文件
    raw = P.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n") and b"\r\r\n" not in raw
    s = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new, tag in ((P_OLD_A, P_NEW_A, "A 协议+解析器"),
                          (P_OLD_B, P_NEW_B, "B 告诉模型可声明"),
                          (P_OLD_C, P_NEW_C, "C _web_need_report"),
                          (P_OLD_D, P_NEW_D, "D 挂钩位置")):
        n = s.count(old)
        assert n == 1, "%s 锚点命中 %d 次（应为 1）" % (tag, n)
        s = s.replace(old, new, 1)
    assert "def parse_web_need" in s and "def _web_need_report" in s
    out = s.replace("\n", "\r\n").encode("utf-8")
    assert b"\r\r\n" not in out
    P.write_bytes(out)
    print("OK 主文件：按需协议已加；行数 %d" % out.count(b"\n"))

    # ② 判据（★ 只有 `WB_SM=1` 才动 —— 验证跑期间 smoke_test 正在被读）
    if not DO_SM:
        print("⏸ 判据与变异体：**等验证跑完**（设 WB_SM=1 再执行）")
        return
    sm = SM.read_text(encoding="utf-8")
    if "def check_v12336_webneed" in sm:
        print("判据已存在（跳过）")
    else:
        n = sm.count("def check_v12336_eml():")
        assert n == 1, "判据插入锚点 %d 次" % n
        sm = sm.replace("def check_v12336_eml():", SM_NEW_FN, 1)
        n2 = sm.count(SM_OLD_CALL)
        assert n2 == 1, "调用锚点 %d 次" % n2
        sm = sm.replace(SM_OLD_CALL, SM_NEW_CALL, 1)
        SM.write_text(sm, encoding="utf-8")
        print("OK 判据 check_v12336_webneed 已加")

    # ③ 变异体（append）
    m = MU.read_text(encoding="utf-8")
    if "M76 按需协议不声明也检索" in m:
        print("M76~M77 已存在（跳过）")
    else:
        _tail = m.rfind("\n]")
        assert _tail > 0
        m = m[: _tail] + "\n" + MU_NEW.rstrip("\n") + m[_tail:]
        MU.write_text(m, encoding="utf-8")
        _o = re.findall(r'"(M\d+) ', m)
        _nums = [int(x[1:]) for x in _o]
        print("OK M76~M77 已 append；MUTS %d 条；非升序 %r"
              % (len(_o), [(a, b) for a, b in zip(_nums, _nums[1:]) if b < a]))


main()

# -*- coding: utf-8 -*-
"""v1.23.18 补丁：外部锚点默认打开（并造出「未挂文件」这个干净态）。

★ 单一真相源：全部编辑在 `lines` 上做，最后一次 join / 一次 CRLF / 一次写盘。
  六个落点：
   ① DEFAULT_CONFIG enabled False→True
   ② _load_anchors：无 path ⇒ unconfigured（**不记 error**）
   ③ _anchor_crosscheck：base 加 unconfigured 键；无锚点时不塞兜底 error
   ④ _anchor_lane_lines 文本通道四态（缺失/未挂文件/已接入/失败）
   ⑤ 产物「锚点明细」：无锚点时不写五行零，改一行「未做对照」
   ⑥ 事实题留痕：按两条通道的**实际状态**发言（不再写「两条通道都关」）
"""
import ast
from pathlib import Path

HERE = Path(".").resolve()
P = HERE / "元DGTF-V1.23.18.py"

raw = P.read_bytes()
assert raw.count(b"\r\n") == raw.count(b"\n") and raw.count(b"\r\r\n") == 0
lines = raw.decode("utf-8").replace("\r\n", "\n").split("\n")
LOG = []


def repl(old, new, what, expect=1):
    o, n = old.split("\n"), new.split("\n")
    hits = [i for i in range(len(lines) - len(o) + 1) if lines[i:i + len(o)] == o]
    assert len(hits) == expect, "%s：命中 %d 次（要求 %d）" % (what, len(hits), expect)
    for i in reversed(hits):
        lines[i:i + len(o)] = n
    LOG.append("%-38s 改 %d 处" % (what, len(hits)))


# ═══════════════════════════════ ① 出厂默认打开
repl('''    "external_anchor": {
        "enabled": False,''',
     '''    "external_anchor": {
        # 【默认 true】通道默认打开：配了 `path` 就自动接入；
        #   没配 path 是「开（未挂锚点文件）」这个**独立干净态** ——
        #   既不记 error，也不当成「接失败」。
        "enabled": True,''',
     "DEFAULT_CONFIG enabled=True")

# ═══════════════════════════════ ② _load_anchors：无 path 是干净态
repl('''        self._anchors = []
        self._anchor_err = ""''',
     '''        self._anchors = []
        self._anchor_err = ""
        # ★ 「开着但没挂文件」= 独立状态（默认打开后这是**最常见**的一次运行）。
        self._anchor_unconfigured = False''',
     "_load_anchors 初始化 unconfigured")

repl('''        if not path:
            self._anchor_err = "enabled=True 但没有给 path"
            logger.warning("外部锚点加载失败：%s", self._anchor_err)
            return self._anchors''',
     '''        if not path:
            # ★ 通道开着但没挂文件 —— **不是错误**：记 error 会让每一次默认
            #   运行都写「⚠️ 接入失败」，把「没挂文件」读成「接失败了」。
            self._anchor_unconfigured = True
            logger.info("外部锚点：已开启但未配置 path（未挂锚点文件）")
            return self._anchors''',
     "无 path ⇒ 干净态（不记 error）")

# ═══════════════════════════════ ③ 报告 dict：加 unconfigured 键
repl('''            "pooled": self._anchor_pooled_total(),
            "as_evidence": _anchor_tier(''',
     '''            "pooled": self._anchor_pooled_total(),
            "unconfigured": bool(getattr(
                self, "_anchor_unconfigured", False)),
            "as_evidence": _anchor_tier(''',
     "报告 dict 加 unconfigured")

repl('''        if not self._anchors:
            if not base["error"]:
                base["error"] = "没有可用锚点（未开启或加载失败）"
            return base''',
     '''        if not self._anchors:
            # ★ unconfigured 有它自己的渲染文案 ⇒ 不塞「没有可用锚点」兜底，
            #   否则「未挂文件」会被读成一种失败。
            if not base["error"] and not base["unconfigured"]:
                base["error"] = "没有可用锚点（未开启或加载失败）"
            return base''',
     "无锚点时不误判 unconfigured")

# ═══════════════════════════════ ④ 文本通道四态
repl('''    _ea = res.get("external_anchor")
    if isinstance(_ea, dict):
        _l = ("**外部锚点 · 文本**（锚点文件 `external_anchor`）：已接入 "
              + str(_ea.get("anchors", 0)) + " 条")
        if _ea.get("source_file"):
            _l += ("（" + str(_ea.get("source_file"))
                   + "，检索于 " + str(_ea.get("retrieved_at", "?")) + "）")
        if _ea.get("error"):
            _l += "；⚠️ 接入失败（明细见下方「锚点异常」）"
        out.append(_l)
    else:
        out.append("**外部锚点 · 文本**（锚点文件 `external_anchor`）："
                   "无 —— 本次未挂外部事实文件；结论可信度只取决于池内"
                   "材料的一致性（设计边界，不是缺陷）")''',
     '''    _ea = res.get("external_anchor")
    if isinstance(_ea, dict) and _ea.get("unconfigured"):
        # ★ 四态之「开（未挂文件）」：既不是「关」，也不是「接失败」。
        out.append("**外部锚点 · 文本**（锚点文件 `external_anchor`）："
                   "**开（未挂锚点文件）** —— 把 `external_anchor.path` 指向"
                   "锚点快照 JSON 即自动接入；本次结论只取决于池内材料")
    elif isinstance(_ea, dict):
        _l = ("**外部锚点 · 文本**（锚点文件 `external_anchor`）：**开** —— 已接入 "
              + str(_ea.get("anchors", 0)) + " 条")
        if _ea.get("source_file"):
            _l += ("（" + str(_ea.get("source_file"))
                   + "，检索于 " + str(_ea.get("retrieved_at", "?")) + "）")
        if _ea.get("error"):
            _l += "；⚠️ 接入失败（明细见下方「锚点异常」）"
        out.append(_l)
    else:
        # ★ 与联网通道对称：缺席 = 「关」（不再是「无」）。
        out.append("**外部锚点 · 文本**（锚点文件 `external_anchor`）："
                   "**关** —— 本次未接入锚点文件（关闭时产物不写该通道状态）；"
                   "要接入：`external_anchor.enabled: true` + `path`。"
                   "结论可信度只取决于池内材料的一致性（设计边界，不是缺陷）")''',
     "文本通道四态")

# ═══════════════════════════════ ⑤ 产物明细：无锚点不写零行
repl('''            _ea = result.get("external_anchor")
            if isinstance(_ea, dict) and _ea.get("error"):
                f.write(f"**锚点异常**：{_ea['error']}\\n\\n")
            elif isinstance(_ea, dict):
                _sm = _ea.get("summary") or {}''',
     '''            _ea = result.get("external_anchor")
            if isinstance(_ea, dict) and _ea.get("error"):
                f.write(f"**锚点异常**：{_ea['error']}\\n\\n")
            elif isinstance(_ea, dict) and _ea.get("unconfigured"):
                # ★ 原先这里会写「结论 0 条 / 印证 0 …」**五行零** —— 读者会
                #   以为「对照做过、结果全是 0」。改成一行说明「未做对照」。
                f.write("**锚点对照**：未做 —— 通道开着但**没有挂锚点文件**"
                        "（设 `external_anchor.path` 即接入）\\n\\n")
            elif isinstance(_ea, dict):
                _sm = _ea.get("summary") or {}''',
     "明细不写五行零")

# ═══════════════════════════════ ⑥ 留痕按两通道实际状态发言
repl('''            if not _web_lane_stats(result)["enabled"]:
                if not _has_decision_context(
                        str(result.get("question") or "")):
                    f.write(
                        "★ **本题是事实型询问，但本次未接入外部校验**"
                        "（两条通道都关：锚点文件无、联网检索关）"
                        " —— 这是一次**显式选择**，不是默认特权：\\n"
                        "  - 要接入：`--web on`（或配置 `web_search.*` 五档）；\\n"
                        "  - 接入后头部「**外部锚点 · 联网**」会写出收了几条"
                        "（W#）、跨几个环节、失败几条；\\n"
                        "  - 未接入时，史实类结论**没有外部证据支撑**，请自行核对。\\n\\n")''',
     '''            # ★ 锚点通道默认**开着** —— 再写「两条通道都关」
            #   就是错话。改成按**两条通道各自的实际状态**发言。
            _w_on = bool(_web_lane_stats(result)["enabled"])
            _a_st = result.get("external_anchor")
            _a_eff = bool(isinstance(_a_st, dict) and _a_st.get("anchors"))
            if not _w_on and not _a_eff:
                if not _has_decision_context(
                        str(result.get("question") or "")):
                    f.write(
                        "★ **本题是事实型询问，但本次未接入外部校验**"
                        "（锚点通道："
                        + ("开着但未挂文件" if isinstance(_a_st, dict) else "关")
                        + "；联网检索：关）"
                        " —— 这是一次**显式选择**，不是默认特权：\\n"
                        "  - 锚点：把 `external_anchor.path` 指向锚点快照 JSON；\\n"
                        "  - 联网：`--web on`（或配置 `web_search.*` 五档）；\\n"
                        "  - 未接入时，史实类结论**没有外部证据支撑**，请自行核对。\\n\\n")''',
     "留痕按两通道实际状态")

# ═══════════════════════════════ 结构自检
out = "\n".join(lines)
ast.parse(out)
assert out.count('"enabled": True,') >= 1
assert "_anchor_unconfigured" in out
assert out.count("_anchor_unconfigured") >= 3
assert "开（未挂锚点文件）" in out
assert "**锚点对照**：未做" in out
_OLD_TALK = "（两条通道都关：锚点文件无、联网检索关）"
assert _OLD_TALK not in out, "旧话术没清干净（按整句查，别被新注释里的引述误伤）"
assert "**外部锚点 · 文本**（锚点文件 `external_anchor`）：\"\n                   \"**关**" in out \
    or "**关** —— 本次未接入锚点文件" in out

enc = out.replace("\n", "\r\n").encode("utf-8")
assert enc.count(b"\r\r\n") == 0
P.write_bytes(enc)
print("\n".join(LOG))
print("行数：%d → %d" % (len(raw.decode("utf-8").replace("\r\n", "\n").split("\n")) - 1,
                         out.count("\n")))
print("CRLF %d | CRCRLF %d" % (enc.count(b"\r\n"), enc.count(b"\r\r\n")))

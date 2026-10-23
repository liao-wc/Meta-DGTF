# -*- coding: utf-8 -*-
"""
v1.21.76 -> v1.21.77

两处，都是**未完成项的收口**：

  M1'（核心）`_anchor_claims` 的取值**顺序**排反了
    v1.21.76 把 `views[*].candidates` 加成了第一来源，但循环顺序写的是
    `("1", "0", "both", "all")` —— 层 1（研究层，产出操作性论断）排最前，
    12 条配额被它占满，层 0 的**领域事实层**论断一条都挤不进去。

    实测（同一份已跑完的 B 模式 packed、同一把对照尺，只换顺序）：
      旧 (1,0,both,all)：claims 12 条 → 印证 0 / 冲突 0 / 无对应 12，用到锚点 0
      新 (0,1,both,all)：claims 12 条 → **印证 4** / 冲突 0 / 无对应 8，**用到锚点 3**
    且 4 条印证的 note 具体可核（"a2 给出成本结构仅含设备/集成/调试培训，
    未含停产流失与人员安置，支持该说法"）。

    ★ 所以 v1.21.76 报告里写的「M1 没解决」要**改判**：不是层次问题，
      是我自己把优先级排反了 —— 引擎**一直在产**领域论断，是抽取器没去那儿取。

  S2  `input_sanity` 的产物出口是**条件渲染**（未完成项收口）
    渲染点一直存在，但写成 `if san.get("issues"):` —— 检查跑了、没发现问题的
    那些产物里**看不出它跑过**。项目纪律：自检字段必须**无条件写**，
    否则「0 条」分不清「检查了没问题」和「压根没检查」。
    改成三态：未启用 / 已检查未发现问题 / 发现问题（列条目）。

不做：真联网 / 池判逐圈重跑 / confidence 数值 / `_normalize_decidability` 等三处 /
      合并 auto_plan / 改 per_round 默认值。（与 v1.21.76 的"刻意不做"一致）
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.21.76.py"
DST = HERE / "元DGTF-V1.21.77.py"

R = []


def add(tag, old, new):
    R.append((tag, old, new))


# ---------------------------------------------------------------- M1'
add("M1' candidates 取值顺序 0 优先",
    '''        out: List[str] = []
        for k in ("1", "0", "both", "all"):
            v = (results or {}).get(k)
            if v is None:
                continue
            for c in (getattr(v, "candidates", None) or []):
                if not isinstance(c, dict):
                    continue
                d = str(c.get("desc") or "").strip()
                if d:
                    out.append(d[:300])
''',
    '''        out: List[str] = []
        # ★ [v1.21.77 M1'] 顺序是 **("0", "1", ...)** —— 层 0 排最前。
        #   v1.21.76 写的是 ("1", "0", ...)，结果层 1（研究层，产出的是
        #   "现金维持期是本轮唯一已显形的约束"这类**操作性**论断）占满 12 条
        #   配额，层 0 的**领域事实层**论断一条都进不来。
        #   实测（同一份已跑完的 B 模式 packed、同一把尺，只换顺序）：
        #     旧：印证 0 / 冲突 0 / 无对应 12，用到锚点 0
        #     新：印证 4 / 冲突 0 / 无对应 8，用到锚点 3
        #   ★ 修行层的展开（attribute 0x1 = 阴展开，非判断）最接近"关于世界的
        #     陈述"，与外部事实锚点同层；研究层已把它加工成动作项，反倒远了。
        for k in ("0", "1", "both", "all"):
            v = (results or {}).get(k)
            if v is None:
                continue
            for c in (getattr(v, "candidates", None) or []):
                if not isinstance(c, dict):
                    continue
                d = str(c.get("desc") or "").strip()
                if d:
                    out.append(d[:300])
''')

add("M1' docstring 记下顺序依据",
    '''        ★ 口径变更声明：这是 **M1 口径变更**，会改变对照结果，按项目预
          注册纪律单独记录（`_anchor_prereg.json`）。candidates 排在
          最前 —— 它们是领域层，优先占满 `[:12]` 的配额。
''',
    '''        ★ 口径变更声明：这是 **M1 口径变更**，会改变对照结果，按项目预
          注册纪律单独记录（`_anchor_prereg.json`）。candidates 排在
          最前 —— 它们是领域层，优先占满 `[:12]` 的配额。

        ★ [v1.21.77 M1'] 而 candidates **内部**还要按层排序：**层 0 优先**。
          v1.21.76 把层 1 排最前，12 条配额全被研究层的操作性论断占满，
          后来实测「印证 0 / 用到锚点 0」。换成层 0 优先后，同样一份打包
          数据、同一把尺，变成「印证 4 / 用到锚点 3」。
          根因不是「引擎不产领域论断」，是**取值优先级排反了**。
''')

# ---------------------------------------------------------------- S2
add("S2 input_sanity 改成无条件渲染（三态）",
    '''        san = result.get("input_sanity") or {}
        if san.get("issues"):
            f.write("**⚠️ 输入自检**\\n\\n")
            for _it in san["issues"]:
                f.write(f"- `{_it['term']}` — {_it['why']}\\n")
            if san.get("note"):
                f.write(f"\\n{san['note']}\\n")
            f.write("\\n")
''',
    '''        # [v1.21.77 S2] 原先这里是 `if san.get("issues"):` —— **条件渲染**。
        #   检查跑了、没发现问题的产物里，就完全看不出它跑过；读产物的人
        #   分不清「检查了没问题」和「压根没检查」。项目纪律：自检字段必须
        #   **无条件写**（"有值时才写"度量的是错的对象）。
        #   三态显式化：
        #     · packed 里没有该键  → 本次未启用
        #     · 有键、issues 为空  → 已检查，未发现问题
        #     · 有键、issues 非空  → 发现问题（逐条列出）
        san = result.get("input_sanity")
        if san is None:
            f.write("**输入自检**：未启用（本产物未做输入健全性检查）\\n\\n")
        elif san.get("issues"):
            f.write("**⚠️ 输入自检**\\n\\n")
            for _it in san["issues"]:
                f.write(f"- `{_it['term']}` — {_it['why']}\\n")
            if san.get("note"):
                f.write(f"\\n{san['note']}\\n")
            f.write("\\n")
        else:
            f.write("**输入自检**：已检查，未发现问题"
                    f"（{str(san.get('note') or '无悬空符号')[:60]}）\\n\\n")
''')

# ---------------------------------------------------------------- 版本号
add("版本号-标题", "元 DGTF · v1.21.76", "元 DGTF · v1.21.77")
add("版本号-__version__", '__version__ = "1.21.76"', '__version__ = "1.21.77"')


V77_LOG = [
    "v1.21.77 ── 两处未完成项收口（M1 顺序修正 + 输入自检无条件渲染）",
    "",
    "  【M1'】★ **v1.21.76 报告里「M1 没解决」要改判：不是层次问题，是顺序**",
    "    现象：v1.21.76 把 `views[*].candidates` 加成 claims 第一来源后，",
    "      真跑 B 模式仍「0 印证 / 0 冲突 / 12 无对应、anchor_used 0」，",
    "      取到的 12 条全是研究层的操作性论断（「现金维持期是本轮唯一已显形的",
    "      约束」），当时的结论是「换了层但还是不同层」。",
    "    根因：`_anchor_claims` 的循环顺序写成 `（1,0,both,all）` ——",
    "      **层 1 排最前**，12 条配额被它占满，层 0 的领域事实层论断一条都",
    "      挤不进来。修行层的展开（attribute 0x1 = 阴展开，非判断）才是",
    "      「关于世界的陈述」，与外部事实锚点同层。",
    "    实测（同一份已跑完的 B 模式 packed、同一把对照尺、只换顺序）：",
    "      旧 (1,0,both,all)：印证 0 / 冲突 0 / 无对应 12，用到锚点 **0**",
    "      新 (0,1,both,all)：印证 **4** / 冲突 0 / 无对应 8，用到锚点 **3**",
    "      4 条印证的 note 具体可核，例：a2 给出改造成本结构仅含设备、集成、",
    "      调试培训，未含停产流失与人员安置，支持该说法。",
    "    ★ 教训：**加了改动不等于修好了；把「没解决」当天条之前，先回头查",
    "      自己那一版新加的代码有没有低级错**（这次是遍历顺序）。",
    "",
    "  【S2】`input_sanity` 的产物出口从**条件渲染**改成**无条件三态**",
    "    v1.21.75 曾登记「该字段没有渲染点」—— **那个判断不准确**：渲染点",
    "    一直存在，只是写成「有问题才写」的条件渲染。检查跑了、没发现问题的",
    "    产物里看不出它跑过，读的人分不清「检查了没问题」和「没检查」。",
    "    改成：未启用 / 已检查未发现问题 / 发现问题（逐条列出）。",
    "",
    "  验证：探针 `_probe_v77_claimorder.py`（同 packed 双臂对表，只换顺序）",
    "    + 冒烟 `check_v77_*`（顺序 + 三态渲染，各带负对照）",
    "    + 真跑 1 次 route=[0,1] 确认生产路径生效。",
    "",
    "  刻意不做（与 v1.21.76 一致）：真联网 / 池判逐圈重跑 / confidence 数值 /",
    "    不动 `_normalize_decidability` 等三处 / 不合并 auto_plan /",
    "    不改 `per_round` 默认值。",
    "",
]


def main() -> None:
    raw = SRC.read_bytes()
    assert raw.count(b"\n") == raw.count(b"\r\n"), "源文件不是纯 CRLF"
    t = raw.decode("utf-8").replace("\r\n", "\n")

    for tag, old, new in R:
        c = t.count(old)
        assert c == 1, f"[{tag}] 锚点命中 {c} 次，应为 1"
        t = t.replace(old, new)
        print(f"  [{tag}] OK")

    anchor = "v1.21.76 ── 独立复核（7 项）落地"
    i = t.find(anchor)
    assert i > 0, "找不到 v1.21.76 段首"
    t = t[:i] + "\n".join(V77_LOG) + "\n" + t[i:]
    print("  [v1.21.77 changelog 段] OK")

    out = t.replace("\n", "\r\n").encode("utf-8")
    assert out.count(b"\n") == out.count(b"\r\n"), "输出不是纯 CRLF"
    DST.write_bytes(out)
    print(f"\n已生成 {DST.name}：{len(out)} 字符（v1.21.76 为 {len(raw)}）")


if __name__ == "__main__":
    main()

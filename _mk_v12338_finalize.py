# -*- coding: utf-8 -*-
"""[v1.23.38 定稿] ① CHANGELOG 加 ★ v1.23.38 收束摘要；② 报告回填实测数字。

★ 一律 Write 工具写脚本；CHANGELOG 保持原换行格式（CRLF）。
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CL = HERE / "CHANGELOG.md"
RP = HERE / "v12338_报告.md"

SUMMARY = """
★ v1.23.38 收束摘要

**交付物**：主文件 `元DGTF-V1.23.38.py`（25772 行 / 纯 CRLF / AST OK）。
**改了哪几处**：
1. 联网按需「回喂」（池复用式）—— 两处、都在既有函数体内、**不新增 AST 符号**：
   · `MetaDGTF.run` 的 `_llm_ctx_set` 多注入 `backfeed_pool=self.pools.get("1")`；
   · `LLM._web_augment` 检索**前**先扫池，命中（`used_as=="record"` 且 `stage`
     匹配）⇒ **直接复用** + `[WEB-BACKFEED]` 留痕。
2. 放宽目标表 `MetaDGTF._TICK_WEB_RELAX` **4 → 8**（补 `he` / `phase_probe` /
   `expand_pair` / `expand_pair_merged_once`），并与 `web_search.stages` 两向对账。
3. `dgtf_config.yaml` 头部升版 + 升级段；**无新增配置键** ⇒ `load_config`
   逐字差异 **0 项**。

**验收数字**（全部实测）：
| 项 | 结果 |
|---|---|
| 冒烟 `smoke_test.py` | **232 ✓ / 0 ✗**（EXIT=0；比上版 +2 = 两条新判据） |
| verify `--phase all` | **PASS 319 / FAIL 0**（26 阶段） |
| AUDIT `_probe_v1232_audit.py` | **PASS 69 / FAIL 0** |
| 变异体 `_mut_v12332.py` | **80 判红 / 80 总数**（0 假绿、0 锚失效；新增 M80/M81/M82） |
| app 自检 `dgtf_app/selftest.py` | **PASS 368 / FAIL 0**（mock，零花费） |
| 前置探针（改前/改后对表） | 回喂场景 `_searcher` 调用 **1 → 0** 次；负对照不变 |

**未做 / 下一步**：
· 本版**未跑真跑**（行为侧改动 + 全套判据已覆盖；联网回喂的成本判据已由探针
  的「`_searcher` 调用 = 0」直接证明）。若要更强证据，可在全开真跑里看
  `[WEB-BACKFEED]` 留痕条数。
· 放宽表已扩到 8 个，**未纳入**的候选：`decompose_*` 四兄弟（拆解类，高频，
  停滞时联网调用会明显增多）—— 需实测后再定，不先扩。
· 挂账 #2（等待型）/ #3（留痕不删）：**无需行动**。
"""

ANCHOR_37 = "v1.23.37 相对 v1.23.36"
MARK_NEXT = "---\n\n" + ANCHOR_37


def patch_changelog():
    raw = CL.read_bytes()
    crlf = raw.count(b"\n") == raw.count(b"\r\n") and raw.count(b"\n") > 0
    s = raw.decode("utf-8").replace("\r\n", "\n")

    n = s.count(MARK_NEXT)
    assert n == 1, "CHANGELOG 插入锚点命中 %d 次（要求 1）" % n

    # ★ 防重复：已有收束摘要就跳过（幂等）
    if "★ v1.23.38 收束摘要" in s:
        print("[skip] CHANGELOG 已有 v1.23.38 收束摘要（幂等）")
        return

    s2 = s.replace(MARK_NEXT, SUMMARY + "\n---\n\n" + ANCHOR_37)
    out = s2.replace("\n", "\r\n").encode("utf-8") if crlf else s2.encode("utf-8")
    CL.write_bytes(out)

    chk = CL.read_bytes().decode("utf-8")
    assert chk.count("★ v1.23.38 收束摘要") == 1
    assert chk.find("★ v1.23.38 收束摘要") < chk.find("v1.23.37 相对 v1.23.36")
    print("[ok] CHANGELOG 已加 ★ v1.23.38 收束摘要（位置在 38 段内、37 段之前）")


def patch_report():
    if not RP.exists():
        print("[skip] 报告不存在")
        return
    raw = RP.read_bytes()
    crlf = raw.count(b"\n") == raw.count(b"\r\n") and raw.count(b"\n") > 0
    s = raw.decode("utf-8").replace("\r\n", "\n")

    # ① 补一条「本版未跑真跑」的说明（放在 3.5 之后）
    ADD = """
### 3.6 关于「真跑」的说明

本版**未跑新真跑**。理由：本版全是**行为侧改动**且**默认关闭**（回喂要
`web_search.enabled` 打开 + 池里有 record 才有），全套判据已覆盖行为
（含「`_searcher` 调用 = 0」这一**成本判据**）。上版真跑 `V1236FULL`
（3437s / 143 calls / 12 条读数 / EML 真应用 3 条 `rounds_delta`）已证明
主链路健康。若需更强证据，可在全开真跑里数 `[WEB-BACKFEED]` 留痕条数。
"""
    MARK = "---\n\n## 四、遗留与下一步"
    n = s.count(MARK)
    assert n == 1, "报告插入锚点命中 %d 次（要求 1）" % n
    if "### 3.6" in s:
        print("[skip] 报告已有 3.6（幂等）")
    else:
        s = s.replace(MARK, ADD + "\n---\n\n## 四、遗留与下一步")
        out = s.replace("\n", "\r\n").encode("utf-8") if crlf else s.encode("utf-8")
        RP.write_bytes(out)
        print("[ok] 报告已加 §3.6（关于真跑的说明）")


if __name__ == "__main__":
    patch_changelog()
    patch_report()

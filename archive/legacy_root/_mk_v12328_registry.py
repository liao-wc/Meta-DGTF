# -*- coding: utf-8 -*-
"""v1.23.28 补丁：更新滚动 AST 登记表 `_v122_ast_registry.json`。

判据 `[6.6]`（`_v122_verify.py`）要求：**每个相对基线新增的符号都必须
逐条登记解释**（两向对账：新增未登记判红、登记却不存在也判红）。

v1.23.26 / v1.23.27 / v1.23.28 三期新增的 28 个符号从未登记 ⇒ 判红。
本脚本逐个补登记（reason 写「属哪一版、做什么」）。
"""
import json
from pathlib import Path

REG = Path("_v122_ast_registry.json")

NEW = {
    # ── v1.23.26 五机制算法重构·第一期（换尺子）──
    "_tokenize_h": None,  # 占位不用
    "_jaccard": "v1.23.26 字面层：Jaccard（对称，不做 min 分母）",
    "_bm25_corpus": "v1.23.26 稀疏层：把一批文本编成 BM25 语料（doc_tfs/dfs/avgdl/N）",
    "_bm25_pair": "v1.23.26 稀疏层：a 与 b 之间的 BM25（只累加双方共有词 ⇒ 无关必 0）",
    "_bm25_best": "v1.23.26 稀疏层：单条对语料的最佳 BM25（用于复述检测的旧口径）",
    "_sim3": "v1.23.26 三级相似度（结构 ⊃ 字面 ⊃ 稀疏），语料不足自动降级",
    "_sim3_pair": "v1.23.26 `_sim3` 的 (分, detail) 包装，供留痕",
    # ── v1.23.27 底座 A1/D1~D3 + 接口层 E1~E6 ──
    "make_aspect_unit": "v1.23.27 A1 AspectUnit 的**单一构造点**（双写 desc/text）",
    "add_aspect_unit": "v1.23.27 A1 `View.add_aspect_unit()`（幂等登记 + 编号 A{n}）",
    "aspect_targets_v12327": "v1.23.27 A2 覆盖对账符号化：收敛 amp#N/th#N/probe#N/A{N} 四种编号",
    "_und_self_touch_symbols": "v1.23.27 A2 给「后来被谁按 id 引用」建凭据（符号对账）",
    "_und_self_touch_texts": "v1.23.27 A2 上一条的文本口径镜像（历史 packed 兼容）",
    "touch_rate": "v1.23.27 A3 双读数之一：能力读数（碰没碰过）；property",
    "aspect_carry_rate": "v1.23.27 A3 双读数之二：延续读数（后来还追不追）；property",
    "make_belief_item": "v1.23.27 D1 BeliefItem 的**单一构造点**（四态 + 熵默认 None）",
    "belief_transition": "v1.23.27 D2 迁移规则**纯函数**：resolved > revoked > stable > 保持",
    "semantic_entropy_of": "v1.23.27 D3 语义熵：单链聚类到簇代表，n<2 返回 None",
    "probe_information_gain": "v1.23.27 E1 EIG 可计算化：G = (h_before-h_after)/h_before",
    "select_probe_focus_submodular": "v1.23.27 E2 子模贪心批选（宁少勿滥，G < floor 停手）",
    "belief_status_counts": "v1.23.27 D1 四态计数（可观测量出口）",
    "note_probe_stop": "v1.23.27 E6 停止信号留痕（只留痕，不拦不改行为）",
    "e6_stop_verdict": "v1.23.27 E6 纯函数：由 seen/max_gain/min_gain/stop_floor 判停",
    "_e6_note_stop": "v1.23.27 E6 记录一条停止信号的内部实现",
    "_raw_entropy": "v1.23.27 E1 未决集合的**原始**语义熵 -Σp·ln p（不归一化）",
    # ── v1.23.28 收尾核查 + 接线修复 ──
    "upsert_belief": "v1.23.28 D1/D2 信念条目登记 + 四态迁移（登记与去重解耦）",
    "refresh_belief_entropy": "v1.23.28 D3 刷新所有条目的 semantic_entropy（唯一调用点）",
    # ── 更早遗留（本轮一并登记）──
    "_record_web_hits": "web_search 命中记录（W# 编号与配额）",
    "_scan": "锚点目录扫描的内部实现（白名单扩展名）",
    "_vp_preview": "View 预览渲染（调试用）",
}


def main():
    d = json.loads(REG.read_text(encoding="utf-8"))
    reg = d["registry"]
    _before = len(reg)
    _added = 0
    for k, v in NEW.items():
        if v is None:
            continue
        if k in reg:
            continue
        reg[k] = {"phase": "v12326-28", "reason": v}
        _added += 1
    d["registry"] = reg
    d["current"] = "元DGTF-V1.23.28.py"
    d["added"] = len(reg)
    # ★ 键序稳定：按字母排序写出（便于逐版 diff）
    d["registry"] = {k: reg[k] for k in sorted(reg)}
    REG.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    print("registry %d -> %d (+%d)" % (_before, len(reg), _added))


if __name__ == "__main__":
    main()

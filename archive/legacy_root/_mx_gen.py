"""mode × rounds × thinking 析因批：任务清单生成器（含预注册）。

★ 为什么是「析因」而不是「混着跑」：把三个因子塞进一批里，如果排布是随机的，
  事后分不清差异来自 mode、rounds 还是 thinking —— 那不如分三批。
  做成**完全交叉 + 随机化顺序**的设计，主效应才分离得出来，交互也算得出来，
  还能避免「跑得早的都在某一档」的时间混杂（本项目自己的教训：
  配置 sympathies 改成矩阵形式也可能随时间漂移）。

设计：
  因子 A  mode     : A（我们的默认） / B（planner 偏好，§7.17⑦ 的嫌疑来源）
  因子 B  rounds   : 5 / 0:6,1:5,both:5,all:5（planner 常给的那组）
  因子 C  thinking : T0 现行（普通关 / reasoner 开） / T1 全关
  区组    question : 欧盟AI法案 / IPv6 / TLS —— 三道**已有预注册事实清单**的题
  固定    route    : full（0,1,both,all）—— 本轮不碰层数这个因子

单元数 2×2×2 = 8；每单元 3 个观测（三道题各一次）= 24 跑。
★ 用「三道不同的题」而不是「同一题跑 3 次」当重复：
  既拿到重复观测（估方差），又让结论跨题成立。这是随机区组设计。

产出：
  mx_design_batch01.md   ← 预注册（预计跑之前就写死判据）
  mx_batch01.txt         ← _run_parallel_batch.py --task-file 用的任务清单
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 2026100203          # 随机化顺序的种子，写死以便复现这一次的执行顺序

QUESTIONS = {
    "eu": "欧盟《人工智能法案》对高风险 AI 系统规定了哪些主要义务？",
    "ip": "IPv6 相比 IPv4 到底改了什么？",
    "tls": "TLS 1.3 相比 TLS 1.2 做了哪些关键改动？",
}

MODES = {"A": "A", "B": "B"}
ROUNDS = {"r5": "5", "r6555": "0:6,1:5,both:5,all:5"}
THINK = {
    # T0 = 现（迁移后）默认：普通调用非思考，仅 ing/view 两处开思考
    "t0": "default=disabled,reasoner=enabled",
    # T1 = 全程不开思考。若质量不降而调用/token 降，则 thinking 不值这个价
    "t1": "default=disabled,reasoner=disabled",
}

cells = []
for m in MODES:
    for rc, rv in ROUNDS.items():
        for tc, tv in THINK.items():
            for qk, q in QUESTIONS.items():
                tag = f"mx_{qk}_{m}_{rc}_{tc}"
                cells.append({
                    "tag": tag, "mode": m, "rounds_r": rc, "rounds": rv,
                    "thinking_a": tc, "thinking": tv,
                    "question_k": qk, "question": q,
                })

rng = random.Random(SEED)
order = cells[:]
rng.shuffle(order)

# ---------- 任务清单 ----------
lines = [
    "# mx batch01 —— mode × rounds × thinking 完全析因，顺序已随机化",
    "# 生成：_mx_gen.py（seed=%d）；共 %d 跑" % (SEED, len(order)),
    "# 格式：[V60_THINKING=...|]<mode> <rounds> <tag> <question>",
    "",
]
for c in order:
    head = f"V60_THINKING={c['thinking']}"
    lines.append(f"{head}|{c['mode']} {c['rounds']} {c['tag']} {c['question']}")
(HERE / "mx_batch01.txt").write_text("\n".join(lines) + "\n",
                                     encoding="utf-8")

# ---------- 预注册 ----------
design = {
    "生成时间": "2026-10-02",
    "种子": SEED,
    "设计": "2(mode) × 2(rounds) × 2(thinking) 完全析因 + 3 题随机区组",
    "单元数": 8,
    "总跑数": len(order),
    "固定量": {
        "route": "full（0,1,both,all）—— 本轮不碰层数",
        "cost_profile": "跟随 yaml 默认 balanced",
        "模型": "deepseek-flash（显式 ID，见 §7.18 迁移）",
    },
    "为什么每单元 3 个观测而不是 1 个": [
        "本项目已 6 次栽在「单点观测→写规则」上。",
        "3 个观测才能估组内极差；结论要跨得过组内极差才配成立。",
        "用三道不同题而不是同题 3 次：既拿到重复观测，又让结论跨题成立。",
    ],
    "主结局（成本）": {
        "指标": "llm_calls + llm_tokens（日志尾部既有字段）",
        "判据": "某因子两水平的中位数差 < 10% → 判定该因子不构成主成本旋钮",
    },
    "次结局（质量）": {
        "指标": "_fact_checklists.json 预注册清单的命中条数",
        "工具": "_fact_audit.py（等长截断 + 盲评，已有验证）",
        "判据": [
            "质量差必须 > 组内极差才许断言；",
            "若 thinking 两档命中率差 ≤1 条而 calls/token 差 >10%，"
            "判 T1（全关）更划算；",
            "开放题形态维度本轮不测（低功率 faith 稳定性尚未建立）。",
        ],
    },
    "交互项": "只在主效应达到判据时才解释，不做事后挖掘；"
              "任何事后发现的模式必须在下一批预注册验证，不许直接写进规则。",
    "执行顺序": "随机化（种子已写死），避免跑得早的集中在某一档造成时间混杂。",
    "单元定义": [
        {k: v for k, v in c.items() if k != "question"} for c in order
    ],
}
(HERE / "mx_design_batch01.md").write_text(
    "# mx batch01 预注册（跑之前写死，跑完之后不许改判据）\n\n```json\n"
    + json.dumps(design, ensure_ascii=False, indent=2)
    + "\n```\n", encoding="utf-8")

print(f"任务清单：mx_batch01.txt（{len(order)} 跑）")
print(f"预注册：mx_design_batch01.md")
print("\n各臂跑数：")
cnt = {}
for c in order:
    cnt[(c["mode"], c["rounds_r"], c["thinking_a"])] = \
        cnt.get((c["mode"], c["rounds_r"], c["thinking_a"]), 0) + 1
for k in sorted(cnt):
    print(f"  mode={k[0]:2s} rounds={k[1]:6s} thinking={k[2]:3s} -> {cnt[k]} 跑")
print("\n前 6 行任务：")
print("\n".join(lines[3:9]))

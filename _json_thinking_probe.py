# -*- coding: utf-8 -*-
"""判定环节能不能开思考 —— 先测掉那个硬约束。

核心风险：生产代码在思考模式下**不发 response_format**（见
LLM.call:4938-4941），JSON 只能靠 prompt 约束。而 18 个判定/规划类
调用点 100% 是 JSON 输出。所以「给判定环节开思考」的前提是：
思考模式下的 JSON 仍然可靠。

测什么（用生产的真实 schema）：
  - json.loads 成功率
  - 结构完整率（judgments 条数对、每条 6 字段齐、取值合法）
  - output tokens（成本）

模型可用 PROBE_MODEL 覆盖；flash 故障时默认退到 v4-pro，
但要注意 v4-pro 的数不能外推成 flash 的数（只测机制，不测定量）。
"""
import os
import re
import json
import statistics

env = {}
for ln in open('.env', 'r', encoding='utf-8'):
    m = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)', ln)
    if m and not ln.strip().startswith('#'):
        env[m.group(1)] = m.group(2).strip().strip('"').strip("'")

import openai

cli = openai.OpenAI(api_key=env['DGTF_API_KEY'],
                    base_url=env.get('DGTF_BASE_URL'), timeout=180)
MODEL = os.environ.get('PROBE_MODEL', 'deepseek-flash').strip()
REPS = int(os.environ.get('PROBE_REPS', '5'))

# 生产 _dual_judge 的真实 schema（元DGTF-V1.21.61.py:6105）
SCHEMA = ('{"judgments":[{"idx":1,"yin":"0|1|both","yang":"0|1|both",'
          '"attribute":"0|1|both","position":"0|1|both",'
          '"why_attribute":"≤30字","why_position":"≤30字"}]}')

SYSTEM = (
    "你是【对偶判断者】。\n"
    "四个维度**独立作答**：从阴看、从阳看、属性、位置，\n"
    "不要回看前一个答案去迁就后一个。\n"
    "不一致是常态，不是错误。\n"
    "both 只在真的看不出偏向时才用；\n"
    "不要为了省事把两端都填 both，那是逃避判断。\n"
    "严格 JSON：\n" + SCHEMA
)

USER = """【处境】
一个团队在做产品设计时，应该在多大程度上让用户参与决策？

【候选列表】
[1] 让用户充分参与需求定义，能显著提升最终满意度
[2] 由专业团队独立决策，才能保证方案的工程可行性
[3] 让用户参与创意发散，但由团队收敛到可落地方案
[4] 用户参与度越高越好，不需要设边界
[5] 完全不听取用户意见，避免需求蔓延

请逐条判断。"""

ARMS = [
    ("非思考", {'thinking': {'type': 'disabled'}}, True),
    ("思考",   {'thinking': {'type': 'enabled', 'effort': 'low'}}, False),
]
FIELDS = ["idx", "yin", "yang", "attribute", "position",
          "why_attribute", "why_position"]
LEGAL = {"0", "1", "both"}
N_EXPECT = 5


def check(txt):
    """返回 (能否 json.loads, 结构是否完整, 备注)"""
    try:
        obj = json.loads(txt)
    except Exception:
        # 生产里有 parse_json 兜底，这里也试一次「抠出首个 {...}」
        m = re.search(r'\{.*\}', txt or '', re.S)
        if not m:
            return False, False, "无 JSON"
        try:
            obj = json.loads(m.group(0))
        except Exception as e:
            return False, False, f"解析失败 {type(e).__name__}"
    js = obj.get("judgments")
    if not isinstance(js, list):
        return True, False, "judgments 不是数组"
    if len(js) != N_EXPECT:
        return True, False, f"条数 {len(js)}≠{N_EXPECT}"
    for it in js:
        if not isinstance(it, dict):
            return True, False, "条目不是对象"
        miss = [f for f in FIELDS if f not in it]
        if miss:
            return True, False, f"缺字段 {miss}"
        for k in ("yin", "yang", "attribute", "position"):
            if str(it[k]).strip() not in LEGAL:
                return True, False, f"{k} 取值非法 {it[k]!r}"
    return True, True, "OK"


print(f"模型={MODEL}  每档 {REPS} 次\n", flush=True)
print(f"{'档位':<8}{'可解析':<10}{'结构完整':<10}{'output中位':<12}失败原因")
print("-" * 66)
for label, extra, use_fmt in ARMS:
    ok_p, ok_s, outs, why = 0, 0, [], []
    for _ in range(REPS):
        kw = dict(model=MODEL,
                  messages=[{"role": "system", "content": SYSTEM},
                            {"role": "user", "content": USER}],
                  max_tokens=32000 if "enabled" in str(extra) else 3000,
                  extra_body=extra)
        if use_fmt:
            kw["response_format"] = {"type": "json_object"}
        else:
            kw["messages"][0]["content"] += \
                "\n\n【重要】只输出一个合法 JSON 对象。"
        try:
            r = cli.chat.completions.create(**kw)
            raw = (r.choices[0].message.content or "").strip()
            u = r.usage
            outs.append(getattr(u, 'completion_tokens', 0) or 0)
            p, s, note = check(raw)
            ok_p += p
            ok_s += s
            if not s:
                why.append(note)
        except Exception as e:
            why.append(f"{type(e).__name__}")
    mo = statistics.median(outs) if outs else 0
    print(f"{label:<8}{ok_p}/{REPS:<8}{ok_s}/{REPS:<8}{mo:<12}"
          f"{'; '.join(why[:3])}")
print("-" * 66)
print("★ 判据：思考档的『结构完整率』必须与非思考档持平（差 ≤1 次），"
      "才谈得上给判定环节开思考。")

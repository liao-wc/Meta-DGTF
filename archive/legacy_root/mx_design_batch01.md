# mx batch01 预注册（跑之前写死，跑完之后不许改判据）

```json
{
  "生成时间": "2026-10-02",
  "种子": 2026100203,
  "设计": "2(mode) × 2(rounds) × 2(thinking) 完全析因 + 3 题随机区组",
  "单元数": 8,
  "总跑数": 24,
  "固定量": {
    "route": "full（0,1,both,all）—— 本轮不碰层数",
    "cost_profile": "跟随 yaml 默认 balanced",
    "模型": "deepseek-flash（显式 ID，见 §7.18 迁移）"
  },
  "为什么每单元 3 个观测而不是 1 个": [
    "本项目已 6 次栽在「单点观测→写规则」上。",
    "3 个观测才能估组内极差；结论要跨得过组内极差才配成立。",
    "用三道不同题而不是同题 3 次：既拿到重复观测，又让结论跨题成立。"
  ],
  "主结局（成本）": {
    "指标": "llm_calls + llm_tokens（日志尾部既有字段）",
    "判据": "某因子两水平的中位数差 < 10% → 判定该因子不构成主成本旋钮"
  },
  "次结局（质量）": {
    "指标": "_fact_checklists.json 预注册清单的命中条数",
    "工具": "_fact_audit.py（等长截断 + 盲评，已有验证）",
    "判据": [
      "质量差必须 > 组内极差才许断言；",
      "若 thinking 两档命中率差 ≤1 条而 calls/token 差 >10%，判 T1（全关）更划算；",
      "开放题形态维度本轮不测（低功率 faith 稳定性尚未建立）。"
    ]
  },
  "交互项": "只在主效应达到判据时才解释，不做事后挖掘；任何事后发现的模式必须在下一批预注册验证，不许直接写进规则。",
  "执行顺序": "随机化（种子已写死），避免跑得早的集中在某一档造成时间混杂。",
  "单元定义": [
    {
      "tag": "mx_tls_B_r5_t0",
      "mode": "B",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "tls"
    },
    {
      "tag": "mx_eu_B_r6555_t0",
      "mode": "B",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "eu"
    },
    {
      "tag": "mx_ip_A_r6555_t0",
      "mode": "A",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "ip"
    },
    {
      "tag": "mx_tls_B_r6555_t0",
      "mode": "B",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "tls"
    },
    {
      "tag": "mx_ip_B_r5_t1",
      "mode": "B",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "ip"
    },
    {
      "tag": "mx_tls_A_r6555_t0",
      "mode": "A",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "tls"
    },
    {
      "tag": "mx_tls_A_r5_t0",
      "mode": "A",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "tls"
    },
    {
      "tag": "mx_tls_A_r5_t1",
      "mode": "A",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "tls"
    },
    {
      "tag": "mx_ip_B_r6555_t1",
      "mode": "B",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "ip"
    },
    {
      "tag": "mx_tls_B_r6555_t1",
      "mode": "B",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "tls"
    },
    {
      "tag": "mx_eu_B_r5_t1",
      "mode": "B",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "eu"
    },
    {
      "tag": "mx_eu_A_r6555_t1",
      "mode": "A",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "eu"
    },
    {
      "tag": "mx_tls_A_r6555_t1",
      "mode": "A",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "tls"
    },
    {
      "tag": "mx_ip_B_r6555_t0",
      "mode": "B",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "ip"
    },
    {
      "tag": "mx_ip_A_r6555_t1",
      "mode": "A",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "ip"
    },
    {
      "tag": "mx_eu_B_r5_t0",
      "mode": "B",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "eu"
    },
    {
      "tag": "mx_eu_A_r6555_t0",
      "mode": "A",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "eu"
    },
    {
      "tag": "mx_eu_B_r6555_t1",
      "mode": "B",
      "rounds_r": "r6555",
      "rounds": "0:6,1:5,both:5,all:5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "eu"
    },
    {
      "tag": "mx_eu_A_r5_t0",
      "mode": "A",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "eu"
    },
    {
      "tag": "mx_tls_B_r5_t1",
      "mode": "B",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "tls"
    },
    {
      "tag": "mx_ip_A_r5_t0",
      "mode": "A",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "ip"
    },
    {
      "tag": "mx_ip_B_r5_t0",
      "mode": "B",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t0",
      "thinking": "default=disabled,reasoner=enabled",
      "question_k": "ip"
    },
    {
      "tag": "mx_ip_A_r5_t1",
      "mode": "A",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "ip"
    },
    {
      "tag": "mx_eu_A_r5_t1",
      "mode": "A",
      "rounds_r": "r5",
      "rounds": "5",
      "thinking_a": "t1",
      "thinking": "default=disabled,reasoner=disabled",
      "question_k": "eu"
    }
  ]
}
```

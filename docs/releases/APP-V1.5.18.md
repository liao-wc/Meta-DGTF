# APP V1.5.18 发布说明

## 主题

事实答案显示门兜底 + 本地模型自动候选。

## 改动

- 质量 API 对旧 packed 也按 evidence gaps 重新计算 answer_quality，未核实事实不再回显无关网页文本。
- 自动帕累托候选新增 local_model；启动实测 last_strategy=local_model。
- 版本/静态资源 1.5.18。

## 验证

- fast_gate 12/0；selftest 371/0；依赖审计 78/0。
- 自动帕累托启动实测 last_strategy=local_model；真实跑质量 API 正确显示 needs_evidence。

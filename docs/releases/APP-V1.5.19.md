# APP V1.5.19 发布说明

## 主题

答案摘要显示门兜底：URL 类问题无 URL 不回答。

## 改动

- 质量 API 对 base URL/接口地址类问题要求答案包含可核对 URL，否则降级 needs_evidence。
- 事实题 needs_evidence 统一不显示历史无关文本。
- 版本/静态资源 1.5.19。

## 验证

- fast_gate 12/0；selftest 371/0；依赖审计 78/0。
- base URL 真实跑质量 API：process_ready=true/4 层达标，answer_quality 被 URL 门降为 needs_evidence。

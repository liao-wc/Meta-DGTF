# ab_results.jsonl 字段说明（2026-10-27）

- `tag`：跑次标签（历史上有 1 个重复：`v95-dual-local`，保留原样不改写）；
- `quality` / `answer_quality` / `answer_ready`：质量读数字段；
- `tokens` / `calls` / `wall_s`：token、调用数、墙钟；
- `cost_window_cny` / `cost_attribution` / `cost_note`：成本**窗口差**口径（不可归因），
  Round 101 之后新增；**旧行（97/145）缺失该字段属历史 schema**，不得求和归因；
- `config` / `preset` / `question` / `note`：配置与题面元信息。

> 新增跑次必须带 cost 三字段；历史行保持原样（不改写证据）。

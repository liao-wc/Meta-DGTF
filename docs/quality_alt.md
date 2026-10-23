# 质量替代分（三态 α 不可靠时）

## 问题

当前真跑 `tri_state=[0,0]`、Krippendorff α=0，`tri_quality=unmeasured`；不能把三态当质量。

## 替代公式

```text
score = 100 × coverage × answer_rate
        × (0.7 + 0.3 × closure)
        − 6 × len(flags)
```

- coverage：packed.quality.coverage；
- answer_rate：answered / answerable_total；
- closure：非 token/预算/截断收尾的层占比；
- flags：duty_short、probe_link_dangling 等；
- grade：A≥85 / B≥70 / C≥55 / D。

## 接口

`GET /api/quality/<task_id>` → score/grade/basis/tri_state/tri_quality。

## 示例

任务 20261021_155104_950be7：coverage 0.9766、answered 4/4、closure 1.0、flags 2 → 78.34 B。

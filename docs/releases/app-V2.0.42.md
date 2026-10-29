# App V2.0.42 发布说明

发布日期：2026-10-29

上一版：App 2.0.41

## 主题

任务归档保留超时/停滞标志，修复超时不可诊断。

## 改动

- run.json 新增 timeout / stalled / cancelled。
- 1200s 总超时任务不再只显示 error。
- 不改变执行逻辑。

## 验证

- App 全方位检查
- App 版本一致性
- App selftest
- fast_gate

## 静态缓存

`2.0.42-timeoutmeta`

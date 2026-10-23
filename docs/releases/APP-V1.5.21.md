# APP V1.5.21 发布说明

## 主题

关键状态原子写 + scratch 清理。

## 改动

- 提案与调度策略 JSON 改为临时文件 + os.replace 原子写，降低中断半截 JSON 风险。
- 清理 _audit_tmp / smoke_outputs 生成型 scratch，释放约 3.5GB；源码/产物未动。
- 版本/静态资源 1.5.21。

## 验证

- fast_gate 12/0；selftest 371/0；依赖审计 78/0。
- 清理 scratch 约 3.5GB；原子写已接提案/策略。

# 提案确认与执行完成报告

日期：2026-10-28T18:05:00+08:00
App：2.0.41
状态：全部人工确认项已处理，无 pending/confirmed

## 一、执行摘要

用户确认“全部执行”后，处理了此前 8 条人工确认项：

| 提案 | 结论 |
|---|---|
| prop-manual-7778e2e864 G5 入学年龄 | superseded，precheck G5 PASS |
| prop-manual-b87b7ab32d 真跑超时 | applied，2.0.40/2.0.41 双层超时治理 |
| prop-audit-08bec79a8c 产物质量 | superseded，保留 needs_evidence，不伪装 verified |
| prop-audit-b76c48149b 异常 run | superseded，历史遗留，不自动重跑/删除 |
| prop-audit-ecf787090a 配对缺口 | superseded，旧格式/中间产物，不重建/移动 |
| prop-audit-026c5489a4 重复题 | superseded，人工重跑/旧格式，不激进收紧缓存 |
| prop-manual-34380d7d77 DeepSeek Search/Fetch | superseded，评估后暂不接入，无凭据 |
| prop-manual-0c7a7e94b2 CADF A/B | superseded，评估后暂不线上裁剪 |

## 二、代码改动

### App 2.0.39

- 移除 pending 24h / confirmed 72h 自动过期。
- 恢复被静默过期的确认项。

提交：df01a82

### App 2.0.40

- DGTF_TASK_TIMEOUT_S 默认 3600s → 1200s。

提交：659ea32

### App 2.0.41

- engine_runner 增加停滞看门狗 DGTF_TASK_STALL_S=600s。
- 日志 600s 无增长判定停滞并终止。
- 与 1200s 总超时形成双层保护。

提交：34294cd

## 三、最终提案状态

```text
pending：0
confirmed：0
active：0
```

最新计数：

```text
expired：156（历史已过期）
superseded：25
rejected：12
applied：7
failed：4
rolled_back：1
```

## 四、验证

```text
App：2.0.41
App 全方位检查：PASS
App 版本一致性：PASS
App selftest：PASS 455 / 0
fast_gate：PASS 16 / 0
outputs_library_audit：完成
```

## 五、未删除/未伪造

- 未删除历史产物、历史提案或 run 记录。
- 未把 needs_evidence 改成 verified。
- 未执行 git push。
- DeepSeek Search/Fetch 未读取/外发密钥；未接入。
- CADF 未做未验证的线上裁剪。

## 六、剩余风险

- precheck 当前 G4 判定审计仍 FAIL（存证 mixed vs 重算 verified）；这是 G5 之外的新缺口，需另行修复。
- 旧产物 516 条 md 无 packed 属历史格式，保留可读性，不自动重建。
- 50 组重复题保留，避免错题复用。
- 异常 run 不自动重跑。

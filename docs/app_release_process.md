# App 发布流程与硬门禁

目标：每次 App 代码/界面变更都同步版本、文档、发布说明和验证门禁，禁止“改一处漏一处”。

## 1. 唯一发布入口

```bash
python scripts/app_release.py --version <new> --cache-tag <cache-tag>
```

自动更新：

- APP_VERSION
- static/index.html 静态缓存串
- README / dgtf_app/README / PROJECT_LAYOUT
- dgtf_engine/dgtf_v2/NAMING.md
- docs/index.html

人工补充：

- docs/releases/app-V<new>.md
- CHANGELOG.md 的 App <new> 段
- 发布说明内容、验证结果、风险

## 2. 本地提交硬门禁

安装：

```bash
python scripts/install_git_hooks.py
```

`.githooks/pre-commit` 会：

1. 检查 staged 的 App 运行时文件是否变更；
2. App 运行时变更必须让 APP_VERSION 相对 HEAD 变化；
3. 必须有 docs/releases/app-V<新版本>.md；
4. CHANGELOG 必须包含新版本；
5. 运行 app_version_check.py；
6. 运行 file_integrity_check.py。

任一项失败，commit 被拒绝。

注意：`git commit --no-verify` 可以绕过本地钩子，因此 CI 和守卫回执门禁是第二层。

## 3. App 检查门禁

`scripts/app_full_check.py` 包含：

- App 版本一致性
- 关键文件完整性
- 静态缓存串一致
- App API/health/selftest 相关检查

## 4. 守卫回执硬门禁

`scripts/guard_receipt.py` 在写 completed 回执前独立复核：

- app_version_check.py
- file_integrity_check.py
- 巡检报告存在且 check_patrol_report.py PASS
- app_audit_latest / outputs_audit_latest / system_audit_latest 存在且不超过 6 小时
- App 审计无硬失败

不通过时不写回执，守卫状态保持 pending_completion。

## 5. CI 门禁

`.github/workflows/ci.yml` 在 app job 中运行：

- app_version_check.py
- file_integrity_check.py

CI 失败禁止合并。

## 6. 标准流程

```text
改 App
→ app_release.py bump
→ 写发布说明 / CHANGELOG
→ app_version_check
→ app_full_check
→ fast_gate / V2 tests / selftest
→ pre-commit hook
→ 本地 commit
→ CI
→ 守卫回执
```

## 7. 不可绕过的边界

本地 hook 可以被 `--no-verify` 绕过；真正的外部保证依赖：

- 受保护分支 + CI required checks；
- 只允许通过 PR 合并；
- 守卫回执独立复核。


## 8. 回归保障矩阵

| 改动区域 | 必须运行的回归 |
|---|---|
| dgtf_app/server.py / API | app_full_check、App selftest、对应接口 smoke |
| dgtf_app/static/app.js、index.html、style.css | node --check、App 页面手动 smoke、模式切换/灯状态检查 |
| dgtf_engine/ | fast_gate、V2 全量 tests、必要真跑 |
| 版本/README/NAMING/发布说明 | app_version_check |
| 文件写入/回退工具 | safe_file_ops 回滚测试、file_integrity_check |
| 守卫/回执 | guard_policy_check、guard_receipt 门禁测试 |

### 自动门禁

- fast_gate：12 项机制门禁；
- V2 tests：51 文件、835 checks；
- App selftest：444 项；
- app_full_check：API/安全/静态/版本/完整性；
- dependency audit：路径与依赖；
- pre-commit：App/engine 改动自动跑 fast_gate；
- CI：fast_gate + V2 tests + 版本/完整性。

### 当前缺口

浏览器 UI 行为（模式切换、灯状态、抽屉/按钮）没有自动化浏览器测试。
当前只能依靠：

- node --check；
- 静态结构与 ID 检查；
- 发布前手动 UI smoke；
- 修改前后对照截图/记录。

这是目前“功能不回归”保证里最薄的一层，后续应补 Playwright/jsdom 级别 UI 回归。

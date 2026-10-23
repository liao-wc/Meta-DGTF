# 元DGTF 开源安全收尾报告

日期：2026-10-23
仓库：https://github.com/liao-wc/meta-dgtf
门户：https://liao-wc.github.io/meta-dgtf/

## 1. 结论

公开仓库的开源安全基础工作已完成：

- 公开可见性：Public
- 许可证：MIT
- 历史：重建为干净基线，移除归档、历史版本和运行态数据
- 漏洞扫描：CodeQL 已配置；当前 open 告警 0，37 条已分类处置
- Secret scanning：open 告警 0
- Dependabot alerts：open 告警 0
- Actions：全部固定 commit SHA，开启 SHA pinning
- 分支保护：禁止强推/删除，required checks + conversation resolution
- 发布：release-artifact 生成 SHA256SUMS
- 文档：SECURITY / PRIVACY / THIRD_PARTY_NOTICES / GOVERNANCE / 依赖与模型安全

## 2. 代码与仓库清理

- 从公开树移除 archive/、runs/、旧引擎版本、_bak/_mut/_chk 历史文件。
- 本地 archive 目录保留，但已加入 .gitignore，不进入 Git。
- Git 历史重建为干净基线，并删除旧分支、旧标签、旧 Release 和旧 Actions 运行记录。
- 当前只保留 main 分支和两个版本标签：
    app-v1.5.24
    engine-v1.30.4

## 3. 安全配置

已启用：

- Secret scanning
- Push protection
- Private Vulnerability Reporting
- CodeQL 默认扫描
- Dependabot security updates
- Dependabot pip + GitHub Actions 更新
- Actions SHA pinning
- Branch protection：
    main 禁止强推
    main 禁止删除
    required checks: app / engine / local-model / dependency-review
    required conversation resolution

## 4. CodeQL 告警处置

初始扫描结果：

- 117 open
- 108 high
- 9 medium

移除旧版本/归档后：

- 47 open
- 44 high
- 3 medium

代码修复后：

- 37 open
- 35 path-injection
- 1 URL 测试断言
- 1 PDF ReDoS

处置结果：

- 35 条 path-injection：经代码复核，路径组件已通过 _safe_id/os.path.basename 归一化，并限制在固定项目目录；标记 false positive。
- 1 条 URL 测试断言：位于 tests_evidence，标记 used in tests。
- 1 条 PDF ReDoS：PDF 内容流扫描窗口已限制为 4 MB，标记 bounded/ won't fix，后续可继续重构。
- 当前 CodeQL open：0

说明：dismiss 不等于代码永不复发。后续修改路径或解析逻辑后，CodeQL 可能重新提示，需要继续复核。

## 5. 代码修复

- dgtf_app/server.py：
  - 新增 _safe_id/_safe_basename/_header_safe
  - 会话/提案/DSH 产物 ID 归一化
  - 静态资源只取 basename
  - PDF 文件名只取 basename
  - Content-Disposition / Content-Type 去 CRLF
- 元DGTF-V1.30.4.py：
  - 搜索失败日志不再打印 query 原文，仅记录长度
  - DeepSeek 文档 URL 改为 hostname 精确校验
- dgtf_v2/input_sanity.py、agent_bridge.py：
  - URL 主机名校验替代子串匹配
- dgtf_app/docparse.py：
  - 去掉空白归一正则
  - GIF 注释改为线性扫描
  - PDF 扫描窗口限制 4 MB
- dgtf_app/library.py、outputs_index.py、engine_runner.py：
  - 文件名统一 os.path.basename
- 测试断言：仅用于测试的 URL 子串断言已标注为测试用途。

## 6. 文档与合规

新增：

- LICENSE：MIT
- SECURITY.md：漏洞报告、支持版本、禁止公开内容
- THIRD_PARTY_NOTICES.md：模型与依赖许可证提示
- docs/PRIVACY.md：本地数据边界、删除方式、联网说明
- docs/OPEN_SOURCE_GOVERNANCE.md：维护、发布、安全响应
- docs/dependency_security.md：依赖与模型加载安全
- docs/security_hardening.md：公开仓库安全说明
- local_model/MODEL_SOURCES.md：模型来源与校验方法
- requirements-local-model.txt：本地 BGE 服务依赖固定版本

模型权重仍未随仓库分发；模型许可证以各上游 model card 为准。

## 7. 验证

- git 工作区：干净
- 当前 main：c85c0cbbf4062f3d2bb3d34167d5d4dbbd0c6a8e
- fast_gate：PASS 12 / FAIL 0
- selftest：PASS 371 / FAIL 0
- py_compile：通过
- App health：HTTP 200，App 1.5.24，Engine 1.30.4
- Pages：已部署，HTTP 200
- CI：success
- repo-classification：success
- Secret scanning open：0
- Dependabot alerts open：0

## 8. 仍需你确认或后续处理

1. 当前仓库有 5 个 Dependabot GitHub Actions 升级 PR，建议逐个 review 后合并或关闭。
2. MIT 是本次选择的代码许可证；如需要专利条款，可改 Apache-2.0。
3. 上游模型许可证需按实际下载的 model card 最终确认。
4. 实际模型权重 SHA256 尚未写入清单；MODEL_SOURCES 已给出校验命令。
5. 签名提交、PR 必须审批、SBOM/发布签名属于可选进阶项，当前未强制开启。
6. GitHub Pages 只是静态门户，Python App 后端仍只在本地/自托管运行。

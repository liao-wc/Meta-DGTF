# Meta-DGTF-道生三阶模型 · 版本命名与迭代规范

当前版本：**V2.2.75**（V2.2.14 本地档 few-shot/端点降档 + stage 登记闭环 + 本地链路提速 3.3x；默认行为不变；App 2.0.37）
上一基线：V2.1.0（历史谱系融合）
历史归档：V1.x（dgtf_engine/dgtf_v1/ 与 V1 历史归档）

## 1. 版本号

采用语义化版本：VMAJOR.MINOR.PATCH。

- MAJOR：架构断代或不可回滚的契约变更；
- MINOR：能力融合、新增机制、发布级功能（V2.2.0 属于此项）；
- PATCH：修复、判据补强、文档/依赖同步，不改默认行为。

版本号只增不减；旧版本文件与标签保留，不覆盖历史。

## 2. 当前映射（V2.2.75）

| 对象 | 命名 |
|---|---|
| 生产引擎 | dgtf_engine/dgtf_v2/engine/Meta-DGTF-V2.2.75.py |
| App | 2.0.81（本地链路两段守护 + /api/health local_chain 读数 + 本地档预设 + DSH 视图隔离 + 版本同步门禁 + 安全文件回退 + 产物活动灯） |
| V2 核心 | dgtf_engine/dgtf_v2/ |
| 融合实现 | Meta-DGTF-V2.2.75.py 内联（history + behavior；融合目标版本仍为 2.2.0 谱系） |
| 历史清单 | dgtf_engine/dgtf_v2/history_manifest.json（数据） |
| 单引擎融合判据 | dgtf_engine/dgtf_v2/tests_inline_fusion.py |
| 主版本标签 | V2.2.75 |
| App 发布标签 | app-V2.0.81 |
| Engine 发布标签 | engine-V2.2.75 |
| 发布说明 | docs/releases/V2.2.75.md |
| 收束报告 | V2.2.75-收束报告.md |

## 3. 迭代流程

1. 复制 Meta-DGTF-V<旧版本>.py 为 Meta-DGTF-V<新版本>.py；
2. 升 __version__，只在新版上改；
3. 新增/更新 dgtf_engine/dgtf_v2/tests_*.py；
4. 跑五道门：fast_gate、V2 全量 tests、App selftest、依赖检查、必要真跑；
5. 写 CHANGELOG.md 新段、docs/releases/V<新版本>.md、收束报告；
6. 更新本文件、README、PROJECT_MAP、Pages；
7. 提交、打三标签（V/ app-/ engine-）、发布并核对资产。

## 4. 红线

1. 新增生产文件/发布标签使用 V2 版本号，不再新增 V1 命名。
2. V1 名称只保留在 dgtf_engine/dgtf_v1/、历史归档、回滚引用和 V1-only smoke 中。
3. dgtf_engine/dgtf_v2/ 是 V2 核心包名，保留以兼容已有导入。
4. 版本标签一旦发布不移动、不重写；内容变化用新版本。
5. 行为融合只作用于调度/阈值，不生成或改写答案。
6. 任何“融合”不得改变历史版本的只读归档事实。

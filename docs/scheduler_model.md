# 本地调度模型 V1

## 训练

用带 numpy 的 Python 执行：

    python train_scheduler_model.py

数据：EML/V2 schedule_outcome + packed question/bucket/qlen/rounds。
按 run_id 分组切分训练/留出，避免同题泄漏。

模型：template one-hot + bucket one-hot + rounds + qlen_z 的岭回归。
权重保存：models/scheduler_model_v1.json。

## 当前指标

- rows 377 / runs 120；
- quality 留出 MAE 0.086，基线 0.149；R² 0.307；
- log tokens 留出 R² 为负，应用时 token 用经验均值，不采用 token 模型。

## 应用

- GET /api/schedule/model
- GET /api/schedule/model/predict?q=...
- POST /api/schedule/model/apply
- UI：V2 面板“采用学习模型”

## 边界

这是 app 侧本地调度小模型，不是 LLM fine-tune。
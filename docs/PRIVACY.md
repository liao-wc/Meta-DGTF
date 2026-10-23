# Privacy

## 数据边界

元DGTF 是本地优先项目，不包含遥测或后台上传。

本地运行数据默认位于：

    dgtf_memory/
    outputs/
    runs/
    cache/
    dgtf_app/runs/

这些目录已从公开仓库排除，并加入 .gitignore。

## 数据可能包含

- 用户问题与对话
- 引擎推理过程与产物
- 知识库条目
- 本地文件上传内容
- 运行日志与错误栈
- 访问令牌/CSRF 令牌
- 模型的本地输出

## 网络访问

- 本地模型推理默认不联网。
- 联网检索/API 只在用户配置并启用时发生。
- 外部检索结果属于第三方内容，不保证准确或可再分发。
- 启用外部模型 API 时，输入内容会发送给该服务商，需自行确认其隐私条款。

## GitHub Pages

公开的 GitHub Pages 只是静态项目门户，不运行 Python 后端，不收集用户数据。

## 删除数据

停止 App 后，可删除：

    dgtf_memory/
    outputs/
    runs/
    cache/
    dgtf_app/runs/

删除前请确认没有需要保留的本地任务结果。

## 公开仓库

请勿把 dgtf_memory、outputs、runs、cache、访问口令、TLS 私钥或真实用户数据
提交到 Git 仓库或 Issue/PR。

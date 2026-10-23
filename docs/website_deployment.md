# 网站部署管理

## 当前部署目标

GitHub Desktop 使用的仓库：

```text
https://github.com/liao-wc/Meta-DGTF
```

本地仓库：

```text
D:\Meta-DGTF
```

## DSH 管理命令

DSH 在部署前使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_github.ps1 -CheckOnly
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_github.ps1
```

脚本行为：

1. 只允许 main 分支；
2. 探测可用的 GitHub 443 IP，绕过本机到 github.com 的间歇性连接问题；
3. `git push origin main`；
4. 校验远端 main 与本地 HEAD 一致；
5. 可选 `-PushTags` 推送标签。

不会自动 stage 未提交文件，不会强制推送。

## 运行网站与仓库部署的区别

当前 App 是 Python 后端，运行在：

```text
https://127.0.0.1:8765/
```

GitHub 仓库保存的是源码/版本，不是可执行网站。要让公网访问，需要一台运行该 Python 服务的服务器、容器或隧道；当前没有配置服务器目标，因此只完成源码部署管理。

## 当前部署状态

- 远端 main：`440b600` 之后的新提交由 DSH 用上述脚本负责推送。
- 本地 App 继续运行在 `127.0.0.1:8765`。

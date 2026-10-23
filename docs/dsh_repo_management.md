# DSH 仓库管理

DSH 接管本仓库的日常同步：

- 只管理 `main` 分支；
- 只推送**已经提交**的内容，不自动 stage 工作区；
- 推送前探测可用 GitHub 443 IP，失败自动换 IP；
- 推送后校验远端 main 与本地 HEAD 一致；
- 不强制推送；远端领先或分叉时只记录，不覆盖。

## 安装自动同步钩子

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_repo_hooks.ps1
```

安装后每次本地 commit 会在后台运行：

```text
scripts/dsh_repo_manage.ps1
```

把已提交的 main 推送到 GitHub。

## 手动检查

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dsh_repo_manage.ps1
```

日志：

```text
_repo_manager.log
```

## 边界

- `dgtf_memory/` 等运行态文件的未提交修改不会被自动提交/推送。
- 自动同步只做 fast-forward 推送；不解决历史分叉。
- 公网网站运行仍需服务器/隧道目标。


## 定时重试

已注册 Windows 计划任务：

```text
DSH-MetaDGTF-RepoSync
每 5 分钟
```

即使某次网络断开，计划任务会继续重试推送已提交的 main。手动运行一次：

```powershell
schtasks.exe /Run /TN "DSH-MetaDGTF-RepoSync"
```

查看日志：

```text
_repo_manager.log
```

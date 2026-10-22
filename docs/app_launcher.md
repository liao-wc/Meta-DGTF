# 元DGTF 启动与访问

## 日常使用

桌面快捷方式：元DGTF

或项目内：

    .\scripts\start_app.cmd

停止：

    .\scripts\stop_app.cmd

## 访问

- 默认 HTTPS：https://127.0.0.1:8765
- 默认使用稳定访问口令，重启后书签仍有效。
- 口令文件：dgtf_memory/.access_token（当前用户可读写，SYSTEM/管理员可管理）
- 重新生成口令：.\scripts\start_app.cmd -Restart -NewToken

## 关闭 / 恢复

停止服务：

    .\scripts\stop_app.cmd

如之前使用过 DGTFApp 隔离账户，管理员执行回退：

    powershell -ExecutionPolicy Bypass -File .\scripts\revert_isolated_service.ps1 -Apply

## 说明

- 当前运行模式：当前 Windows 用户，无 DGTFApp 服务账户/计划任务。
- HTTPS 证书：DGTF Local CA + 服务器叶子，CA 已加入 CurrentUser Root。
- 访问口令：默认启用；静态资源和 API 都需要 token/cookie。
- 相同用户下的恶意进程仍可能读取 token 文件或浏览器 profile；这是同用户边界。

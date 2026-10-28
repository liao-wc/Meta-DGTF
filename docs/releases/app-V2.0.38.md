# App V2.0.38 发布说明

发布日期：2026-10-28

上一版：App 2.0.37

## 主题

修复 App 无法连接当前 DSH Web，恢复 DSH 本对话。

## 根因

- dgtf_memory/dsh_web_url.txt 指向旧端口 53962。
- 当前 DSH Web 实际端口为 53143。
- 旧探测函数先读本地文件、后读 DSH_WEB_URL，导致请求旧端口并报 WinError 10061。

## 修复

- 改为先试环境 DSH_WEB_URL，再试本地文件，最后才试旧端口。
- 探测成功后持久化当前地址。
- /api/dsh/current/messages 恢复 200。

## 验证

- DSH 当前会话消息读取成功
- App 全方位检查
- App 版本一致性
- App selftest
- fast_gate

## 静态缓存

`2.0.38-dshweb`

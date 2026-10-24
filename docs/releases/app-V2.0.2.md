# App V2.0.2 发布说明（补丁）

日期：2026-10-24
类型：PATCH（App；引擎仍为 V2.2.1）

## 修复

1. **「DSH 会话」列表点开正在运行的会话看不到实时内容**：这些 `dsh-current-*` 会话的
   App 侧 turn 记录只有壳（真实内容在 DSH GUI 会话里）。现在点击此类会话直接打开
   「DSH 本对话」整段实时镜像（`full=1`，首屏最近约 200 条 + 700ms 增量 + 载入更早），
   不再停留在「用户 新对话 / DSH Agent 运行中…」。
2. **恢复会话同源问题**：localStorage 里保存的 `dsh-current-*` 不再被当作普通 App
   会话恢复（避免空壳视图），统一交给实时镜像。
3. **「读取全部库」偶发 Failed to fetch**：Agent 面板读库对瞬时网络错误自动重试 1 次；
   最终失败时点名具体库（如「DSH 会话：Failed to fetch」），不再只显示笼统的
   「部分失败：Failed to fetch」。
4. **每个 DSH 会话独立记录**：外部 `dsh-current-*` 会话由服务端按 `start_seq → end_seq`
   （下一会话起点）返回**自身时段**的事件切片；会话列表对同时段重复记录去重；
   打开会话只显示当时那段内容，运行中的会话 600ms 轮询增量刷新，不再混入整段 DSH 会话。

## 验证

- `python -m py_compile dgtf_app/server.py` → 0
- `node --check dgtf_app/static/app.js` → 0
- App 重启后 `/api/health` → ok=true、app=2.0.2、engine=2.2.1
- 首页缓存串 → `?v=2.0.2-dshlive`；`/static/app.js` 已含新分支
- `/api/dsh/chats` 返回 `external=dsh-current` 会话；selftest **PASS 371 / FAIL 0**
- 会话独立性实测：当前会话共 **20 个独立窗口**，**0 条事件越界、0 对窗口重叠**；
  运行中会话 600ms 轮询持续刷新（`ISOLATED=True`）

## 边界

- 不改引擎；会话实时内容仍以 DSH GUI 当前根会话为准（`/api/dsh/current/events?full=1`）。
- 浏览器需刷新一次加载新前端缓存串。

# App V2.0.27 发布说明

发布日期：2026-10-26

上一版：App 2.0.26

## 主题

演练模式侧边栏活动灯语义修正。

## 主要改动

- App 灯：有任务运行时亮蓝。
- 产物灯：有任务运行时亮蓝。
- 联网灯：仅非演练任务显式启用 web 时亮蓝；修复 fused_ground_web 导致的误亮。
- 演练模式不再误亮联网灯；模型灯保持不亮。

## 验证

- 演练任务活动采样：app=true / engine=true / web=false / products=true。
- App 全方位检查 PASS
- App selftest 444/0
- fast_gate 12/12
- V2 tests 51/51（835 checks）

## 静态缓存

`2.0.27-activityfix`

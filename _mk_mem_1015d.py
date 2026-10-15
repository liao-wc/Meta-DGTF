# -*- coding: utf-8 -*-
"""追加 2026-10-15 记忆：副本 V1.23.37（按需协议 + 圈级心跳）+ app 同步。"""
import io, os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".workbuddy", "memory", "2026-10-15.md")
ADD = u"""
---

## 十、★ 分批推进（用户口径：「主文件可以改，但新建副本，等上一次验收完再并入」）

### 冻结与副本
· **验证版 `元DGTF-V1.23.36.py` 冻结**（验收链正在验它）；
· **副本 `元DGTF-V1.23.37.py`**（`cp` + 两处版本号）⇒ 新改动落这里；
· ★ **`smoke_test.py` / `_mut_v12332.py` / `dgtf_config.yaml` 一律不动**
  （它们正被变异体读；判据/变异体的改动用 `WB_SM=1` 开关**压后执行**）。

### 本批两件（都在副本上）
1. **联网按需协议**（`_patch_v12336_webneed.py`）
   · 环节产出里可写 `===WEB-NEED===` + `{"queries": [...]}` ⇒ 引擎**解析 ⇒ 过 Gate
     ⇒ 检索 ⇒ 进池 + 留痕**；
   · **不改任何环节的 prompt/schema**（**可选**协议 ⇒ 不说就零变化）；
   · **本批不回喂**（回喂要在同环节再调一次，成本翻倍）—— 先把「声明被听见并真的去查了」做实；
   · 挂钩点：`LLM.call` 的**成功返回**处（`return content` 之前，L8957）。
2. **心跳 · 圈级**（`_patch_v12337_roundtick.py`）
   · 用**上一圈**的读数调**本圈**（比层级心跳更细）；
   · 跨圈状态：存 `self._round_view`（`MetaDGTF` 实例 ⇒ 跨圈存活），
     ★ **不塞 `Pool`**（避免动 dataclass 字段触发「全字段出口」审计链）；
   · **两处 `view = dg.run(inp)` 各存一行**（serial 通道 + B/C/D-H 通道）；
   · 读点：`_before_round`（**本身就是两处通道共用的**）⇒ 读只需一处。

### ★★ 本批三个坑（都值得记）
1. **锚点撞注释**：`view = dg.run(inp)` 这行在**注释里也出现两次** ⇒ 只用它当锚点
   会命中 **3 处**（断言判红）。**⇒ 锚点一律带上下文**（连上 `dg = DGTF(...)`
   与 `view.rounds_run = …`）。
2. **heredoc 逐层转义不可靠**：想用 `<< 'PYEOF'` 内联改脚本锚点 ⇒ 转义层数算错、
   锚点找不到。**⇒ 改脚本一律用 Write 工具重写**（项目铁律早有此条）。
3. **探针抓到真缺口**：`parse_web_need` 的**降级分支**（JSON 解不出时逐行取）
   写的是 `len(_l) > 2` ⇒ 把**单字查询**（如「丙」）滤掉；
   而这一支存在的意义正是「**环节写了、但格式不标准**」⇒ **更不该丢需求**。
   ⇒ 改为「**只滤 JSON 残渣**（空行 / `queries` 键行 / 纯括号行），不设长度阈值」；
   **同时同步源头补丁脚本**（同一个逻辑两处，否则重建会丢修复）。

### 另一件跨任务：**app 侧同步**（`_patch_v12336_appsyc.py`）
`dgtf_app/params.py` 的 `_KEY_CN`（键名→中文）**缺 55 项**：
25 个 `api.thinking.stages.*`（一直没补）+ 30 个 `web_search.stages.*`（本轮新增）。
（该文件自己的注释就写着判定口径：「`/api/params` 每项的 label 都要含 `（`」。）
⇒ 补齐后**剩余缺口 0**；★ 该文件**换行不纯**（LF/CRLF 混）⇒ **只插新行、不整体归一**。

### 副本验收（零 API）
`_probe_v12337_new.py` **全过**：
· 按需协议：不声明 `[]` / 标准 JSON ✓ / 超量被截到 3 ✓ / 单行 ✓ / 畸形 5 例不抛错 ✓；
· 圈级心跳：连跑两圈 ⇒ 出现 `@r2` 标记的圈级调用 ✓。
"""


def main():
    raw = io.open(P, "rb").read()
    assert raw.count(b"\r\n") == 0, "记忆应为 LF-only"
    s = raw.decode("utf-8")
    if "分批推进" in s and "V1.23.37" in s:
        print("已存在该节"); return
    s = s.rstrip("\n") + "\n" + ADD
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK 记忆已追加；行数 %d" % s.count("\n"))


main()

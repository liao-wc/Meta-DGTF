# -*- coding: utf-8 -*-
"""追加今日记忆第十三节：全局链路核查（四条链路）。"""
import io, os

P = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 ".workbuddy", "memory", "2026-10-14.md")
ADD = u"""
---

## 十三、全局链路核查（用户要求：以全局视角过四条链路）

### ① 自我学习迭代（EML）—— **通**
- 冒烟判据：`OK v1.23.31 经验记忆回路（闸门/只增/双边/遗忘/RRIF/构造性证明会学）全过`。
- 日志实证学习真在发生：`过闸新增 2` / `升级 2` / `用 2 条（生效 1）`。
- 本轮改动对 EML **零影响**（EML 读写都在 `MetaDGTF` 层，不读 `quant_readings`）。

### ② dgtf_app —— **需要更新，已修**（用户问题的实测答案）
- `dgtf_app/selftest.py` 报 **PASS 366 / FAIL 1**：「参数标签统一成『键（中文说明）』」。
- 根因：上一轮引擎新增 `actions.merge_expand`，**app 侧 `_KEY_CN` 中文标签表没同步**
  ⇒ `label_for()` 退化成裸键 ⇒ 判据红。
- ⇒ 又一次「引擎 `DEFAULT_CONFIG` 与 app `_KEY_CN` **各一份键清单** ⇒ 新增键必漏一处」。
- 修（`_patch_v12333_appkey.py`）：① `params.py` 补标签；
  ② ★ 把该判据失败消息改成**报出缺标签的键名**（原来只报总数 ⇒ 排查要自己遍历）。
- 重跑 **PASS 367 / FAIL 0**。
- 另确认：`params.py` 面板**从出厂 yaml 自动扁平化**（不写死键）⇒ 新键自动出现；
  `engine_runner.py` 走 CLI，本轮**没动 CLI 参数** ⇒ 接口兼容。

### ③ 日志显示是否同步 —— **逮到真断点，已修**
| 出口 | 修前 | 修后 |
|---|---|---|
| `to_dict()` → packed JSON | ✓ | ✓ |
| 产物 md 附录（机械 JSON） | ✓（要翻 JSON） | ✓ |
| 产物 md **正文可读段** | **✗** | **✓ 新增** |
| 日志 `vp` | 仅 `collapsed` 告警 | 同（不逐条吵） |
| dgtf_app 展示 | ✗ | ✓（读 md ⇒ 自然可见） |

⇒ 「引擎算了 4 个读数，人类在正文与日志里都看不见」—— 与用户诉求原文
（「ing 的输出内容 / view 的输出重点要有依据」）直接冲突。
★ 第 2 类失败（有值但零信息量）的变体：**有值但没有可读出口**。

修（`_patch_v12333_quantmd.py`）：每层正文尾部加
```
【各环节量化】（零成本读数；缺输入一律不给）
  · 锚点保真度（restate_fidelity）：drifted（coverage=0.0、ratio=0.8、fidelity=0.0）
  · ing 语义密度（ing_density）：ok（value=0.8519、chars=54）
```
★ 三处取舍（都对着已知事故）：**遍历全部键**（不维护渲染清单 ⇒ 新读数自动出现）/
未知键**降级为键名** / **中文标签 + 英文键名都给**（可读 + 可 grep + 附录
字段名覆盖统计不再失真）。

### ④ 链路依赖 —— **无破坏**
- `inp.pool._prev_cand_descs` **不进产物**（`Pool.to_dict()` 是**手工白名单**；
  探针 Q5 实证：产物 JSON 里搜不到该串）。
- `quant_readings` 新键对下游无破坏（冒烟 / `--phase all` / AUDIT 全绿）。
- **三通道**（serial / B / C）落盘层与值**逐字相同** ⇒ 无漂移。
- ★ 确立**下游依赖清单**：`quant_readings` 四个出口 =
  `to_dict()` / 产物正文（新）/ 产物附录 JSON / dgtf_app（经 md）
  ⇒ **新增读数四处都要能看到**。

### 新判据 ㉟ + 新变异体 M55
- **㉟ 可读性**：猴补丁捕获 `_render` 正文，断言含 `【各环节量化】` +
  中文标签「锚点保真度」+ **英文键名** `restate_fidelity`。
  （与 **㉞** **共用同一次 mock run** ⇒ 不拖慢冒烟。）
- **M55**：关掉正文段 ⇒ 判红。

### ★ 本轮新工具（过程证据，保留入库）
- `_probe_v12333_candyield.py` —— 真实入口可达（Q1 调用次数 / Q2 返回值 /
  Q3 落盘 / Q4 读法一致 / **Q5 产物无污染**）。
- `_probe_v12333_candyield_par.py` —— **三通道**一致性（防「一处有一处没有」）。
- `_probe_v12333_quantmd.py` —— 读数进**产物正文**（可读性）。
"""


def main():
    if "## 十三、全局链路核查" in io.open(P, encoding="utf-8").read():
        print("已存在第十三节"); return
    raw = io.open(P, "rb").read()
    assert raw.count(b"\r\n") == 0, "记忆应为 LF-only"
    s = raw.decode("utf-8").rstrip("\n") + "\n" + ADD
    io.open(P, "wb").write(s.encode("utf-8"))
    print("OK 第十三节已追加，行数 %d" % s.count("\n"))


main()

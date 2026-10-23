# -*- coding: utf-8 -*-
"""生成 元DGTF 整体架构图（PNG + SVG + Mermaid）。

布局：交互/应用 → 调度/预算/停止 → 四层螺旋 → 基础设施 → 产物/验证门。
只依赖 Pillow 与系统雅黑字体；SVG 与 PNG 共用同一份布局数据。
"""
from __future__ import annotations

import html
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "docs" / "架构图"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 2800, 1370
BG = "#F8FAFC"
INK = "#0F172A"
MUTED = "#475569"
FAINT = "#94A3B8"
LINE = "#CBD5E1"
SHADOW = "#E2E8F0"

BLUE = "#2563EB"
PURPLE = "#7C3AED"
TEAL = "#0D9488"
GREEN = "#059669"
AMBER = "#D97706"
ROSE = "#E11D48"
SLATE = "#475569"
CYAN = "#0891B2"
OK = "#16A34A"

FONT_REG = "C:/Windows/Fonts/msyh.ttc"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"


def fnt(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

F_TITLE = fnt(56, True)
F_SUB = fnt(24)
F_SEC = fnt(28, True)
F_BT = fnt(25, True)
F_BODY = fnt(19)
F_BODY_S = fnt(17)
F_NOTE = fnt(18)
F_SMALL = fnt(16)
F_FOOT = fnt(18)


def wrap(text: str, font, maxw: int):
    out, cur = [], ""
    for ch in str(text):
        if ch == "\n":
            out.append(cur)
            cur = ""
            continue
        if not cur or d.textlength(cur + ch, font=font) <= maxw:
            cur += ch
        else:
            out.append(cur)
            cur = ch
    if cur:
        out.append(cur)
    return out or [""]


BOXES = []


def box(id_, x, y, w, h, color, title, body, sub="", small=False):
    BOXES.append(dict(id=id_, x=x, y=y, w=w, h=h, color=color,
                      title=title, body=body, sub=sub, small=small))


# ── 左：交互 / 应用 / 配置 ─────────────────────────────────
box("A1", 70, 170, 400, 170, BLUE, "① 交互入口", [
    "CLI：python 元DGTF-V1.25.0.py",
    "Web 工作台：server.py + app.js",
    "任务队列 / 实时日志 / 取消 / 归档",
])
box("A2", 70, 360, 400, 190, BLUE, "② 应用层 dgtf_app", [
    "engine_runner：子进程 + 并发 3",
    "params：yaml 合并 + 校验",
    "library / outputs / dashboard",
])
box("A3", 70, 560, 400, 155, BLUE, "③ 配置与输入", [
    "dgtf_config.yaml（all_on=false）",
    "dgtf_config.user.yaml（已清空）",
    "题面 / 锚点 / 联网开关",
])
box("A4", 70, 735, 400, 135, BLUE, "关键运行参数", [
    "shape_limit=8 · max_tokens=2.0M",
    "effort=low · bandit=off · EML=on",
], small=True)

# ── 中左：调度 / 模式 / 预算 / 停止 ────────────────────────
box("B1", 530, 170, 470, 150, PURPLE, "④ 调度 auto_plan", [
    "五维规划：route / mode / rounds / max_calls",
    "规则优先 → LLM 兜底；脏值钳制",
])
box("B2", 530, 350, 470, 170, PURPLE, "⑤ 执行模式", [
    "serial（层序）/ A–H（阶段 DAG）",
    "waits=上游跑完 / gates=上游出首圈",
    "预热圈 + 阶段闸 + 并行展开",
])
box("B3", 530, 550, 470, 160, PURPLE, "⑥ 预算与续跑", [
    "max_calls / max_minutes / max_tokens=2M",
    "层/圈边界优雅停 → paused + 快照",
    "resume_ckpt 复用已完成层",
])
box("B4", 530, 730, 470, 180, PURPLE, "⑦ 停止与质量", [
    "自然安住 / 结构饱和 / 空转 / 职责 / 目标",
    "anytime：Hoeffding 或 e-process（opt-in）",
    "覆盖闸 / 预算闸 / 历史最佳圈指针",
    "读数：覆盖 · 三态 · S · 密度 · 复读",
], small=True)

# ── 中右：四层螺旋 ────────────────────────────────────────
box("C0", 1030, 200, 470, 250, TEAL, "0 修行 · manifest", [
    "用最少圈数把各层面挖尽",
    "· 阴阳展开 / & 撞不动 / 线头 / 探针",
    "· Heaps 边际新增率 → 结构饱和",
    "收敛：趋近无穷（饱和）",
], sub="objective=manifest")
box("C1", 1550, 200, 470, 250, GREEN, "1 研究 · truth", [
    "用最少圈数给出确定答案",
    "· 拆解 → 证据/锚点 → 三态判决",
    "· 覆盖 / 清算 / 可判定性冻结",
    "收敛：有限（覆盖率）",
], sub="objective=truth")
box("Cb", 1030, 490, 470, 250, AMBER, "both 对撞 · collision", [
    "无穷发散 ∩ 有限确定 ⇒ 融合新层面",
    "· 阴/阳两臂 → 第三者 → 张力",
    "· 产出率 ×(1−语义停滞罚)",
    "收敛：张力被消化 / 产出率",
], sub="objective=collision")
box("Ca", 1550, 490, 470, 250, ROSE, "all 元 · closure", [
    "记忆结晶 / 决策 / 行动 + 回看全程",
    "· 四件事留痕 · 元层清算",
    "· 未交代 / 悬置 / 冲突都留痕",
    "收敛：留痕完整度",
], sub="objective=closure")
box("CH", 1030, 752, 990, 96, "#4F46E5", "三通道并行（每圈都写）", [
    "content 写了什么 · context 凭什么写 · self 自己怎么看这次写",
], small=True)

# ── 右：产物 / 读数 / 验证门 ──────────────────────────────
box("D1", 2080, 170, 650, 210, CYAN, "10 产物与留痕", [
    "· outputs/*.md（正文 + 分层 md）",
    "· *.packed.json（结构化全量）",
    "· *.run.log / *.run.json（运行归档）",
    "· 失败 / 悬置 / 冲突都留痕，不删行",
], small=True)
box("D2", 2080, 410, 650, 170, CYAN, "11 质量读数 / V2 影子", [
    "覆盖 · 三态一致 · 职责 S · 语义密度",
    "复读率 · 候选产出率 · 历史最佳圈",
    "质量闭环：覆盖/三态/决策/线索",
], small=True)
box("D3", 2080, 590, 650, 250, OK, "12 验证门（必须全绿）", [
    "冒烟 266　·　跨档验收 319",
    "工程审计 70　·　变异体 3/3（113 基线）",
    "前端自检 371　·　内核 24 · 优化 27",
    "静态审计：15 critical / 118 major / 164 minor",
    "默认 GBK 环境：门禁 EXIT=0",
], small=True)

# ── 底部：基础设施 ────────────────────────────────────────
INFRA = [
    ("I1", 550, "LLM 网关", [
        "DeepSeek flash / v4-pro",
        "thinking 分档 · JSON mode",
        "重试 · 分环节成本",
        "JSON 自修复（失败时）",
    ]),
    ("I2", 840, "联网检索", [
        "Tavily + 缓存 + 域名 tier",
        "三层配额 + 连续失败降级",
        "W# 只作参照，不进候选",
    ]),
    ("I3", 1130, "外部锚点", [
        "snapshot / Tavily",
        "tier 门 + 交叉核对",
        "引用表 / triage 降级",
    ]),
    ("I4", 1420, "EML 记忆", [
        "episodes / playbook / nogoods / bandit",
        "micro → meso → macro",
        "质量闸 · 升级 · 遗忘 · 召回",
    ]),
    ("I5", 1710, "前沿内核 F1–F4", [
        "F1 e-process 任意停时",
        "F2 保形 · F3 BOCPD",
        "F4 Dung 论证（只标不删）",
    ]),
]
for _id, _x, _t, _b in INFRA:
    box(_id, _x, 975, 270, 230, SLATE, _t, _b, small=True)

# ── 绘制 ──────────────────────────────────────────────────
def draw_box(b):
    x, y, w, h = b["x"], b["y"], b["w"], b["h"]
    d.rounded_rectangle((x + 5, y + 6, x + w + 5, y + h + 6),
                        radius=18, fill=SHADOW)
    d.rounded_rectangle((x, y, x + w, y + h), radius=18,
                        fill="#FFFFFF", outline=b["color"], width=2)
    d.rounded_rectangle((x + 1, y + 1, x + 8, y + h - 1), radius=6,
                        fill=b["color"])
    d.text((x + 28, y + 18), b["title"], font=F_BT, fill=b["color"])
    _y = y + 58
    if b.get("sub"):
        d.text((x + 28, _y), b["sub"], font=F_SMALL, fill=MUTED)
        _y += 26
    _f = F_BODY_S if b.get("small") else F_BODY
    _lh = 25 if b.get("small") else 29
    _maxw = w - 52
    for raw in b["body"]:
        for line in wrap(raw, _f, _maxw):
            if _y + _lh > y + h - 8:
                print("WARN overflow", b["id"], raw[:24])
                break
            d.text((x + 28, _y), line, font=_f, fill=INK)
            _y += _lh


for _b in BOXES:
    draw_box(_b)


def arrow(pts, color=FAINT, width=3, dashed=False, head=True):
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if not dashed:
            d.line([a, b], fill=color, width=width)
        else:
            _dashed(a, b, color, width)
    if head:
        a, b = pts[-2], pts[-1]
        vx, vy = b[0] - a[0], b[1] - a[1]
        ln = max((vx * vx + vy * vy) ** 0.5, 1e-6)
        ux, uy = vx / ln, vy / ln
        px, py = -uy, ux
        s = 13
        d.polygon([(b[0], b[1]),
                   (b[0] - ux * s + px * s * 0.55, b[1] - uy * s + py * s * 0.55),
                   (b[0] - ux * s - px * s * 0.55, b[1] - uy * s - py * s * 0.55)],
                  fill=color)


def _dashed(a, b, color, width=3, dash=12, gap=9):
    x1, y1 = a
    x2, y2 = b
    ln = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if ln <= 0:
        return
    ux, uy = (x2 - x1) / ln, (y2 - y1) / ln
    t = 0.0
    while t < ln:
        e = min(t + dash, ln)
        d.line([(x1 + ux * t, y1 + uy * t),
                (x1 + ux * e, y1 + uy * e)], fill=color, width=width)
        t = e + gap


# 主流程
arrow([(470, 245), (530, 245)], LINE)
arrow([(470, 435), (530, 435)], LINE)
arrow([(1000, 435), (1030, 435)], LINE)
arrow([(1500, 325), (1550, 325)], LINE)
arrow([(1285, 450), (1285, 490)], LINE)
arrow([(1550, 450), (1500, 490)], LINE)
arrow([(1500, 615), (1550, 615)], LINE)
arrow([(2020, 615), (2055, 615), (2055, 290), (2080, 290)], LINE)
arrow([(2405, 380), (2405, 410)], LINE)
arrow([(2405, 560), (2405, 590)], LINE)
# 核心 ←→ 基础设施
for _x in (1200, 1500, 1800):
    arrow([(_x, 975), (_x, 848)], LINE, width=2, head=True)
# （EML → 调度/守卫 的口径写在基础设施标题里，避免与回看虚线交叉）
# 三通道条接在四层下方
for _x in (1265, 1785):
    arrow([(_x, 740), (_x, 752)], LINE, width=2, head=False)
# 回看 / carry / 自省（走右侧，避开三通道条）
arrow([(2020, 700), (2040, 700), (2040, 900), (1015, 900), (1015, 325), (1030, 325)],
      "#94A3B8", width=2, dashed=True)

# 标题
d.text((70, 42), "元 DGTF · 整体架构", font=F_TITLE, fill=INK)
d.text((72, 112), "v1.25.0 · 单文件四层螺旋推理引擎 · 四层 × 三通道 × 可审计产物",
       font=F_SUB, fill=MUTED)
d.text((1030, 145), "⑧ 四层螺旋核心（每层：目标 → 展开 → 沉淀 → 读数 → 停止）",
       font=F_SEC, fill=INK)
d.text((1030, 176), "每层每圈：摊开 → 深入 → 收束；层间靠 carry / 自省 / 记忆回流",
       font=F_SMALL, fill=MUTED)
d.text((2280, 112), "实线 = 主流程　虚线 = 回流 / 经验", font=F_SMALL, fill=FAINT)
d.text((530, 930), "⑨ 认知与证据基础设施",
       font=F_SEC, fill=INK)

# 标签
def lab(x, y, text, color=MUTED, size=F_NOTE, anchor=None):
    d.text((x, y), text, font=size, fill=color, anchor=anchor)


lab(1005, 404, "模式/圈数", FAINT, F_SMALL)
lab(1512, 292, "展开", FAINT, F_SMALL)
lab(1512, 582, "融合", FAINT, F_SMALL)
lab(1262, 462, "对撞", FAINT, F_SMALL)
lab(1200, 884, "回看 / carry / 自省 → 下一圈", FAINT, F_SMALL)

# 底部红线
red1 = ("红线：输入是形状不是数据　·　悬置不打分　·　未对齐合法　·　停止≠清算　·　失败留痕　·　"
        "入池挡重复　·　参数按层覆盖　·　自省不可合并　·　EML 不碰答案　·　没有读数不假装有")
red2 = ("版本：v1.25.0（28327 行 / 纯 CRLF）　|　最优配置：all_on=false · shape=8 · "
        "max_tokens=2M · effort=low　|　成本参考：四层 ≈230 calls / 1.7M tokens / ¥4.3")
d.rounded_rectangle((70, 1240, 2690, 1328), radius=14, fill="#FFFFFF",
                    outline=LINE, width=1)
_y = 1252
for _ln in wrap(red1, F_FOOT, 2560):
    d.text((90, _y), _ln, font=F_FOOT, fill=INK)
    _y += 24
for _ln in wrap(red2, F_SMALL, 2560):
    d.text((90, _y), _ln, font=F_SMALL, fill=MUTED)
    _y += 22

png = OUT / "元DGTF-整体架构-v1.25.0.png"
img.save(png, "PNG", optimize=True)
print("PNG", png, png.stat().st_size)

# ── SVG（同一布局）────────────────────────────────────────
svg = []
svg.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d">' % (W, H, W, H))
svg.append('<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" '
           'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           '<path d="M 0 0 L 10 5 L 0 10 z" fill="#94A3B8"/></marker></defs>')
svg.append('<rect width="100%" height="100%" fill="{}"/>'.format(BG))


def esc(s):
    return html.escape(str(s), quote=True)


def svg_text(x, y, text, size, color=INK, bold=False):
    svg.append('<text x="%d" y="%d" font-family="Microsoft YaHei, Segoe UI, sans-serif" '
               'font-size="%d" fill="%s"%s>%s</text>'
               % (x, y, size, color, ' font-weight="700"' if bold else "",
                  esc(text)))


def svg_para(x, y, lines, font, color, lh, maxw):
    _y = y
    for raw in lines:
        for line in wrap(raw, font, maxw):
            svg_text(x, _y, line, font.size, color)
            _y += lh


for b in BOXES:
    x, y, w, h = b["x"], b["y"], b["w"], b["h"]
    svg.append('<rect x="%d" y="%d" width="%d" height="%d" rx="18" fill="#E2E8F0"/>'
               % (x + 5, y + 6, w, h))
    svg.append('<rect x="%d" y="%d" width="%d" height="%d" rx="18" fill="#FFFFFF" '
               'stroke="%s" stroke-width="2"/>' % (x, y, w, h, b["color"]))
    svg.append('<rect x="%d" y="%d" width="7" height="%d" rx="3" fill="%s"/>'
               % (x + 1, y + 1, h - 2, b["color"]))
    svg_text(x + 28, y + 42, b["title"], 25, b["color"], True)
    _y = y + 72
    if b.get("sub"):
        svg_text(x + 28, _y, b["sub"], 16, MUTED)
        _y += 26
    else:
        _y = y + 96
    _f = F_BODY_S if b.get("small") else F_BODY
    _lh = 25 if b.get("small") else 29
    svg_para(x + 28, _y, b["body"], _f, INK, _lh, w - 52)


def svg_arrow(pts, dashed=False):
    _pts = " ".join("%d,%d" % p for p in pts)
    svg.append('<polyline points="%s" fill="none" stroke="#94A3B8" '
               'stroke-width="2.5" marker-end="url(#ah)"%s/>'
               % (_pts, ' stroke-dasharray="12 9"' if dashed else ""))


for _pts in [ [(470,245),(530,245)], [(470,435),(530,435)],
              [(1000,435),(1030,435)], [(1500,325),(1550,325)],
              [(1285,450),(1285,490)], [(1550,450),(1500,490)],
              [(1500,615),(1550,615)],
              [(2020,615),(2055,615),(2055,290),(2080,290)],
              [(2405,380),(2405,410)], [(2405,560),(2405,590)] ]:
    svg_arrow(_pts)
for _x in (1200, 1500, 1800):
    svg_arrow([(_x, 975), (_x, 848)])
svg_arrow([(1265, 740), (1265, 752)])
svg_arrow([(1785, 740), (1785, 752)])
svg_arrow([(2020, 700), (2040, 700), (2040, 900), (1015, 900), (1015, 325), (1030, 325)], True)

svg_text(70, 88, "元 DGTF · 整体架构", 56, INK, True)
svg_text(72, 134, "v1.25.0 · 单文件四层螺旋推理引擎 · 四层 × 三通道 × 可审计产物", 24, MUTED)
svg_text(1030, 170, "⑧ 四层螺旋核心（每层：目标 → 展开 → 沉淀 → 读数 → 停止）", 28, INK, True)
svg_text(1030, 194, "每层每圈：摊开 → 深入 → 收束；层间靠 carry / 自省 / 记忆回流", 16, MUTED)
svg_text(2280, 126, "实线 = 主流程　虚线 = 回流 / 经验", 16, FAINT)
svg_text(530, 955, "⑨ 认知与证据基础设施", 28, INK, True)

for _x, _y, _t, _c in [
    (1005, 404, "模式/圈数", FAINT), (1512, 292, "展开", FAINT),
    (1512, 582, "融合", FAINT), (1262, 462, "对撞", FAINT),
    (1200, 884, "回看 / carry / 自省 → 下一圈", FAINT)]:
    svg_text(_x, _y, _t, 16, _c)

svg.append('<rect x="70" y="1240" width="2620" height="88" rx="14" fill="#FFFFFF" '
           'stroke="#CBD5E1"/>')
_y = 1252
for _ln in wrap(red1, F_FOOT, 2560):
    svg_text(90, _y, _ln, 18, INK); _y += 24
for _ln in wrap(red2, F_SMALL, 2560):
    svg_text(90, _y, _ln, 16, MUTED); _y += 22
svg.append("</svg>")
svgp = OUT / "元DGTF-整体架构-v1.25.0.svg"
svgp.write_text("\n".join(svg), encoding="utf-8")
print("SVG", svgp, svgp.stat().st_size)

# ── Mermaid（可编辑源）───────────────────────────────────
mmd = """flowchart TB
  subgraph UI[交互 / 应用]
    CLI[CLI 元DGTF-V1.25.0.py]
    WEB[Web 工作台 server.py + app.js]
    RUN[engine_runner 任务/日志/归档]
    CFG[配置 factory + user yaml]
  end
  subgraph ORCH[调度 / 预算 / 停止]
    PLAN[auto_plan 五维规划]
    MODE[serial / A-H 阶段 DAG]
    BUDGET[max_calls / max_minutes / max_tokens]
    STOP[停止与质量读数]
  end
  subgraph CORE[四层螺旋]
    L0[0 修行 manifest]
    L1[1 研究 truth]
    BOTH[both 对撞 collision]
    ALL[all 元 closure]
    CH[三通道 content / context / self]
  end
  subgraph INFRA[认知与证据基础设施]
    LLM[LLM 网关]
    WEB2[联网检索]
    ANC[外部锚点]
    EML[EML 记忆]
    F[前沿内核 F1-F4]
  end
  subgraph OUT[产物 / 验证]
    MD[md + packed.json + run 归档]
    Q[质量读数]
    GATE[冒烟/验收/审计/变异体/前端自检]
  end
  CLI --> RUN
  WEB --> RUN
  CFG --> PLAN
  RUN --> PLAN
  PLAN --> MODE --> BUDGET --> STOP
  STOP --> CORE
  CORE --> MD --> Q --> GATE
  L0 --> L1
  L0 --> BOTH
  L1 --> BOTH
  BOTH --> ALL
  ALL -. carry / 自省 .-> L0
  CORE <--> INFRA
  EML -. 调度/守卫建议 .-> STOP
"""
mmdp = OUT / "元DGTF-整体架构-v1.25.0.mmd"
mmdp.write_text(mmd, encoding="utf-8")
print("MMD", mmdp)

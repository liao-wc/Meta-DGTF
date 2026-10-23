# 第六期补丁 P6-3：四个量化读数的**真实产物出口**（L2/L3/L4）。
# ★ 承本项目通则「字段有值 ≠ 有出口」「有出口 ≠ 有值」——**两向都要查**：
#   这里同时做两件事：① View 上加 property 算出值；② to_dict 出到产物。
# ★ 红线：只出**读数与线索**，不改象限、不删候选、不打分。
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

# ── A1：View 上新增读数字段（与 goal_trace 同片区）──
A1 = '''    goal_trace: List[dict] = field(default_factory=list)'''
NEW1 = '''    goal_trace: List[dict] = field(default_factory=list)
    # ★ [第六期] 各环节量化读数（零成本、纯函数产出；缺输入 ⇒ 不出键）。
    quant_readings: Dict[str, dict] = field(default_factory=dict)'''

# ── A2：to_dict 出口（紧挨 goal_trace 出口，同款「有值才出」纪律）──
A2 = '''        if getattr(self, "goal_trace", None):
            d["goal_trace"] = list(self.goal_trace)'''
NEW2 = '''        # ★ [第六期] 量化读数出口：**有才出**（空 dict 不出键，
        #   与 goal_trace 同款纪律，避免产物里出现空壳读数）。
        if getattr(self, "quant_readings", None):
            d["quant_readings"] = {
                str(k): dict(v) for k, v in (self.quant_readings or {}).items()
                if isinstance(v, dict) and v
            }
        if getattr(self, "goal_trace", None):
            d["goal_trace"] = list(self.goal_trace)'''


def _apply(text, anchor, new, tag):
    n = text.count(anchor)
    if n != 1:
        print("X %s 锚点命中 %d 次" % (tag, n)); sys.exit(1)
    return text.replace(anchor, new, 1)


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 非纯 CRLF"); sys.exit(1)
    s = txt.replace("\r\n", "\n")
    s = _apply(s, A1, NEW1, "A1")
    s = _apply(s, A2, NEW2, "A2")
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 第六期补丁 P6-3 已打：读数出口（quant_readings）")


if __name__ == "__main__":
    main()

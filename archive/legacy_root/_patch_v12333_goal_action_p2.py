# 第二期补丁（P2-2）：补上**并行通道**的 `_refresh_goal_hint` 接线。
# ★ 自洽核查逮到：P2-1 的 A7 锚点只命中串行那处（15144），并行那处
#   （16807）因为上下文注释不同而**漏接** —— 正是本项目「一处有一处没有」的老坑。
#   判据 ㉖ 就是为拦这个写的（要求两处都接）。
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "元DGTF-V1.23.33.py"

ANCHOR = '''        # ★ [四层目标 → 每圈运行] 并行通道同样算（两通道一处实现）。
        self._layer_goal_now(entry, view)
        _goal_hit, _goal_why = self._goal_stop_signal(entry, view)'''

NEW = '''        # ★ [四层目标 → 每圈运行] 并行通道同样算（两通道一处实现）。
        self._layer_goal_now(entry, view)
        self._refresh_goal_hint(entry, view)
        _goal_hit, _goal_why = self._goal_stop_signal(entry, view)'''


def main():
    b = SRC.read_bytes()
    txt = b.decode("utf-8")
    if txt.count("\r\n") != txt.count("\n") or "\r\r\n" in txt:
        print("X 非纯 CRLF"); sys.exit(1)
    s = txt.replace("\r\n", "\n")
    n = s.count(ANCHOR)
    if n != 1:
        print("X 锚点命中 %d 次" % n); sys.exit(1)
    s = s.replace(ANCHOR, NEW, 1)
    out = s.replace("\n", "\r\n").encode("utf-8")
    if out.decode("utf-8").count("\r\r\n"):
        print("X r-r-n"); sys.exit(1)
    SRC.write_bytes(out)
    print("OK 第二期补丁 P2-2 已打：并行通道接线补齐")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""等待 _run_v12327.log 里出现收尾标志（或超时），然后打印末段。"""
import sys, time, os

LOG = "_run_v12327.log"
DONE_MARKERS = ("最终产物", "已写入", "[DONE]", "完成。", "耗时", "总耗时")


def tail(path, n):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()[-n:]
    except Exception as e:
        return ["<tail fail: %s>" % e]


def main():
    budget = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    t0 = time.time()
    last_lines = -1
    while time.time() - t0 < budget:
        try:
            with open(LOG, "r", encoding="utf-8", errors="replace") as f:
                txt = f.read()
        except Exception:
            time.sleep(10)
            continue
        lines = txt.count("\n")
        if lines != last_lines:
            last_lines = lines
            print("[%s] lines=%d" % (
                time.strftime("%H:%M:%S"), lines), flush=True)
        if any(m in txt for m in DONE_MARKERS) and lines > 1900:
            print("=== DONE-ish ===", flush=True)
            break
        # 停在固定行数超过 300 秒 ⇒ 程序已退出
        time.sleep(10)
    print("=== TAIL 30 ===", flush=True)
    for ln in tail(LOG, 30):
        print(ln.rstrip(), flush=True)
    print("TOTAL_LINES=%d" % last_lines, flush=True)


if __name__ == "__main__":
    main()

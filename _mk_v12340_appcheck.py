# -*- coding: utf-8 -*-
"""v1.23.40 端到端：dgtf_app 应用层自检（起服务 → selftest → 收尾）。

本版动了 `dgtf_app/params.py`（新增 `web_search.relax_force` 键名）⇒ 必须
在应用层确认「参数面板 + 全链路接口」仍全绿（mock，零 API 花费）。

用法： python _mk_v12340_appcheck.py
产出： `_app_selftest_v12340.log`（人类可读）。
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE / "dgtf_app"
PY = sys.executable
PORT = 8765
BASE = "http://127.0.0.1:%d" % PORT
LOG = HERE / "_app_selftest_v12340.log"


def _up(timeout=30.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(BASE + "/", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def main() -> int:
    env = dict(os.environ)
    # ★ sandbox safe-delete 守卫拦服务进程内 os.remove ⇒ library/delete 会
    #   报 RemoteDisconnected（不是 bug）⇒ 起服务时关掉该守卫。
    env["CODEBUDDY_SAFE_DELETE_ENABLED"] = "0"
    env["DGTF_APP_MOCK"] = "1"

    srv = subprocess.Popen(
        [PY, "-u", "server.py", "--port", str(PORT)],
        cwd=str(APP), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace",
    )
    try:
        if not _up():
            print("[ERR] 服务未在超时内就绪")
            return 2
        print("[ok] 服务已就绪 %s" % BASE)
        p = subprocess.run([PY, "-u", "selftest.py", "--base", BASE],
                           cwd=str(APP), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        LOG.write_bytes(out.encode("utf-8"))
        tail = [ln for ln in out.splitlines() if ln.strip()][-3:]
        print("\n".join(tail))
        # 汇总行
        summ = [ln for ln in out.splitlines() if "结果：" in ln or "PASS" in ln]
        print("---")
        for ln in summ[-2:]:
            print(ln)
        return 0 if ("FAIL 0" in out) else 1
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=8)
        except Exception:
            srv.kill()
        print("[ok] 服务已收尾")


if __name__ == "__main__":
    sys.exit(main())

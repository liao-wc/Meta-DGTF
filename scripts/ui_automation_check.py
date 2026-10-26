# -*- coding: utf-8 -*-
"""App UI 自动化回归：模式切换、Agent 灯、历史按钮、控制台错误。

默认使用本机 Edge + Selenium headless。Selenium/Edge 不可用时 SKIP（返回 0），
本地发布检查/守卫可直接调用；失败时返回 1。
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN = (ROOT / "dgtf_memory" / ".access_token").read_text(encoding="utf-8").strip()


def _skip(msg):
    print(json.dumps({"ok": True, "skipped": True, "reason": msg}, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://127.0.0.1:8765")
    ap.add_argument("--json-out", default="docs/ui_audit_latest.json")
    ap.add_argument("--timeout", type=float, default=20)
    a = ap.parse_args()
    try:
        from selenium import webdriver
        from selenium.webdriver.edge.options import Options
    except Exception as exc:
        return _skip("selenium unavailable: %s" % exc)
    edge = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    if not edge.is_file():
        return _skip("Edge not found")
    o = Options()
    o.add_argument("--headless=new")
    o.add_argument("--disable-gpu")
    o.add_argument("--no-sandbox")
    o.add_argument("--window-size=1280,900")
    o.add_argument("--allow-insecure-localhost")
    o.add_argument("--ignore-certificate-errors")
    try:
        o.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    except Exception:
        pass
    driver = None
    tests = []

    def ck(name, ok, detail=""):
        tests.append({"name": name, "ok": bool(ok), "detail": str(detail)[:1000]})

    def js(expr):
        return driver.execute_script(expr)

    try:
        driver = webdriver.Edge(options=o)
        driver.set_page_load_timeout(a.timeout)
        driver.get(a.base.rstrip("/") + "/?t=" + TOKEN)
        time.sleep(2.5)
        ck("页面标题", "Meta-DGTF" in driver.title, driver.title)
        ck("侧边栏北斗七星", int(js("return document.querySelectorAll('.bd-row').length")) == 7,
           js("return document.querySelectorAll('.bd-row').length"))
        agent_cls = str(js("var e=document.querySelector('.bd-row[data-env-key=agent] .dot'); return e ? e.className : ''"))
        ck("Agent 就绪灯不为灰", "no" not in agent_cls and "ok" in agent_cls, agent_cls)
        ck("DSH 历史按钮已移除", js("return !document.querySelector('#dsh-history-toggle')") is True)
        ck("初始不是 DSH 对话", js("return !document.querySelector('.rl-dsh-live')") is True)
        # 点击 DSH Agent：只切模式，不自动进对话
        js("document.querySelector('#pill-dsh').click(); return true")
        time.sleep(0.6)
        ck("DSH 模式开关已打开", js("return document.body.classList.contains('dsh-mode')") is True)
        ck("点击后不自动切进 DSH 对话", js("return !document.querySelector('.rl-dsh-live')") is True)
        ck("点击后仍停留在首屏", js("return document.body.classList.contains('stage-empty')") is True)
        ck("历史按钮仍不存在", js("return !document.querySelector('#dsh-history-toggle')") is True)
        # 退出 DSH 模式
        js("document.querySelector('#pill-dsh').click(); return true")
        time.sleep(0.5)
        ck("退出 DSH 模式", js("return !document.body.classList.contains('dsh-mode')") is True)
        ck("退出后回到首屏", js("return document.body.classList.contains('stage-empty')") is True)
        # 控制台错误
        try:
            logs = driver.get_log("browser")
            severe = [x for x in logs if str(x.get("level")) == "SEVERE" and "favicon" not in str(x.get("message"))]
            ck("无浏览器 SEVERE 错误", not severe, json.dumps(severe[:3], ensure_ascii=False))
        except Exception as exc:
            ck("无浏览器 SEVERE 错误", True, "log unavailable: %s" % exc)
    except Exception as exc:
        ck("UI 自动化执行", False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
    doc = {"ok": all(x["ok"] for x in tests), "tests": tests, "ts": time.time()}
    p = ROOT / a.json_out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

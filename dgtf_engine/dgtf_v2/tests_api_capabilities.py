# -*- coding: utf-8 -*-
from dgtf_v2.api_capabilities import summary, MATRIX


def main():
    ok = True
    s = summary()
    r = s["n"] == len(MATRIX); ok = ok and r
    print("PASS" if r else "FAIL", "n")
    r = s["counts"].get("used", 0) >= 6; ok = ok and r
    print("PASS" if r else "FAIL", "used")
    r = not any(x["status"] not in ("used", "adapted", "optional", "n/a", "auto") for x in MATRIX); ok = ok and r
    print("PASS" if r else "FAIL", "status")
    r = any(x["feature"] == "Fetch" and x["status"] == "used" for x in MATRIX); ok = ok and r
    print("PASS" if r else "FAIL", "fetch")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""v1.23.28：`Pool.to_dict` 补 `sem_entropy_thr` 出口。

冒烟的前向守卫 `check_v123_pool_export` 抓到：新增了 dataclass 字段
`Pool.sem_entropy_thr` 但 `to_dict` 手工白名单没同步（键名必须 == 字段名）。
与 `revoke_sources` 同一形态 —— 「配置生效值必须出口，否则读产物的人
不知道这批读数按哪个门槛算的」。
"""
SRC = "元DGTF-V1.23.28.py"


def _load(path=SRC):
    b = open(path, "rb").read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n") - crlf
    assert crlf > 0
    assert lf == 0, "混入裸 LF %d 处" % lf
    assert b.count(b"\r\r\n") == 0
    return b.decode("utf-8").replace("\r\n", "\n"), crlf, lf


def _save(txt, path=SRC):
    out = txt.replace("\r\n", "\n").replace("\n", "\r\n")
    data = out.encode("utf-8")
    assert data.count(b"\r\r\n") == 0
    open(path, "wb").write(data)


def patch(txt, name, old, new, count=1):
    n = txt.count(old)
    assert n == count, "[%s] 锚点命中 %d 次（期望 %d）" % (name, n, count)
    return txt.replace(old, new)


def main():
    txt, crlf0, lf0 = _load()
    print("[in] CRLF=%d LF=%d" % (crlf0, lf0))

    txt = patch(
        txt, "pool-export-semthr",
        '''        d["revoke_sources"] = int(self.revoke_sources)
''',
        '''        d["revoke_sources"] = int(self.revoke_sources)
        # [D3 可配] 语义熵聚类阈值同上：出口的是**实际生效值**（配置可能
        #   覆盖默认）—— 读产物的人要知道这批 `semantic_entropy` 是按哪个
        #   门槛算的。★ 键名必须 == 字段名（前向守卫按
        #   `__dataclass_fields__` 逐个查出口，改名即判红）。
        d["sem_entropy_thr"] = float(self.sem_entropy_thr)
''',
    )

    _save(txt)
    _, crlf1, lf1 = _load()
    print("[out] CRLF=%d LF=%d  \\r\\r\\n=%d"
          % (crlf1, lf1, open(SRC, "rb").read().count(b"\r\r\n")))
    print("[OK] pool export added")


if __name__ == "__main__":
    main()

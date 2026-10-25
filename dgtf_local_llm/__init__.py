# -*- coding: utf-8 -*-
"""Meta-DGTF-道生三阶模型 · 本地推理服务包。

模块：
  service.py  8772 HTTP 服务（/health, /generate）
  client.py   给 engine/app 用的零依赖客户端（失败返回结构化 dict，便于云回退）

契约与实测见 docs/local_model_daosheng.md。
"""

__all__ = ["service", "client"]

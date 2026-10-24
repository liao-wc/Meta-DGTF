# 本地模型与全链路验证

日期：2026-10-24

- BGE embedding 服务 http://127.0.0.1:8771/health：200，model=bge-small-zh-v1.5，dev=cuda，dim=512。
- /embed 真实编码“四层推理系统的最小可行闭环”：ok=true，512 维向量。
- local_model/envs/dgtf_llm_env：pip check 0 broken；torch 2.14.1+cu126；transformers 5.20.2。
- App /api/health：app 2.0.0，engine Meta-DGTF-V2.2.0.py / 2.2.0，BGE 由后台线程拉起。
- App→engine：engine_runner 选 Meta-DGTF-V2.2.0.py，任务走 App 队列/日志/outputs；子进程无控制台窗口。


## App 任务贯穿

- App 队列任务 20261024_082813_b7348f 成功调用引擎，输出 20261024_083648_Python中len函数的作用是什.*。
- App health 200，BGE 8771 健康，engine_runner 选 V2.2.0。

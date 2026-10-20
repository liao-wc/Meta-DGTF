# -*- coding: utf-8 -*-
"""元DGTF V2 三平面参考内核（EML / Scheduler / Layer Contracts）。

生产引擎仍是 元DGTF-V1.23.66.py；本包是 V2 的可运行设计原型与回放工具。
"""
from .contracts import (Budget, LayerContract, LayerResult, LayerState,
                        LAYER_CONTRACTS, ContractViolation, validate_result)
from .memory import Event, MemoryLake
from .scheduler import Action, Decision, Scheduler, ScheduleTrace, WorldState
from .orchestrator import MockLayerExecutor, Orchestrator, RunReport
from .shadow import V2Shadow

__all__ = [
    "Budget", "LayerContract", "LayerResult", "LayerState", "LAYER_CONTRACTS",
    "ContractViolation", "validate_result", "Event", "MemoryLake",
    "Action", "Decision", "Scheduler", "ScheduleTrace", "WorldState",
    "MockLayerExecutor", "Orchestrator", "RunReport", "V2Shadow",
]

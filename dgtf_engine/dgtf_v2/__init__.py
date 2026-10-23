# -*- coding: utf-8 -*-
"""Meta-DGTF V2 三平面参考内核（EML / Scheduler / Layer Contracts）。

生产引擎为 Meta-DGTF-V2.2.0.py；本包是 V2 契约/调度/回放核心。
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

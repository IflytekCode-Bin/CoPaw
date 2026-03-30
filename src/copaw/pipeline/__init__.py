# -*- coding: utf-8 -*-
"""CoPaw Pipeline module for multi-agent orchestration.

This module provides pipeline classes for orchestrating multiple agents
in various patterns: sequential, fanout, conditional, and loop.
"""

from .base import PipelineBase
from .sequential import SequentialPipeline
from .fanout import FanoutPipeline
from .conditional import ConditionalPipeline
from .loop import LoopPipeline
from .msghub import CoPawMsgHub
from .state_manager import StateManager

__all__ = [
    "PipelineBase",
    "SequentialPipeline",
    "FanoutPipeline",
    "ConditionalPipeline",
    "LoopPipeline",
    "CoPawMsgHub",
    "StateManager",
]

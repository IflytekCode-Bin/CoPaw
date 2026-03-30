# -*- coding: utf-8 -*-
"""Pipeline base class for multi-agent orchestration.

This module provides the abstract base class for all pipeline types,
defining the common interface for pipeline execution, hook management,
and state tracking.
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

import shortuuid
from agentscope.message import Msg

if TYPE_CHECKING:
    from .state_manager import StateManager

logger = logging.getLogger(__name__)


class PipelineStatus(str, Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Valid hook types for pipeline lifecycle
VALID_HOOK_TYPES = frozenset(
    {
        "pre_pipeline",
        "post_pipeline",
        "pre_agent_call",
        "post_agent_call",
        "on_error",
        "on_timeout",
        "on_state_change",
    },
)

# Type alias for hook callables
# Hooks receive (pipeline, **kwargs) and return None
HookCallable = Callable[..., Any]


class PipelineBase(ABC):
    """Abstract base class for all pipeline types.

    A pipeline orchestrates the execution of multiple agents in a defined
    pattern (sequential, parallel, conditional, etc.), with integrated
    state management and lifecycle hooks.

    Attributes:
        name: Human-readable pipeline name.
        agents: List of agents participating in this pipeline.
        pipeline_id: Unique identifier for this pipeline execution.
        status: Current execution status.
    """

    def __init__(
        self,
        name: str,
        agents: Optional[List[Any]] = None,
        state_manager: Optional["StateManager"] = None,
        hooks: Optional[Dict[str, List[HookCallable]]] = None,
    ) -> None:
        """Initialize the pipeline.

        Args:
            name: Human-readable pipeline name.
            agents: List of agent instances to participate.
            state_manager: Optional state manager for checkpointing.
            hooks: Optional dict mapping hook_type to list of callables.
        """
        self.name = name
        self.agents = list(agents) if agents else []
        self.pipeline_id = self._generate_pipeline_id()
        self.status = PipelineStatus.PENDING

        # Lazy-import to avoid circular imports
        if state_manager is None:
            from .state_manager import StateManager

            self._state_manager = StateManager()
        else:
            self._state_manager = state_manager

        # Hook registry
        self._hooks: Dict[str, List[HookCallable]] = {}
        if hooks:
            for hook_type, hook_list in hooks.items():
                for hook in hook_list:
                    self.register_hook(hook_type, hook)

        logger.debug(
            "Pipeline '%s' created (id=%s, agents=%d)",
            self.name,
            self.pipeline_id,
            len(self.agents),
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(
        self,
        msg: Msg | List[Msg] | None = None,
        **kwargs: Any,
    ) -> Msg | List[Msg] | None:
        """Execute the pipeline.

        Args:
            msg: Initial input message(s).
            **kwargs: Additional keyword arguments.

        Returns:
            Final output message(s) from the pipeline.
        """

    # ------------------------------------------------------------------
    # Hook management
    # ------------------------------------------------------------------

    def register_hook(
        self,
        hook_type: str,
        hook: HookCallable,
    ) -> None:
        """Register a lifecycle hook.

        Args:
            hook_type: One of the valid hook types (pre_pipeline, etc.).
            hook: A callable ``(pipeline, **kwargs) -> None``.

        Raises:
            ValueError: If *hook_type* is not recognised.
        """
        if hook_type not in VALID_HOOK_TYPES:
            raise ValueError(
                f"Invalid hook_type '{hook_type}'. "
                f"Must be one of {sorted(VALID_HOOK_TYPES)}",
            )
        self._hooks.setdefault(hook_type, []).append(hook)
        logger.debug(
            "Registered hook '%s' on pipeline '%s'",
            hook_type,
            self.name,
        )

    def unregister_hook(
        self,
        hook_type: str,
        hook: HookCallable,
    ) -> bool:
        """Remove a previously registered hook.

        Returns:
            True if the hook was found and removed, False otherwise.
        """
        hook_list = self._hooks.get(hook_type, [])
        try:
            hook_list.remove(hook)
            return True
        except ValueError:
            return False

    async def _run_hooks(self, hook_type: str, **kwargs: Any) -> None:
        """Run all hooks registered for *hook_type*.

        Each hook is awaited if it is a coroutine function; otherwise it
        is called synchronously.  Exceptions in hooks are logged but do
        **not** abort the pipeline.
        """
        for hook in self._hooks.get(hook_type, []):
            try:
                import asyncio

                if asyncio.iscoroutinefunction(hook):
                    await hook(self, **kwargs)
                else:
                    hook(self, **kwargs)
            except Exception:
                logger.exception(
                    "Hook '%s' raised an error in pipeline '%s'",
                    hook_type,
                    self.name,
                )

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _set_status(self, status: PipelineStatus) -> None:
        """Update pipeline status and fire on_state_change hooks."""
        old = self.status
        self.status = status
        logger.debug(
            "Pipeline '%s' status: %s → %s",
            self.name,
            old.value,
            status.value,
        )
        # Fire asynchronously if possible — caller should await _run_hooks
        # directly when inside an async context.

    @property
    def state_manager(self) -> "StateManager":
        """Access the state manager."""
        return self._state_manager

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pipeline_id() -> str:
        """Generate a unique pipeline execution ID."""
        return f"pl_{shortuuid.uuid()[:12]}"

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"name={self.name!r} "
            f"id={self.pipeline_id!r} "
            f"agents={len(self.agents)} "
            f"status={self.status.value!r}>"
        )

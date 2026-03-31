# -*- coding: utf-8 -*-
"""Fanout Pipeline — distribute a message to multiple agents in parallel.

All agents receive the *same* input message and execute concurrently
(via ``asyncio.gather``) or sequentially.  The outputs are collected
into a list.

Typical use-cases: multi-reviewer code review, parallel research, voting.
"""

import asyncio
import logging
from copy import deepcopy
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from agentscope.message import Msg

from .base import PipelineBase, PipelineStatus

if TYPE_CHECKING:
    from .state_manager import StateManager

logger = logging.getLogger(__name__)


class FanoutPipeline(PipelineBase):
    """Broadcast an input to multiple agents and collect their outputs.

    Example::

        pipeline = FanoutPipeline(
            name="code_review",
            agents=[security_expert, perf_expert, style_expert],
            enable_gather=True,
        )
        results = await pipeline.execute(
            msg=Msg("user", "Review this code", "user"),
        )
        # results is a list of Msg from each agent
    """

    def __init__(
        self,
        name: str,
        agents: List[Any],
        state_manager: Optional["StateManager"] = None,
        hooks: Optional[dict] = None,
        *,
        enable_gather: bool = True,
        timeout: float | None = None,
    ) -> None:
        """
        Args:
            name: Pipeline name.
            agents: List of agents to receive the broadcast message.
            state_manager: Optional state persistence backend.
            hooks: Optional dict of hook_type → list[callable].
            enable_gather: If True, use ``asyncio.gather`` for concurrent
                execution.  If False, execute agents sequentially (useful
                for rate-limited APIs).
            timeout: Per-agent timeout in seconds.  ``None`` means no limit.
        """
        super().__init__(
            name=name,
            agents=agents,
            state_manager=state_manager,
            hooks=hooks,
        )
        self.enable_gather = enable_gather
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        msg: Msg | List[Msg] | None = None,
        **kwargs: Any,
    ) -> List[Msg | Exception]:
        """Run the fanout pipeline.

        Args:
            msg: Input message broadcast to every agent.
            **kwargs: Additional keyword arguments forwarded to each agent.

        Returns:
            A list of output messages (one per agent).  If an agent raises
            an exception its slot contains the ``Exception`` object instead.
        """
        self._set_status(PipelineStatus.RUNNING)
        await self._run_hooks("pre_pipeline", msg=msg)

        results: List[Msg | Exception]

        if self.enable_gather:
            results = await self._execute_parallel(msg, **kwargs)
        else:
            results = await self._execute_sequential(msg, **kwargs)

        self._set_status(PipelineStatus.COMPLETED)
        await self._run_hooks("post_pipeline", msg=results)
        return results

    # ------------------------------------------------------------------
    # Internal execution strategies
    # ------------------------------------------------------------------

    async def _execute_parallel(
        self,
        msg: Msg | List[Msg] | None,
        **kwargs: Any,
    ) -> List[Msg | Exception]:
        """Execute all agents concurrently via asyncio.gather."""

        async def _run_one(idx: int, agent: Any) -> Msg:
            agent_id = getattr(agent, "agent_id", str(idx))
            await self._run_hooks(
                "pre_agent_call",
                agent=agent,
                step=idx,
                msg=msg,
            )
            try:
                if self.timeout:
                    result = await asyncio.wait_for(
                        agent(deepcopy(msg)),
                        timeout=self.timeout,
                    )
                else:
                    result = await agent(deepcopy(msg))
            except asyncio.TimeoutError as exc:
                await self._run_hooks(
                    "on_timeout",
                    agent=agent,
                    step=idx,
                    timeout=self.timeout,
                )
                raise
            except Exception as exc:
                await self._run_hooks(
                    "on_error",
                    agent=agent,
                    step=idx,
                    error=exc,
                )
                raise

            await self._run_hooks(
                "post_agent_call",
                agent=agent,
                step=idx,
                msg=result,
            )

            # Save checkpoint
            await self._state_manager.save_checkpoint(
                pipeline_id=self.pipeline_id,
                step=idx,
                agent_id=agent_id,
                input_msg=msg if isinstance(msg, Msg) else None,
                output_msg=result,
                metadata={
                    "pipeline_name": self.name,
                    "mode": "parallel",
                    "status": "completed",
                },
            )
            return result

        tasks = [_run_one(i, agent) for i, agent in enumerate(self.agents)]
        raw = await asyncio.gather(*tasks, return_exceptions=True)

        # Log errors
        for i, item in enumerate(raw):
            if isinstance(item, Exception):
                agent_id = getattr(self.agents[i], "agent_id", str(i))
                logger.error(
                    "Pipeline '%s' agent '%s' failed: %s",
                    self.name,
                    agent_id,
                    item,
                )

        return list(raw)

    async def _execute_sequential(
        self,
        msg: Msg | List[Msg] | None,
        **kwargs: Any,
    ) -> List[Msg | Exception]:
        """Execute agents one by one (each still receives the *same* input)."""
        results: List[Msg | Exception] = []

        for idx, agent in enumerate(self.agents):
            agent_id = getattr(agent, "agent_id", str(idx))
            await self._run_hooks(
                "pre_agent_call",
                agent=agent,
                step=idx,
                msg=msg,
            )

            try:
                if self.timeout:
                    result = await asyncio.wait_for(
                        agent(deepcopy(msg)),
                        timeout=self.timeout,
                    )
                else:
                    result = await agent(deepcopy(msg))
            except asyncio.TimeoutError as exc:
                await self._run_hooks(
                    "on_timeout",
                    agent=agent,
                    step=idx,
                    timeout=self.timeout,
                )
                results.append(exc)
                continue
            except Exception as exc:
                await self._run_hooks(
                    "on_error",
                    agent=agent,
                    step=idx,
                    error=exc,
                )
                results.append(exc)
                continue

            await self._run_hooks(
                "post_agent_call",
                agent=agent,
                step=idx,
                msg=result,
            )

            # Save checkpoint
            await self._state_manager.save_checkpoint(
                pipeline_id=self.pipeline_id,
                step=idx,
                agent_id=agent_id,
                input_msg=msg if isinstance(msg, Msg) else None,
                output_msg=result,
                metadata={
                    "pipeline_name": self.name,
                    "mode": "sequential",
                    "status": "completed",
                },
            )
            results.append(result)

        return results

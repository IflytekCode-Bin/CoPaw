# -*- coding: utf-8 -*-
"""Loop Pipeline — repeat agent execution until an exit condition is met.

Runs a sequence of agents in a loop, passing the output of one iteration
as the input to the next, until the exit condition returns True or the
maximum iteration count is reached.

Use-cases: iterative refinement, self-critique loops, negotiation rounds.
"""

import logging
from copy import deepcopy
from typing import Any, Callable, List, Optional, TYPE_CHECKING

from agentscope.message import Msg

from .base import PipelineBase, PipelineStatus

if TYPE_CHECKING:
    from .state_manager import StateManager

logger = logging.getLogger(__name__)

# Type alias: exit condition receives (current_msg, iteration_index)
# and returns True when the loop should *stop*.
ExitConditionFn = Callable[[Msg | List[Msg] | None, int], bool]


class LoopPipeline(PipelineBase):
    """Repeat a sequence of agents until an exit condition is satisfied.

    Example::

        def done(msg, iteration):
            return iteration >= 3 or "APPROVED" in str(msg.content)

        pipeline = LoopPipeline(
            name="refine",
            agents=[drafter, critic],
            exit_condition=done,
            max_iterations=5,
        )
        result = await pipeline.execute(
            msg=Msg("user", "Write an essay on AI safety", "user"),
        )
    """

    def __init__(
        self,
        name: str,
        agents: List[Any],
        exit_condition: ExitConditionFn,
        max_iterations: int = 10,
        state_manager: Optional["StateManager"] = None,
        hooks: Optional[dict] = None,
    ) -> None:
        """
        Args:
            name: Pipeline name.
            agents: Ordered list of agents executed each iteration.
            exit_condition: ``(msg, iteration) -> bool``; returns True
                when the loop should stop.
            max_iterations: Hard upper bound on loop count (safety net).
            state_manager: Optional state persistence backend.
            hooks: Optional dict of hook_type → list[callable].
        """
        super().__init__(
            name=name,
            agents=agents,
            state_manager=state_manager,
            hooks=hooks,
        )
        self.exit_condition = exit_condition
        self.max_iterations = max_iterations

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        msg: Msg | List[Msg] | None = None,
        **kwargs: Any,
    ) -> Msg | List[Msg] | None:
        """Run the loop pipeline.

        Args:
            msg: Initial input message.
            **kwargs: Additional keyword arguments forwarded to each agent.

        Returns:
            The output message from the last completed iteration.
        """
        self._set_status(PipelineStatus.RUNNING)
        await self._run_hooks("pre_pipeline", msg=msg)

        current_msg = msg
        iteration = 0

        try:
            while iteration < self.max_iterations:
                # Check exit condition *before* executing the round
                if self.exit_condition(current_msg, iteration):
                    logger.info(
                        "Pipeline '%s' exit condition met at iteration %d",
                        self.name,
                        iteration,
                    )
                    break

                logger.debug(
                    "Pipeline '%s' iteration %d/%d",
                    self.name,
                    iteration + 1,
                    self.max_iterations,
                )

                # Run all agents in sequence for this iteration
                for step_idx, agent in enumerate(self.agents):
                    agent_id = getattr(agent, "agent_id", str(step_idx))
                    global_step = iteration * len(self.agents) + step_idx

                    await self._run_hooks(
                        "pre_agent_call",
                        agent=agent,
                        step=global_step,
                        iteration=iteration,
                        msg=current_msg,
                    )

                    try:
                        result = await agent(deepcopy(current_msg))
                    except Exception as exc:
                        await self._run_hooks(
                            "on_error",
                            agent=agent,
                            step=global_step,
                            iteration=iteration,
                            error=exc,
                        )
                        # Save failure
                        await self._state_manager.save_checkpoint(
                            pipeline_id=self.pipeline_id,
                            step=global_step,
                            agent_id=agent_id,
                            input_msg=current_msg,
                            metadata={
                                "pipeline_name": self.name,
                                "iteration": iteration,
                                "status": "failed",
                                "error": str(exc),
                            },
                        )
                        self._set_status(PipelineStatus.FAILED)
                        raise

                    await self._run_hooks(
                        "post_agent_call",
                        agent=agent,
                        step=global_step,
                        iteration=iteration,
                        msg=result,
                    )

                    # Checkpoint
                    await self._state_manager.save_checkpoint(
                        pipeline_id=self.pipeline_id,
                        step=global_step,
                        agent_id=agent_id,
                        input_msg=current_msg,
                        output_msg=result,
                        metadata={
                            "pipeline_name": self.name,
                            "iteration": iteration,
                            "step_in_iteration": step_idx,
                            "status": "completed",
                        },
                    )

                    current_msg = result

                iteration += 1

            if iteration >= self.max_iterations:
                logger.warning(
                    "Pipeline '%s' reached max iterations (%d)",
                    self.name,
                    self.max_iterations,
                )

        except Exception:
            raise
        else:
            self._set_status(PipelineStatus.COMPLETED)

        await self._run_hooks(
            "post_pipeline",
            msg=current_msg,
            iterations=iteration,
        )
        return current_msg

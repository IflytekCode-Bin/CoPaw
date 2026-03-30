# -*- coding: utf-8 -*-
"""Sequential Pipeline — execute agents one after another.

Each agent receives the output of the previous agent as its input.
This is the most common pattern for multi-step task workflows such as:
    analyse → draft → review → finalise
"""

import logging
from copy import deepcopy
from typing import Any, List, Optional, TYPE_CHECKING

from agentscope.message import Msg

from .base import PipelineBase, PipelineStatus

if TYPE_CHECKING:
    from .state_manager import StateManager

logger = logging.getLogger(__name__)


class SequentialPipeline(PipelineBase):
    """Execute agents sequentially, passing each output as the next input.

    Example::

        pipeline = SequentialPipeline(
            name="report_gen",
            agents=[analyst, writer, reviewer],
        )
        result = await pipeline.execute(
            msg=Msg("user", "Analyse Q4 sales", "user"),
        )
    """

    def __init__(
        self,
        name: str,
        agents: List[Any],
        state_manager: Optional["StateManager"] = None,
        hooks: Optional[dict] = None,
        *,
        resume_from_step: int | None = None,
    ) -> None:
        """
        Args:
            name: Pipeline name.
            agents: Ordered list of agents.
            state_manager: Optional state persistence backend.
            hooks: Optional dict of hook_type → list[callable].
            resume_from_step: If set, skip agents before this step index
                and start execution from the given step using the last
                checkpoint as input.
        """
        super().__init__(
            name=name,
            agents=agents,
            state_manager=state_manager,
            hooks=hooks,
        )
        self._resume_from_step = resume_from_step

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        msg: Msg | List[Msg] | None = None,
        **kwargs: Any,
    ) -> Msg | List[Msg] | None:
        """Run the sequential pipeline.

        Args:
            msg: Initial message passed to the first agent.
            **kwargs: Additional keyword arguments forwarded to each agent.

        Returns:
            The final output message from the last agent, or ``None``
            if the pipeline was cancelled.
        """
        self._set_status(PipelineStatus.RUNNING)
        await self._run_hooks("pre_pipeline", msg=msg)

        current_msg = msg

        # Handle resume from checkpoint
        start_step = 0
        if self._resume_from_step is not None:
            checkpoint = await self._state_manager.load_checkpoint(
                pipeline_id=self.pipeline_id,
                step=self._resume_from_step - 1,
            )
            if checkpoint and checkpoint.get("output_msg"):
                current_msg = Msg.from_dict(checkpoint["output_msg"])
                start_step = self._resume_from_step
                logger.info(
                    "Resuming pipeline '%s' from step %d",
                    self.name,
                    start_step,
                )

        try:
            for step_idx, agent in enumerate(self.agents):
                if step_idx < start_step:
                    continue

                agent_id = getattr(agent, "agent_id", str(step_idx))

                # Save pre-execution checkpoint
                await self._state_manager.save_checkpoint(
                    pipeline_id=self.pipeline_id,
                    step=step_idx,
                    agent_id=agent_id,
                    input_msg=current_msg,
                    metadata={
                        "pipeline_name": self.name,
                        "total_steps": len(self.agents),
                        "status": "in_progress",
                    },
                )

                # Pre-agent hook
                await self._run_hooks(
                    "pre_agent_call",
                    agent=agent,
                    step=step_idx,
                    msg=current_msg,
                )

                # Execute agent
                logger.debug(
                    "Pipeline '%s' step %d/%d → agent '%s'",
                    self.name,
                    step_idx + 1,
                    len(self.agents),
                    agent_id,
                )
                try:
                    result = await agent(deepcopy(current_msg))
                except Exception as exc:
                    await self._run_hooks(
                        "on_error",
                        agent=agent,
                        step=step_idx,
                        error=exc,
                    )
                    # Save failure checkpoint
                    await self._state_manager.save_checkpoint(
                        pipeline_id=self.pipeline_id,
                        step=step_idx,
                        agent_id=agent_id,
                        input_msg=current_msg,
                        metadata={
                            "pipeline_name": self.name,
                            "status": "failed",
                            "error": str(exc),
                        },
                    )
                    self._set_status(PipelineStatus.FAILED)
                    await self._run_hooks(
                        "on_state_change",
                        old_status=PipelineStatus.RUNNING,
                        new_status=PipelineStatus.FAILED,
                    )
                    raise

                # Post-agent hook
                await self._run_hooks(
                    "post_agent_call",
                    agent=agent,
                    step=step_idx,
                    msg=result,
                )

                # Save post-execution checkpoint
                await self._state_manager.save_checkpoint(
                    pipeline_id=self.pipeline_id,
                    step=step_idx,
                    agent_id=agent_id,
                    input_msg=current_msg,
                    output_msg=result,
                    metadata={
                        "pipeline_name": self.name,
                        "status": "completed",
                    },
                )

                current_msg = result

        except Exception:
            # Status already set in the inner handler
            raise
        else:
            self._set_status(PipelineStatus.COMPLETED)

        await self._run_hooks("post_pipeline", msg=current_msg)
        return current_msg

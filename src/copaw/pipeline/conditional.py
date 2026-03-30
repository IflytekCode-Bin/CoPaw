# -*- coding: utf-8 -*-
"""Conditional Pipeline — route execution based on a condition.

Evaluates a predicate against the input message and delegates to
one of two sub-pipelines (true_branch / false_branch).

Use-cases: task routing, complexity-based dispatch, A/B testing.
"""

import logging
from typing import Any, Callable, List, Optional, TYPE_CHECKING

from agentscope.message import Msg

from .base import PipelineBase, PipelineStatus

if TYPE_CHECKING:
    from .state_manager import StateManager

logger = logging.getLogger(__name__)

# Type alias: condition receives a Msg and returns a bool
ConditionFn = Callable[[Msg | List[Msg] | None], bool]


class ConditionalPipeline(PipelineBase):
    """Choose between two sub-pipelines based on a condition.

    Example::

        def is_complex(msg):
            return len(str(msg.content)) > 500

        pipeline = ConditionalPipeline(
            name="task_router",
            condition=is_complex,
            true_branch=SequentialPipeline("complex", [planner, exec, val]),
            false_branch=SequentialPipeline("simple", [simple_agent]),
        )
        result = await pipeline.execute(msg=user_msg)
    """

    def __init__(
        self,
        name: str,
        condition: ConditionFn,
        true_branch: PipelineBase,
        false_branch: PipelineBase,
        state_manager: Optional["StateManager"] = None,
        hooks: Optional[dict] = None,
    ) -> None:
        """
        Args:
            name: Pipeline name.
            condition: A callable ``(msg) -> bool``.
            true_branch: Pipeline to execute when condition is True.
            false_branch: Pipeline to execute when condition is False.
            state_manager: Optional state persistence backend.
            hooks: Optional dict of hook_type → list[callable].
        """
        # agents list stays empty — the branches own their agents
        super().__init__(
            name=name,
            agents=[],
            state_manager=state_manager,
            hooks=hooks,
        )
        self.condition = condition
        self.true_branch = true_branch
        self.false_branch = false_branch

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        msg: Msg | List[Msg] | None = None,
        **kwargs: Any,
    ) -> Msg | List[Msg] | None:
        """Evaluate condition and delegate to the matching branch.

        Args:
            msg: Input message to evaluate.
            **kwargs: Forwarded to the chosen sub-pipeline.

        Returns:
            Output from the selected branch.
        """
        self._set_status(PipelineStatus.RUNNING)
        await self._run_hooks("pre_pipeline", msg=msg)

        # Evaluate
        try:
            branch_taken = self.condition(msg)
        except Exception as exc:
            logger.error(
                "Condition evaluation failed in pipeline '%s': %s",
                self.name,
                exc,
            )
            await self._run_hooks("on_error", error=exc, step="condition")
            self._set_status(PipelineStatus.FAILED)
            raise

        branch_name = "true_branch" if branch_taken else "false_branch"
        selected = self.true_branch if branch_taken else self.false_branch
        logger.debug(
            "Pipeline '%s' condition → %s (executing '%s')",
            self.name,
            branch_taken,
            selected.name,
        )

        # Save routing decision
        await self._state_manager.save_checkpoint(
            pipeline_id=self.pipeline_id,
            step=0,
            agent_id=f"condition:{branch_name}",
            input_msg=msg if isinstance(msg, Msg) else None,
            metadata={
                "pipeline_name": self.name,
                "branch_taken": branch_name,
                "condition_result": branch_taken,
            },
        )

        # Delegate
        try:
            result = await selected.execute(msg, **kwargs)
        except Exception as exc:
            self._set_status(PipelineStatus.FAILED)
            raise

        self._set_status(PipelineStatus.COMPLETED)
        await self._run_hooks("post_pipeline", msg=result)
        return result

"""Recursive pipeline executor with nested sub-pipeline support.

This module provides the execution engine for CoPaw pipelines,
supporting infinite nesting of sub-pipelines.

Architecture
~~~~~~~~~~~~
Every Pipeline is a ``Msg → Msg`` async callable, which means:

    - A ``SequentialPipeline`` can contain agents AND sub-pipelines
    - A ``FanoutPipeline`` can broadcast to agents AND sub-pipelines
    - Sub-pipelines are resolved lazily at execution time

This is natively supported by AgentScope because ``Pipeline.__call__``
has the same signature as ``AgentBase.__call__``:

    ``async def __call__(self, msg: Msg) -> Msg``
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from agentscope.message import Msg
from agentscope.agent import AgentBase

from copaw.pipeline import (
    SequentialPipeline,
    FanoutPipeline,
    ConditionalPipeline,
    LoopPipeline,
)
from copaw.pipeline.state_manager import StateManager
from copaw.pipeline.base import PipelineStatus

if TYPE_CHECKING:
    from copaw.app.pipeline_manager import PipelineManager
    from copaw.app.multi_agent_manager import MultiAgentManager

logger = logging.getLogger(__name__)

# ─── Agent & Pipeline Resolution ───────────────────────────────────

async def _resolve_agents(
    agent_ids: List[str],
    multi_agent_manager: Any = None,
) -> List[AgentBase]:
    """Resolve agent IDs to AgentBase instances.

    Args:
        agent_ids: List of agent IDs.
        multi_agent_manager: MultiAgentManager instance to get workspaces.

    Returns:
        List of resolved AgentBase instances.
    """
    from ..config.config import load_agent_config
    from ..agents.react_agent import CoPawAgent

    agents = []
    for aid in agent_ids:
        try:
            if multi_agent_manager is not None:
                # Get workspace from manager (lazy loading)
                workspace = await multi_agent_manager.get_agent(aid)
                # Get agent config
                agent_config = load_agent_config(aid)
                # Create CoPawAgent instance
                agent = CoPawAgent(
                    agent_config=agent_config,
                    workspace_dir=workspace.workspace_dir,
                )
                if agent is not None:
                    agents.append(agent)
                else:
                    logger.warning("Agent %s creation returned None, skipping", aid)
            else:
                logger.error("No multi_agent_manager provided, cannot resolve agent %s", aid)
        except Exception as e:
            logger.error("Failed to resolve agent %s: %s", aid, e)
    return agents


async def _resolve_sub_pipelines(
    sub_pipeline_ids: List[str],
    pipeline_manager: "PipelineManager",
    multi_agent_manager: Any = None,
) -> List[Any]:
    """Resolve sub-pipeline IDs to pipeline instances.

    Args:
        sub_pipeline_ids: List of sub-pipeline IDs.
        pipeline_manager: PipelineManager instance.
        multi_agent_manager: MultiAgentManager instance.

    Returns:
        List of resolved pipeline instances (which are callable).
    """
    pipelines = []
    for pid in sub_pipeline_ids:
        try:
            pipeline_def = pipeline_manager.get(pid)
            if pipeline_def is None:
                logger.warning("Sub-pipeline %s not found, skipping", pid)
                continue
            pipeline_instance = await build_pipeline_async(
                pipeline_def, pipeline_manager, multi_agent_manager
            )
            if pipeline_instance is not None:
                pipelines.append(pipeline_instance)
        except Exception as e:
            logger.error("Failed to resolve sub-pipeline %s: %s", pid, e)
    return pipelines


# ─── Pipeline Builder ──────────────────────────────────────────────

def build_pipeline(
    pipeline_def: dict,
    pipeline_manager: "PipelineManager",
    agent_factory: Any = None,
) -> Optional[Any]:
    """Build a pipeline instance from a definition dict.

    This function builds pipelines synchronously using agents passed
    directly (not resolved via MultiAgentManager). It is kept for
    backward compatibility and simple test scenarios.

    For production use, prefer ``build_pipeline_async``.

    Args:
        pipeline_def: Pipeline definition from storage.
        pipeline_manager: PipelineManager for resolving sub-pipelines.
        agent_factory: Callable or manager that creates agent instances.

    Returns:
        Built pipeline instance, or None if construction failed.
    """
    name = pipeline_def.get("name", "unnamed")
    pipeline_type = pipeline_def.get("type", "sequential")
    agent_ids = pipeline_def.get("agents", [])
    sub_pipeline_ids = pipeline_def.get("sub_pipelines", [])

    # Resolve agents (sync fallback)
    agents = []
    if agent_factory is not None:
        for aid in agent_ids:
            try:
                if callable(agent_factory):
                    agent = agent_factory(aid)
                else:
                    agent = agent_factory.get_agent(aid)
                if agent is not None:
                    agents.append(agent)
            except Exception as e:
                logger.error("Failed to resolve agent %s: %s", aid, e)

    # Resolve sub-pipelines (sync fallback - may not work for nested async)
    sub_pipelines = []
    for pid in sub_pipeline_ids:
        try:
            child_def = pipeline_manager.get(pid)
            if child_def:
                child = build_pipeline(child_def, pipeline_manager, agent_factory)
                if child is not None:
                    sub_pipelines.append(child)
        except Exception as e:
            logger.error("Failed to resolve sub-pipeline %s: %s", pid, e)

    execution_units = agents + sub_pipelines

    if not execution_units:
        logger.warning("Pipeline '%s' has no agents or sub-pipelines", name)
        return None

    # Build based on type
    state_manager = StateManager()

    if pipeline_type == "sequential":
        return SequentialPipeline(
            name=name,
            agents=execution_units,
            state_manager=state_manager,
        )
    elif pipeline_type == "fanout":
        return FanoutPipeline(
            name=name,
            agents=execution_units,
            state_manager=state_manager,
        )
    elif pipeline_type == "conditional":
        return ConditionalPipeline(
            name=name,
            agents=execution_units,
            state_manager=state_manager,
        )
    elif pipeline_type == "loop":
        return LoopPipeline(
            name=name,
            agents=execution_units,
            state_manager=state_manager,
        )
    else:
        logger.error("Unknown pipeline type: %s", pipeline_type)
        return None


async def build_pipeline_async(
    pipeline_def: dict,
    pipeline_manager: "PipelineManager",
    multi_agent_manager: Any = None,
) -> Optional[Any]:
    """Build a pipeline instance from a definition dict (async version).

    This function recursively builds pipelines: if a pipeline has
    sub-pipelines, they are also built and included.

    Args:
        pipeline_def: Pipeline definition from storage.
        pipeline_manager: PipelineManager for resolving sub-pipelines.
        multi_agent_manager: MultiAgentManager for resolving agent workspaces.

    Returns:
        Built pipeline instance, or None if construction failed.
    """
    name = pipeline_def.get("name", "unnamed")
    pipeline_type = pipeline_def.get("type", "sequential")
    agent_ids = pipeline_def.get("agents", [])
    sub_pipeline_ids = pipeline_def.get("sub_pipelines", [])

    # Resolve agents (async via MultiAgentManager)
    agents = await _resolve_agents(agent_ids, multi_agent_manager)

    # Resolve sub-pipelines (recursive!)
    sub_pipelines = await _resolve_sub_pipelines(
        sub_pipeline_ids, pipeline_manager, multi_agent_manager
    )

    # Merge agents and sub-pipelines into execution list
    # Sub-pipelines are callable just like agents
    execution_units = agents + sub_pipelines

    if not execution_units:
        logger.warning("Pipeline '%s' has no agents or sub-pipelines", name)
        return None

    # Build based on type
    state_manager = StateManager()

    if pipeline_type == "sequential":
        return SequentialPipeline(
            name=name,
            agents=execution_units,
            state_manager=state_manager,
        )
    elif pipeline_type == "fanout":
        return FanoutPipeline(
            name=name,
            agents=execution_units,
            state_manager=state_manager,
        )
    elif pipeline_type == "conditional":
        return ConditionalPipeline(
            name=name,
            agents=execution_units,
            state_manager=state_manager,
        )
    elif pipeline_type == "loop":
        return LoopPipeline(
            name=name,
            agents=execution_units,
            state_manager=state_manager,
        )
    else:
        logger.error("Unknown pipeline type: %s", pipeline_type)
        return None


# ─── Recursive Executor ────────────────────────────────────────────

async def execute_nested_pipeline(
    pipeline_id: str,
    msg: Optional[Msg] = None,
    pipeline_manager: Optional["PipelineManager"] = None,
    multi_agent_manager: Optional["MultiAgentManager"] = None,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Execute a pipeline with nested sub-pipeline support.

    This is the main entry point for executing pipelines. It:
    1. Loads the pipeline definition
    2. Builds the pipeline (recursively resolving sub-pipelines)
    3. Executes it

    Args:
        pipeline_id: The pipeline ID to execute.
        msg: Initial message to pass to the pipeline.
        pipeline_manager: PipelineManager instance.
        multi_agent_manager: MultiAgentManager instance for agent resolution.
        context: Optional execution context.
        **kwargs: Additional arguments passed to pipeline.execute().

    Returns:
        Dict with execution result, status, and any errors.
    """
    if pipeline_manager is None:
        from copaw.app.pipeline_manager import get_pipeline_manager
        pipeline_manager = get_pipeline_manager()

    pipeline_def = pipeline_manager.get(pipeline_id)
    if pipeline_def is None:
        return {
            "status": "failed",
            "error": f"Pipeline {pipeline_id} not found",
            "result": None,
        }

    # Validate nesting depth before execution
    try:
        check_nesting_depth(pipeline_id, pipeline_manager)
    except ValueError as e:
        return {
            "status": "failed",
            "error": f"Invalid pipeline structure: {e}",
            "result": None,
        }

    try:
        # Build the pipeline (recursively resolves sub-pipelines)
        pipeline = await build_pipeline_async(
            pipeline_def, pipeline_manager, multi_agent_manager
        )

        if pipeline is None:
            return {
                "status": "failed",
                "error": "Pipeline has no agents or sub-pipelines",
                "result": None,
            }

        # Execute
        input_msg = msg or Msg("system", "Execute pipeline", "system")
        result_msg = await pipeline.execute(msg=input_msg, **kwargs)

        # Update pipeline status to completed
        pipeline_manager.update(pipeline_id, name=pipeline_def["name"])

        return {
            "status": "completed",
            "result": result_msg.to_dict() if result_msg else None,
            "error": None,
        }

    except Exception as e:
        logger.error("Pipeline execution failed: %s", e, exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "result": None,
        }


# ─── Depth Checker ─────────────────────────────────────────────────

def check_nesting_depth(
    pipeline_id: str,
    pipeline_manager: "PipelineManager",
    max_depth: int = 10,
    _current_depth: int = 0,
    _visited: Optional[set] = None,
) -> int:
    """Check the nesting depth of a pipeline.

    Args:
        pipeline_id: Root pipeline ID.
        pipeline_manager: PipelineManager instance.
        max_depth: Maximum allowed nesting depth.
        _current_depth: Current depth (internal).
        _visited: Set of visited pipeline IDs for cycle detection (internal).

    Returns:
        The nesting depth.

    Raises:
        ValueError: If max_depth is exceeded or a cycle is detected.
    """
    if _visited is None:
        _visited = set()

    if pipeline_id in _visited:
        raise ValueError(f"Cycle detected in pipeline nesting: {pipeline_id}")

    if _current_depth > max_depth:
        raise ValueError(f"Max nesting depth ({max_depth}) exceeded")

    _visited.add(pipeline_id)

    pipeline_def = pipeline_manager.get(pipeline_id)
    if pipeline_def is None:
        return _current_depth

    sub_pipelines = pipeline_def.get("sub_pipelines", [])
    if not sub_pipelines:
        return _current_depth

    max_child_depth = _current_depth
    for child_id in sub_pipelines:
        child_depth = check_nesting_depth(
            child_id, pipeline_manager, max_depth,
            _current_depth + 1, _visited
        )
        max_child_depth = max(max_child_depth, child_depth)

    return max_child_depth

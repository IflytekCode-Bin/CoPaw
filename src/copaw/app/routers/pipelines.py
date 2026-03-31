# -*- coding: utf-8 -*-
"""Pipeline management APIs."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...pipeline import (
    SequentialPipeline,
    FanoutPipeline,
    ConditionalPipeline,
    LoopPipeline,
    StateManager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

# Global state manager
state_manager = StateManager()

# In-memory pipeline registry (TODO: persist to database)
pipeline_registry: Dict[str, Dict[str, Any]] = {}


# ── Schemas ───────────────────────────────────────────────────────────────


class PipelineType(str):
    """Pipeline type enum."""

    SEQUENTIAL = "sequential"
    FANOUT = "fanout"
    CONDITIONAL = "conditional"
    LOOP = "loop"


class PipelineCreate(BaseModel):
    """Pipeline creation request."""

    name: str = Field(..., description="Pipeline name")
    type: str = Field(..., description="Pipeline type")
    agents: List[str] = Field(..., description="Agent IDs")
    description: Optional[str] = Field(None, description="Description")
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Pipeline-specific config",
    )


class PipelineUpdate(BaseModel):
    """Pipeline update request."""

    name: Optional[str] = None
    agents: Optional[List[str]] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class PipelineExecute(BaseModel):
    """Pipeline execution request."""

    input: str = Field(..., description="Input message content")
    kwargs: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional execution parameters",
    )


class PipelineResponse(BaseModel):
    """Pipeline response."""

    id: str
    name: str
    type: str
    agents: List[str]
    description: Optional[str] = None
    status: str = "pending"
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class PipelineExecutionResponse(BaseModel):
    """Pipeline execution response."""

    pipeline_id: str
    execution_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/", response_model=List[PipelineResponse])
async def list_pipelines():
    """List all pipelines."""
    return [
        PipelineResponse(
            id=pid,
            name=p["name"],
            type=p["type"],
            agents=p["agents"],
            description=p.get("description"),
            status=p.get("status", "pending"),
            config=p.get("config", {}),
            created_at=p["created_at"],
            updated_at=p["updated_at"],
        )
        for pid, p in pipeline_registry.items()
    ]


@router.post("/", response_model=PipelineResponse)
async def create_pipeline(data: PipelineCreate):
    """Create a new pipeline."""
    import shortuuid

    pipeline_id = f"pl_{shortuuid.uuid()[:12]}"
    now = datetime.now().isoformat()

    pipeline_data = {
        "name": data.name,
        "type": data.type,
        "agents": data.agents,
        "description": data.description,
        "config": data.config,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }

    pipeline_registry[pipeline_id] = pipeline_data

    logger.info(f"Created pipeline {pipeline_id}: {data.name}")

    return PipelineResponse(
        id=pipeline_id,
        **pipeline_data,
    )


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: str):
    """Get pipeline by ID."""
    if pipeline_id not in pipeline_registry:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    p = pipeline_registry[pipeline_id]
    return PipelineResponse(
        id=pipeline_id,
        name=p["name"],
        type=p["type"],
        agents=p["agents"],
        description=p.get("description"),
        status=p.get("status", "pending"),
        config=p.get("config", {}),
        created_at=p["created_at"],
        updated_at=p["updated_at"],
    )


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(pipeline_id: str, data: PipelineUpdate):
    """Update pipeline."""
    if pipeline_id not in pipeline_registry:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    p = pipeline_registry[pipeline_id]

    if data.name is not None:
        p["name"] = data.name
    if data.agents is not None:
        p["agents"] = data.agents
    if data.description is not None:
        p["description"] = data.description
    if data.config is not None:
        p["config"] = data.config

    p["updated_at"] = datetime.now().isoformat()

    logger.info(f"Updated pipeline {pipeline_id}")

    return PipelineResponse(
        id=pipeline_id,
        **p,
    )


@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    """Delete pipeline."""
    if pipeline_id not in pipeline_registry:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    del pipeline_registry[pipeline_id]
    logger.info(f"Deleted pipeline {pipeline_id}")

    return {"message": "Pipeline deleted successfully"}


@router.post("/{pipeline_id}/execute", response_model=PipelineExecutionResponse)
async def execute_pipeline(pipeline_id: str, data: PipelineExecute):
    """Execute a pipeline.

    Note: This is a simplified synchronous execution.
    For production, consider using background tasks or a task queue.
    """
    if pipeline_id not in pipeline_registry:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    p = pipeline_registry[pipeline_id]

    import shortuuid
    from agentscope.message import Msg

    execution_id = f"exec_{shortuuid.uuid()[:12]}"
    started_at = datetime.now().isoformat()

    try:
        # Create input message
        input_msg = Msg(
            name="user",
            content=data.input,
            role="user",
        )

        # TODO: Load actual agents from agent registry
        # For now, return mock response
        logger.info(
            f"Executing pipeline {pipeline_id} (type={p['type']}, "
            f"agents={p['agents']})",
        )

        # Mock execution
        result = {
            "message": "Pipeline execution completed (mock)",
            "pipeline_type": p["type"],
            "agents": p["agents"],
        }

        completed_at = datetime.now().isoformat()

        # Update pipeline status
        p["status"] = "completed"
        p["updated_at"] = completed_at

        return PipelineExecutionResponse(
            pipeline_id=pipeline_id,
            execution_id=execution_id,
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            result=result,
        )

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)

        # Update pipeline status
        p["status"] = "failed"
        p["updated_at"] = datetime.now().isoformat()

        return PipelineExecutionResponse(
            pipeline_id=pipeline_id,
            execution_id=execution_id,
            status="failed",
            started_at=started_at,
            error=str(e),
        )


@router.get("/{pipeline_id}/history", response_model=List[Dict[str, Any]])
async def get_pipeline_history(pipeline_id: str):
    """Get pipeline execution history."""
    if pipeline_id not in pipeline_registry:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    try:
        history = await state_manager.get_pipeline_history(pipeline_id)
        return history
    except Exception as e:
        logger.error(f"Failed to get pipeline history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve pipeline history",
        )


@router.get("/executions/list")
async def list_all_executions():
    """List all pipeline executions."""
    try:
        pipeline_ids = await state_manager.list_pipelines()
        all_executions = []

        for pid in pipeline_ids:
            history = await state_manager.get_pipeline_history(pid)
            all_executions.extend(history)

        return all_executions
    except Exception as e:
        logger.error(f"Failed to list executions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to list executions",
        )

"""Pipeline management API routes."""

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

# Absolute imports
from copaw.app.pipeline_manager import get_pipeline_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class PipelineConfig(BaseModel):
    """Pipeline configuration."""

    leader_agent: Optional[str] = None
    owner_agent_id: Optional[str] = None
    max_retries: int = 3
    timeout: Optional[int] = None


class CreatePipelineRequest(BaseModel):
    """Request to create a pipeline."""

    name: str = Field(..., description="Pipeline name")
    type: str = Field(..., description="Pipeline type")
    agents: List[str] = Field(..., description="List of agent IDs")
    description: Optional[str] = Field(None, description="Pipeline description")
    config: Optional[PipelineConfig] = Field(None, description="Pipeline configuration")
    owner_agent_id: Optional[str] = Field(None, description="Owner agent ID")
    sub_pipelines: List[str] = Field(default_factory=list, description="Sub-pipeline IDs")
    parent_pipeline_id: Optional[str] = Field(None, description="Parent pipeline ID for nesting")


class UpdatePipelineRequest(BaseModel):
    """Request to update a pipeline."""

    name: Optional[str] = None
    type: Optional[str] = None
    agents: Optional[List[str]] = None
    description: Optional[str] = None
    config: Optional[PipelineConfig] = None
    sub_pipelines: Optional[List[str]] = None


class PipelineResponse(BaseModel):
    """Pipeline response."""

    id: str
    name: str
    type: str
    agents: List[str]
    description: Optional[str] = None
    config: Optional[dict] = None
    status: str = "pending"
    owner_agent_id: Optional[str] = None
    sub_pipelines: List[str] = []
    parent_pipeline_id: Optional[str] = None
    created_at: str
    updated_at: str


class ExecutePipelineRequest(BaseModel):
    """Request to execute a pipeline."""

    message: str = Field(..., description="Input message")
    context: Optional[dict] = Field(None, description="Execution context")


class PipelineExecutionResponse(BaseModel):
    """Pipeline execution response."""

    id: str
    pipeline_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


@router.get("/", response_model=List[PipelineResponse])
async def list_pipelines(
    owner_agent_id: Optional[str] = Query(None, description="Filter by owner agent ID"),
    parent_pipeline_id: Optional[str] = Query(None, description="Filter by parent pipeline ID"),
):
    """List all pipelines, optionally filtered."""
    manager = get_pipeline_manager()
    pipelines = manager.list_all(
        owner_agent_id=owner_agent_id,
        parent_pipeline_id=parent_pipeline_id,
    )
    return pipelines


@router.post("/", response_model=PipelineResponse)
async def create_pipeline(request: CreatePipelineRequest):
    """Create a new pipeline."""
    manager = get_pipeline_manager()
    config_dict = {}
    if request.config:
        config_dict = request.config.model_dump()

    pipeline = manager.create(
        name=request.name,
        pipeline_type=request.type,
        agents=request.agents,
        description=request.description,
        config=config_dict,
        owner_agent_id=request.owner_agent_id,
        sub_pipelines=request.sub_pipelines,
        parent_pipeline_id=request.parent_pipeline_id,
    )
    return pipeline


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: str):
    """Get pipeline by ID."""
    manager = get_pipeline_manager()
    pipeline = manager.get(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(pipeline_id: str, request: UpdatePipelineRequest):
    """Update a pipeline."""
    manager = get_pipeline_manager()
    config_dict = None
    if request.config:
        config_dict = request.config.model_dump()

    pipeline = manager.update(
        pipeline_id=pipeline_id,
        name=request.name,
        pipeline_type=request.type,
        agents=request.agents,
        description=request.description,
        config=config_dict,
        sub_pipelines=request.sub_pipelines,
    )
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    """Delete a pipeline."""
    manager = get_pipeline_manager()
    deleted = manager.delete(pipeline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"message": "Pipeline deleted successfully"}


@router.post("/{pipeline_id}/execute", response_model=PipelineExecutionResponse)
async def execute_pipeline(
    pipeline_id: str,
    request: ExecutePipelineRequest,
    req: Request,
):
    """Execute a pipeline with nested sub-pipeline support."""
    from datetime import datetime as _dt
    from ..pipeline_manager import get_pipeline_manager
    from agentscope.message import Msg

    manager = get_pipeline_manager()
    pipeline = manager.get(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    execution_id = f"exec_{pipeline_id}_{_dt.utcnow().strftime('%Y%m%d%H%M%S')}"

    try:
        # Try to get MultiAgentManager from request state if available
        multi_agent_manager = None
        if hasattr(req.app.state, "multi_agent_manager"):
            multi_agent_manager = req.app.state.multi_agent_manager

        from copaw.app.pipeline_executor import execute_nested_pipeline

        input_msg = Msg("user", request.message, "user")

        result = await execute_nested_pipeline(
            pipeline_id=pipeline_id,
            msg=input_msg,
            pipeline_manager=manager,
            multi_agent_manager=multi_agent_manager,
            context=request.context,
        )

        return PipelineExecutionResponse(
            id=execution_id,
            pipeline_id=pipeline_id,
            status=result.get("status", "completed"),
            result=result.get("result"),
            error=result.get("error"),
            started_at=_dt.utcnow().isoformat(),
            completed_at=_dt.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error("Pipeline execution failed: %s", e)
        return PipelineExecutionResponse(
            id=execution_id,
            pipeline_id=pipeline_id,
            status="failed",
            result=None,
            error=str(e),
            started_at=_dt.utcnow().isoformat(),
            completed_at=_dt.utcnow().isoformat(),
        )


@router.get("/{pipeline_id}/history", response_model=List[PipelineExecutionResponse])
async def get_pipeline_history(pipeline_id: str):
    """Get execution history for a pipeline (stub)."""
    manager = get_pipeline_manager()
    pipeline = manager.get(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return []


@router.get("/{pipeline_id}/depth")
async def get_nesting_depth(pipeline_id: str):
    """Check the nesting depth of a pipeline."""
    manager = get_pipeline_manager()
    pipeline = manager.get(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    try:
        from ..pipeline_executor import check_nesting_depth
        depth = check_nesting_depth(pipeline_id, manager)
        return {"pipeline_id": pipeline_id, "depth": depth}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class PipelineSelectOption(BaseModel):
    """Option for pipeline select dropdown."""
    value: str
    label: str
    owner_agent_id: Optional[str] = None
    sub_pipeline_count: int = 0


@router.get("/select-options", response_model=List[PipelineSelectOption])
async def get_pipeline_select_options(
    exclude_id: Optional[str] = Query(None, description="Pipeline ID to exclude"),
):
    """Get all pipelines as select options for form dropdowns."""
    manager = get_pipeline_manager()
    all_pipelines = manager.list_all()
    options = []
    for p in all_pipelines:
        if p["id"] == exclude_id:
            continue
        options.append(PipelineSelectOption(
            value=p["id"],
            label=p["name"],
            owner_agent_id=p.get("owner_agent_id"),
            sub_pipeline_count=len(p.get("sub_pipelines", [])),
        ))
    return options

"""Pipeline management API routes."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from copaw.pipeline import (
    SequentialPipeline,
    FanoutPipeline,
    ConditionalPipeline,
    LoopPipeline,
)
from copaw.pipeline.state_manager import StateManager

router = APIRouter(prefix="/pipelines", tags=["pipelines"])

# In-memory storage for demo (replace with database in production)
_pipelines_db = {}
_executions_db = {}


class PipelineConfig(BaseModel):
    """Pipeline configuration."""

    leader_agent: Optional[str] = None
    max_retries: int = 3
    timeout: Optional[int] = None


class CreatePipelineRequest(BaseModel):
    """Request to create a pipeline."""

    name: str = Field(..., description="Pipeline name")
    type: str = Field(..., description="Pipeline type")
    agents: List[str] = Field(..., description="List of agent IDs")
    description: Optional[str] = Field(None, description="Pipeline description")
    config: Optional[PipelineConfig] = Field(None, description="Pipeline configuration")


class UpdatePipelineRequest(BaseModel):
    """Request to update a pipeline."""

    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[PipelineConfig] = None


class PipelineResponse(BaseModel):
    """Pipeline response."""

    id: str
    name: str
    type: str
    agents: List[str]
    description: Optional[str] = None
    config: Optional[dict] = None
    status: str = "pending"
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
async def list_pipelines():
    """List all pipelines."""
    return list(_pipelines_db.values())


@router.post("/", response_model=PipelineResponse)
async def create_pipeline(request: CreatePipelineRequest):
    """Create a new pipeline."""
    pipeline_id = f"pipeline_{len(_pipelines_db) + 1}"
    now = datetime.utcnow().isoformat()

    pipeline_data = {
        "id": pipeline_id,
        "name": request.name,
        "type": request.type,
        "agents": request.agents,
        "description": request.description,
        "config": request.config.dict() if request.config else None,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }

    _pipelines_db[pipeline_id] = pipeline_data
    return pipeline_data


@router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: str):
    """Get pipeline by ID."""
    if pipeline_id not in _pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return _pipelines_db[pipeline_id]


@router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(pipeline_id: str, request: UpdatePipelineRequest):
    """Update a pipeline."""
    if pipeline_id not in _pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline = _pipelines_db[pipeline_id]

    if request.name is not None:
        pipeline["name"] = request.name
    if request.description is not None:
        pipeline["description"] = request.description
    if request.config is not None:
        pipeline["config"] = request.config.dict()

    pipeline["updated_at"] = datetime.utcnow().isoformat()

    return pipeline


@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    """Delete a pipeline."""
    if pipeline_id not in _pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    del _pipelines_db[pipeline_id]
    return {"message": "Pipeline deleted successfully"}


@router.post("/{pipeline_id}/execute", response_model=PipelineExecutionResponse)
async def execute_pipeline(pipeline_id: str, request: ExecutePipelineRequest):
    """Execute a pipeline."""
    if pipeline_id not in _pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline = _pipelines_db[pipeline_id]
    execution_id = f"exec_{len(_executions_db) + 1}"
    now = datetime.utcnow().isoformat()

    execution_data = {
        "id": execution_id,
        "pipeline_id": pipeline_id,
        "status": "running",
        "result": None,
        "error": None,
        "started_at": now,
        "completed_at": None,
    }

    _executions_db[execution_id] = execution_data

    try:
        # TODO: Implement actual pipeline execution
        # For now, just simulate success
        execution_data["status"] = "completed"
        execution_data["result"] = {
            "message": "Pipeline executed successfully",
            "agents": pipeline["agents"],
        }
        execution_data["completed_at"] = datetime.utcnow().isoformat()
    except Exception as e:
        execution_data["status"] = "failed"
        execution_data["error"] = str(e)
        execution_data["completed_at"] = datetime.utcnow().isoformat()

    return execution_data


@router.get("/{pipeline_id}/history", response_model=List[PipelineExecutionResponse])
async def get_pipeline_history(pipeline_id: str):
    """Get pipeline execution history."""
    if pipeline_id not in _pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    history = [
        exec_data
        for exec_data in _executions_db.values()
        if exec_data["pipeline_id"] == pipeline_id
    ]

    return history

"""Leader Agent management API routes."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from copaw.app.leader_manager import get_leader_manager, LeaderAgentInfo

router = APIRouter(prefix="/leader", tags=["leader"])


class SetLeaderRequest(BaseModel):
    """Request to set a leader agent."""

    agent_id: str


class LeaderResponse(BaseModel):
    """Leader agent response."""

    agent_id: str
    set_at: str
    pipelines: list[str]


@router.get("/", response_model=Optional[LeaderResponse])
async def get_leader():
    """Get the current leader agent."""
    manager = get_leader_manager()
    leader_info = manager.get_leader()

    if leader_info is None:
        return None

    return LeaderResponse(
        agent_id=leader_info.agent_id,
        set_at=leader_info.set_at,
        pipelines=leader_info.pipelines,
    )


@router.post("/", response_model=LeaderResponse)
async def set_leader(request: SetLeaderRequest):
    """Set an agent as leader."""
    manager = get_leader_manager()
    leader_info = manager.set_leader(request.agent_id)

    return LeaderResponse(
        agent_id=leader_info.agent_id,
        set_at=leader_info.set_at,
        pipelines=leader_info.pipelines,
    )


@router.delete("/")
async def remove_leader():
    """Remove the current leader agent."""
    manager = get_leader_manager()
    removed = manager.remove_leader()

    if not removed:
        raise HTTPException(status_code=404, detail="No leader agent is currently set")

    return {"message": "Leader agent removed successfully"}


@router.get("/pipelines", response_model=list[str])
async def get_leader_pipelines():
    """Get all pipelines associated with the current leader."""
    manager = get_leader_manager()
    return manager.get_leader_pipelines()

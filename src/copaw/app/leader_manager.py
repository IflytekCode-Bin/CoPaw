"""Leader Agent and Pipeline relationship management."""

from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel


class LeaderAgentInfo(BaseModel):
    """Leader agent information."""

    agent_id: str
    set_at: str
    pipelines: List[str] = []


class LeaderAgentManager:
    """Manage leader agent and its pipeline relationships."""

    def __init__(self):
        """Initialize the manager with in-memory storage."""
        self._leader_agent: Optional[str] = None
        self._leader_info: Optional[LeaderAgentInfo] = None
        self._agent_pipelines: Dict[str, List[str]] = {}  # agent_id -> pipeline_ids

    def set_leader(self, agent_id: str) -> LeaderAgentInfo:
        """Set an agent as leader.

        Args:
            agent_id: The agent ID to set as leader

        Returns:
            LeaderAgentInfo: The leader agent information
        """
        # Get existing pipelines if this agent was already a leader
        existing_pipelines = []
        if self._leader_agent == agent_id and self._leader_info:
            existing_pipelines = self._leader_info.pipelines

        self._leader_agent = agent_id
        self._leader_info = LeaderAgentInfo(
            agent_id=agent_id,
            set_at=datetime.utcnow().isoformat(),
            pipelines=existing_pipelines,
        )
        return self._leader_info

    def remove_leader(self) -> bool:
        """Remove the current leader agent.

        Returns:
            bool: True if a leader was removed, False if no leader was set
        """
        if self._leader_agent is None:
            return False

        self._leader_agent = None
        self._leader_info = None
        return True

    def get_leader(self) -> Optional[LeaderAgentInfo]:
        """Get the current leader agent information.

        Returns:
            Optional[LeaderAgentInfo]: The leader agent info, or None if no leader is set
        """
        return self._leader_info

    def add_pipeline_to_leader(self, pipeline_id: str) -> bool:
        """Add a pipeline to the current leader agent.

        Args:
            pipeline_id: The pipeline ID to add

        Returns:
            bool: True if added successfully, False if no leader is set
        """
        if self._leader_info is None:
            return False

        if pipeline_id not in self._leader_info.pipelines:
            self._leader_info.pipelines.append(pipeline_id)

        return True

    def remove_pipeline_from_leader(self, pipeline_id: str) -> bool:
        """Remove a pipeline from the current leader agent.

        Args:
            pipeline_id: The pipeline ID to remove

        Returns:
            bool: True if removed successfully, False if not found
        """
        if self._leader_info is None:
            return False

        if pipeline_id in self._leader_info.pipelines:
            self._leader_info.pipelines.remove(pipeline_id)
            return True

        return False

    def get_leader_pipelines(self) -> List[str]:
        """Get all pipelines associated with the current leader.

        Returns:
            List[str]: List of pipeline IDs
        """
        if self._leader_info is None:
            return []

        return self._leader_info.pipelines.copy()


# Global singleton instance
_leader_manager = LeaderAgentManager()


def get_leader_manager() -> LeaderAgentManager:
    """Get the global leader agent manager instance.

    Returns:
        LeaderAgentManager: The singleton manager instance
    """
    return _leader_manager

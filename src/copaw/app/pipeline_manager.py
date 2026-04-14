"""Persistent Pipeline storage and management.

Stores pipeline definitions as JSON files under WORKING_DIR/pipelines/
and provides CRUD operations with automatic persistence.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict
from copy import deepcopy

# Absolute import to avoid relative import issues
from copaw.constant import WORKING_DIR

logger = logging.getLogger(__name__)

# Storage directory
PIPELINES_DIR = WORKING_DIR / "pipelines"


def _ensure_dir() -> Path:
    """Ensure the pipelines directory exists."""
    PIPELINES_DIR.mkdir(parents=True, exist_ok=True)
    return PIPELINES_DIR


def _pipeline_file(pipeline_id: str) -> Path:
    """Return the file path for a pipeline."""
    return _ensure_dir() / f"{pipeline_id}.json"


def _generate_id(existing_ids: List[str]) -> str:
    """Generate a unique pipeline ID."""
    counter = 1
    while True:
        pid = f"pipeline_{counter}"
        if pid not in existing_ids:
            return pid
        counter += 1


def _load_all() -> Dict[str, dict]:
    """Load all pipeline definitions from disk."""
    pipelines = {}
    _ensure_dir()
    for f in PIPELINES_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                pipelines[data["id"]] = data
        except Exception as e:
            logger.warning("Failed to load pipeline file %s: %s", f, e)
    return pipelines


def _save(pipeline: dict) -> None:
    """Persist a pipeline definition to disk."""
    filepath = _pipeline_file(pipeline["id"])
    tmp_path = filepath.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(pipeline, fh, indent=2, ensure_ascii=False)
    tmp_path.replace(filepath)


def _delete_file(pipeline_id: str) -> None:
    """Delete a pipeline file."""
    filepath = _pipeline_file(pipeline_id)
    if filepath.exists():
        filepath.unlink()


class PipelineManager:
    """Manage persistent pipeline storage."""

    def __init__(self):
        self._cache: Optional[Dict[str, dict]] = None

    def _load(self) -> Dict[str, dict]:
        """Lazy-load pipelines from disk."""
        if self._cache is None:
            self._cache = _load_all()
        return self._cache

    def _invalidate(self) -> None:
        """Invalidate the cache so next load reads from disk."""
        self._cache = None

    def list_all(
        self,
        owner_agent_id: Optional[str] = None,
        parent_pipeline_id: Optional[str] = None,
    ) -> List[dict]:
        """List all pipelines with optional filters."""
        pipelines = list(self._load().values())
        if owner_agent_id:
            pipelines = [p for p in pipelines if p.get("owner_agent_id") == owner_agent_id]
        if parent_pipeline_id:
            pipelines = [p for p in pipelines if p.get("parent_pipeline_id") == parent_pipeline_id]
        return pipelines

    def get(self, pipeline_id: str) -> Optional[dict]:
        """Get a pipeline by ID."""
        return self._load().get(pipeline_id)

    def create(
        self,
        name: str,
        pipeline_type: str,
        agents: List[str],
        description: Optional[str] = None,
        config: Optional[dict] = None,
        owner_agent_id: Optional[str] = None,
        sub_pipelines: Optional[List[str]] = None,
        parent_pipeline_id: Optional[str] = None,
    ) -> dict:
        """Create a new pipeline and persist it."""
        all_ids = list(self._load().keys())
        pipeline_id = _generate_id(all_ids)
        now = datetime.now(timezone.utc).isoformat()

        pipeline = {
            "id": pipeline_id,
            "name": name,
            "type": pipeline_type,
            "agents": agents,
            "description": description or "",
            "config": config or {},
            "status": "pending",
            "owner_agent_id": owner_agent_id,
            "sub_pipelines": sub_pipelines or [],
            "parent_pipeline_id": parent_pipeline_id,
            "created_at": now,
            "updated_at": now,
        }

        _save(pipeline)
        self._invalidate()
        return deepcopy(pipeline)

    def update(
        self,
        pipeline_id: str,
        name: Optional[str] = None,
        pipeline_type: Optional[str] = None,
        agents: Optional[List[str]] = None,
        description: Optional[str] = None,
        config: Optional[dict] = None,
        sub_pipelines: Optional[List[str]] = None,
    ) -> Optional[dict]:
        """Update a pipeline."""
        pipelines = self._load()
        if pipeline_id not in pipelines:
            return None

        pipeline = pipelines[pipeline_id]

        if name is not None:
            pipeline["name"] = name
        if pipeline_type is not None:
            pipeline["type"] = pipeline_type
        if agents is not None:
            pipeline["agents"] = agents
        if description is not None:
            pipeline["description"] = description
        if config is not None:
            pipeline["config"] = config
        if sub_pipelines is not None:
            pipeline["sub_pipelines"] = sub_pipelines

        pipeline["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save(pipeline)
        self._invalidate()
        return deepcopy(pipeline)

    def delete(self, pipeline_id: str) -> bool:
        """Delete a pipeline."""
        pipelines = self._load()
        if pipeline_id not in pipelines:
            return False

        # Also delete child pipelines (orphan)
        child_pipelines = [
            pid for pid, p in pipelines.items()
            if p.get("parent_pipeline_id") == pipeline_id
        ]
        for child_id in child_pipelines:
            pipelines[child_id]["parent_pipeline_id"] = None
            _save(pipelines[child_id])

        _delete_file(pipeline_id)
        self._invalidate()
        return True

    def get_by_owner(self, owner_agent_id: str) -> List[dict]:
        """Get all pipelines owned by an agent."""
        return self.list_all(owner_agent_id=owner_agent_id)

    def get_children(self, parent_pipeline_id: str) -> List[dict]:
        """Get all sub-pipelines of a parent pipeline."""
        return self.list_all(parent_pipeline_id=parent_pipeline_id)

    def rebuild_cache(self) -> None:
        """Force reload from disk."""
        self._invalidate()


# Singleton instance
_pipeline_manager: Optional[PipelineManager] = None


def get_pipeline_manager() -> PipelineManager:
    """Get the global PipelineManager singleton."""
    global _pipeline_manager
    if _pipeline_manager is None:
        _pipeline_manager = PipelineManager()
    return _pipeline_manager

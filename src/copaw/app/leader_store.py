"""Persistent per-agent leader flag storage.

Each agent can be independently marked as a Leader.
Leadership state is persisted to WORKING_DIR/leaders.json so it survives restarts.
"""

import json
import logging
from pathlib import Path
from typing import Set, Optional

# Absolute import to avoid relative import issues
from copaw.constant import WORKING_DIR

logger = logging.getLogger(__name__)

_LEADERS_FILE = WORKING_DIR / "leaders.json"


def _ensure_dir() -> Path:
    """Ensure the leaders file directory exists."""
    _LEADERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    return _LEADERS_FILE.parent


def _load() -> Set[str]:
    """Load the set of leader agent IDs."""
    _ensure_dir()
    if not _LEADERS_FILE.exists():
        return set()
    try:
        with open(_LEADERS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return set(data.get("leaders", []))
            elif isinstance(data, list):
                return set(data)
            return set()
    except Exception as e:
        logger.warning("Failed to load leaders file: %s", e)
        return set()


def _save(leader_ids: Set[str]) -> None:
    """Persist the set of leader agent IDs."""
    _ensure_dir()
    tmp_path = _LEADERS_FILE.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump({"version": 1, "leaders": sorted(leader_ids)}, fh, indent=2, ensure_ascii=False)
    tmp_path.replace(_LEADERS_FILE)


class LeaderStore:
    """Manage per-agent leader flags with file persistence."""

    def __init__(self):
        self._cache: Optional[Set[str]] = None

    def _get_cache(self) -> Set[str]:
        if self._cache is None:
            self._cache = _load()
        return self._cache

    def is_leader(self, agent_id: str) -> bool:
        """Check if an agent is a leader."""
        return agent_id in self._get_cache()

    def set_leader(self, agent_id: str) -> bool:
        """Mark an agent as leader."""
        cache = self._get_cache()
        if agent_id in cache:
            return False
        cache.add(agent_id)
        _save(cache)
        return True

    def remove_leader(self, agent_id: str) -> bool:
        """Remove leader flag from an agent."""
        cache = self._get_cache()
        if agent_id not in cache:
            return False
        cache.discard(agent_id)
        _save(cache)
        return True

    def get_leaders(self) -> Set[str]:
        """Get all leader agent IDs."""
        return set(self._get_cache())

    def set_leaders(self, leader_ids: Set[str]) -> None:
        """Replace the entire set of leaders."""
        self._cache = leader_ids
        _save(leader_ids)

    def reload(self) -> Set[str]:
        """Force reload from disk."""
        self._cache = None
        return self._get_cache()


# Singleton instance
_leader_store: Optional[LeaderStore] = None


def get_leader_store() -> LeaderStore:
    """Get the global LeaderStore singleton."""
    global _leader_store
    if _leader_store is None:
        _leader_store = LeaderStore()
    return _leader_store

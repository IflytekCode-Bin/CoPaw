# -*- coding: utf-8 -*-
"""Backup module for CoPaw enterprise storage.

Architecture:
- BackupCoordinator: Process-level, manages multiple agents
- BackupAgent: Agent-level, handles unique resources
"""

from .backup_coordinator import BackupCoordinator
from .backup_agent import BackupAgent

# Legacy single-agent backup manager (deprecated, use BackupAgent)
from .backup_manager import BackupManager

__all__ = [
    "BackupCoordinator",
    "BackupAgent",
    "BackupManager",  # Deprecated
]
# -*- coding: utf-8 -*-
"""CoPaw Storage Module.

Provides hybrid storage solutions:
- SQLiteMemoryManager: Local fast queries with FTS5
- MinIOStorageManager: Remote backup and large file storage
- HybridStorageManager: Combined approach
"""

from .minio_manager import MinIOStorageManager
from .sqlite_manager import SQLiteMemoryManager
from .hybrid_manager import HybridStorageManager
from .constants import (
    STORAGE_PRIORITY,
    SYNC_STRATEGIES,
    CLEANUP_RULES,
)

__all__ = [
    "MinIOStorageManager",
    "SQLiteMemoryManager",
    "HybridStorageManager",
    "STORAGE_PRIORITY",
    "SYNC_STRATEGIES",
    "CLEANUP_RULES",
]
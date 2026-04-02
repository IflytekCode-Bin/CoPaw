# -*- coding: utf-8 -*-
"""Hybrid Storage Manager for CoPaw.

Combines SQLite and MinIO for optimal storage:
- SQLite: Fast local queries, FTS5, relationships
- MinIO: Remote backup, large files, cross-agent sharing
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentscope.message import Msg

from .minio_manager import MinIOStorageManager
from .sqlite_manager import SQLiteMemoryManager
from .constants import STORAGE_PRIORITY

logger = logging.getLogger(__name__)


class HybridStorageManager:
    """Hybrid storage manager combining SQLite and MinIO.

    Features:
    - SQLite for fast local operations
    - MinIO for remote backup and sharing
    - Automatic sync based on priority
    - Graceful degradation when MinIO unavailable
    """

    def __init__(
        self,
        working_dir: str,
        agent_id: str = "default",
        minio_enabled: bool = True,
        minio_endpoint: str = "localhost:9000",
        minio_access_key: str = "minioadmin",
        minio_secret_key: str = "minioadmin123",
    ):
        """Initialize hybrid storage manager.

        Args:
            working_dir: Working directory
            agent_id: Agent identifier
            minio_enabled: Enable MinIO backup
            minio_endpoint: MinIO endpoint
            minio_access_key: MinIO access key
            minio_secret_key: MinIO secret key
        """
        self.working_dir = Path(working_dir)
        self.agent_id = agent_id
        self.minio_enabled = minio_enabled

        # SQLite is always available
        self.sqlite = SQLiteMemoryManager(
            working_dir=working_dir,
            agent_id=agent_id,
        )

        # MinIO is optional
        self.minio: Optional[MinIOStorageManager] = None
        if minio_enabled:
            try:
                self.minio = MinIOStorageManager(
                    agent_id=agent_id,
                    endpoint=minio_endpoint,
                    access_key=minio_access_key,
                    secret_key=minio_secret_key,
                    working_dir=self.working_dir,
                )
                logger.info("MinIO backup enabled")
            except Exception as e:
                logger.warning(f"MinIO not available: {e}")
                self.minio = None

        self._sync_queue: asyncio.Queue = asyncio.Queue()
        self._sync_task: Optional[asyncio.Task] = None

    # ============================================================
    # Message Operations
    # ============================================================

    async def ingest_message(
        self,
        message: Msg,
        conversation_id: str,
    ) -> int:
        """Ingest a message into storage.

        Args:
            message: Message to ingest
            conversation_id: Conversation ID

        Returns:
            Token count
        """
        # 1. SQLite (immediate)
        token_count = self.sqlite.insert_message(
            message_id=message.id or str(datetime.now().timestamp()),
            conversation_id=conversation_id,
            role=message.role,
            content=str(message.content),
        )

        # 2. MinIO (async, non-blocking)
        if self.minio:
            asyncio.create_task(
                self._sync_message_to_minio(message, conversation_id)
            )

        return token_count

    async def _sync_message_to_minio(
        self,
        message: Msg,
        conversation_id: str,
    ) -> None:
        """Sync message to MinIO."""
        try:
            await self.minio.upload_json(
                f"conversations/{conversation_id}/messages/{message.id}.json",
                {
                    "message_id": message.id,
                    "conversation_id": conversation_id,
                    "role": message.role,
                    "content": str(message.content),
                    "timestamp": datetime.now().isoformat(),
                },
            )
        except Exception as e:
            logger.error(f"Failed to sync message to MinIO: {e}")

    # ============================================================
    # Search Operations
    # ============================================================

    async def search(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search messages (uses SQLite FTS5).

        Args:
            query: Search query
            conversation_id: Optional conversation filter
            limit: Max results

        Returns:
            List of matching messages
        """
        return self.sqlite.search_messages(query, conversation_id, limit)

    async def search_by_time(
        self,
        start_time: datetime,
        end_time: datetime,
        conversation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search by time range."""
        return self.sqlite.search_by_time_range(
            start_time, end_time, conversation_id
        )

    # ============================================================
    # Conversation Operations
    # ============================================================

    async def create_conversation(
        self,
        conversation_id: str,
        session_id: str,
        channel: str = "console",
        user_id: str = "default",
        title: Optional[str] = None,
    ) -> None:
        """Create a new conversation."""
        # SQLite
        self.sqlite.create_conversation(
            conversation_id, session_id, channel, user_id, title
        )

        # MinIO
        if self.minio:
            await self.minio.upload_json(
                f"conversations/{conversation_id}/meta.json",
                {
                    "conversation_id": conversation_id,
                    "session_id": session_id,
                    "channel": channel,
                    "user_id": user_id,
                    "title": title,
                    "created_at": datetime.now().isoformat(),
                },
            )

    async def get_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get messages for a conversation."""
        return self.sqlite.get_messages(conversation_id, limit)

    async def get_recent_messages(
        self,
        conversation_id: str,
        count: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent messages."""
        return self.sqlite.get_recent_messages(conversation_id, count)

    # ============================================================
    # Summary Operations (DAG Compaction)
    # ============================================================

    async def create_summary(
        self,
        summary_id: str,
        conversation_id: str,
        kind: str,
        content: str,
        depth: int = 0,
        source_messages: Optional[List[str]] = None,
        model: Optional[str] = None,
    ) -> int:
        """Create a summary node."""
        # SQLite
        token_count = self.sqlite.insert_summary(
            summary_id, conversation_id, kind, content,
            depth, source_messages, model
        )

        # MinIO
        if self.minio:
            await self.minio.upload_json(
                f"conversations/{conversation_id}/summaries/{summary_id}.json",
                {
                    "summary_id": summary_id,
                    "conversation_id": conversation_id,
                    "kind": kind,
                    "depth": depth,
                    "content": content,
                    "token_count": token_count,
                    "source_messages": source_messages,
                    "model": model,
                    "created_at": datetime.now().isoformat(),
                },
            )

        return token_count

    async def get_summaries(
        self,
        conversation_id: str,
        depth: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get summaries for a conversation."""
        return self.sqlite.get_summaries(conversation_id, depth)

    # ============================================================
    # Statistics
    # ============================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        stats = {
            "sqlite": {
                "db_size_bytes": self.sqlite.get_db_size(),
                "db_size_mb": round(self.sqlite.get_db_size() / 1024 / 1024, 2),
                "token_stats": self.sqlite.get_token_stats(),
            },
            "minio": None,
        }

        if self.minio:
            try:
                stats["minio"] = await self.minio.get_storage_stats()
            except Exception as e:
                stats["minio"] = {"error": str(e)}

        return stats

    # ============================================================
    # Backup Operations
    # ============================================================

    async def backup(self, full: bool = False) -> Dict[str, str]:
        """Trigger backup.

        Args:
            full: Full backup vs incremental

        Returns:
            Dict of backup locations
        """
        if not self.minio:
            return {"error": "MinIO not available"}

        results = {}

        if full:
            results["workspace"] = await self.minio.backup_full()
        else:
            await self.minio.sync_config()
            await self.minio.sync_memory()
            await self.minio.sync_sessions()
            results["status"] = "incremental sync completed"

        # Backup SQLite
        date_str = datetime.now().strftime('%Y-%m-%d')
        db_path = self.sqlite.db_path
        results["sqlite"] = await self.minio.upload_file(
            db_path,
            f"exports/{date_str}/memory.db",
            compress=True,
        )

        return results

    async def restore(
        self,
        backup_date: str,
        conversation_id: Optional[str] = None,
    ) -> bool:
        """Restore from backup.

        Args:
            backup_date: Date string (YYYY-MM-DD)
            conversation_id: Optional specific conversation

        Returns:
            Success status
        """
        if not self.minio:
            logger.error("MinIO not available for restore")
            return False

        try:
            # Restore SQLite
            await self.minio.download_file(
                f"exports/{backup_date}/memory.db.gz",
                self.sqlite.db_path,
                decompress=True,
            )

            logger.info(f"Restored from {backup_date}")
            return True
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    # ============================================================
    # Lifecycle
    # ============================================================

    async def start(self) -> None:
        """Start background sync."""
        if self.minio:
            self._sync_task = asyncio.create_task(
                self.minio.start_watching()
            )
            logger.info("Started background sync")

    async def stop(self) -> None:
        """Stop background sync."""
        if self.minio:
            self.minio.stop_watching()

        if self._sync_task:
            self._sync_task.cancel()

        logger.info("Stopped background sync")

    async def cleanup(self) -> Dict[str, int]:
        """Run cleanup tasks."""
        results = {}

        # Local cleanup
        if self.minio:
            results["cleaned"] = await self.minio.cleanup_local()

        # SQLite vacuum
        self.sqlite.vacuum()
        results["vacuum"] = "completed"

        return results
# -*- coding: utf-8 -*-
"""Backup Manager for CoPaw Enterprise Storage.

Provides:
- Realtime sync of critical files to MinIO
- Scheduled backups of all workspace data
- Cross-agent resource sharing
- Disaster recovery capability
"""

import asyncio
import gzip
import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from minio import Minio
from minio.error import S3Error
from watchfiles import awatch

logger = logging.getLogger(__name__)


# Storage priorities
P0_REALTIME = ["config.json", "MEMORY.md", "memory/", "sessions/", "agent.json"]
P1_CHANGE = ["dialog/", "file_store/", "chats.json"]
P2_SCHEDULE = ["skills/", "active_skills/", "customized_skills/"]
P3_MANUAL = ["exports/", "media/"]
P4_LOCAL_ONLY = ["logs/", "tool_result/", "browser/", "embedding_cache/", "*.tmp"]


class BackupManager:
    """Enterprise backup manager for CoPaw workspace.

    Features:
    - Realtime sync of critical files (P0)
    - Change-triggered sync (P1)
    - Scheduled backup (P2)
    - Graceful degradation when MinIO unavailable
    """

    def __init__(
        self,
        workspace_dir: str,
        agent_id: str,
        minio_endpoint: Optional[str] = None,
        minio_access_key: Optional[str] = None,
        minio_secret_key: Optional[str] = None,
        minio_secure: bool = False,
        enabled: bool = True,
    ):
        """Initialize backup manager.

        Args:
            workspace_dir: Workspace directory path
            agent_id: Agent identifier
            minio_endpoint: MinIO endpoint (or from env)
            minio_access_key: MinIO access key (or from env)
            minio_secret_key: MinIO secret key (or from env)
            minio_secure: Use HTTPS
            enabled: Enable backup (default True)
        """
        self.workspace_dir = Path(workspace_dir)
        self.agent_id = agent_id
        self.enabled = enabled and self._check_minio_config()

        # MinIO configuration (env vars preferred)
        self.endpoint = minio_endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = minio_access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = minio_secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin123")
        self.secure = minio_secure or os.getenv("MINIO_SECURE", "false").lower() == "true"

        self.bucket = f"copaw-{agent_id}"
        self.client: Optional[Minio] = None
        self._running = False
        self._sync_task: Optional[asyncio.Task] = None

        if self.enabled:
            self._init_minio()
        else:
            logger.warning(
                f"BackupManager disabled for {agent_id}. "
                "MinIO not configured or unavailable."
            )

    def _check_minio_config(self) -> bool:
        """Check if MinIO is configured."""
        return bool(
            os.getenv("MINIO_ENDPOINT")
            or os.getenv("BACKUP_ENABLED", "false").lower() == "true"
        )

    def _init_minio(self) -> None:
        """Initialize MinIO client."""
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )

            # Ensure bucket exists
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")

            logger.info(
                f"BackupManager initialized: agent={self.agent_id}, "
                f"bucket={self.bucket}, endpoint={self.endpoint}"
            )

        except S3Error as e:
            logger.error(f"MinIO initialization failed: {e}")
            self.enabled = False
            self.client = None

    async def sync_file(
        self,
        local_path: Path,
        remote_path: str,
        compress: bool = False,
    ) -> bool:
        """Sync a single file to MinIO."""
        if not self.enabled or not self.client:
            return False

        if not local_path.exists():
            return False

        try:
            checksum = await self._calculate_checksum(local_path)

            # Check if file changed
            try:
                stat = self.client.stat_object(self.bucket, remote_path)
                remote_checksum = stat.metadata.get("x-amz-meta-sha256", "")
                if remote_checksum == checksum:
                    return True  # Unchanged
            except S3Error:
                pass

            if compress:
                await self._upload_compressed(local_path, remote_path, checksum)
            else:
                self.client.fput_object(
                    self.bucket,
                    remote_path,
                    str(local_path),
                    metadata={"sha256": checksum, "agent_id": self.agent_id},
                )

            logger.debug(f"Synced: {local_path.name}")
            return True

        except Exception as e:
            logger.error(f"Sync failed: {local_path} -> {e}")
            return False

    async def sync_directory(
        self,
        local_dir: Path,
        remote_prefix: str,
        exclude_patterns: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """Sync a directory to MinIO."""
        if not self.enabled or not self.client or not local_dir.exists():
            return {}

        results = {}
        exclude_patterns = exclude_patterns or []

        # Normalize remote prefix (remove trailing slash)
        remote_prefix = remote_prefix.rstrip("/")

        for file_path in local_dir.rglob("*"):
            if not file_path.is_file():
                continue

            relative = file_path.relative_to(local_dir)
            if self._should_exclude(str(relative), exclude_patterns):
                continue

            # Build clean path without double slashes
            remote_path = f"{remote_prefix}/{relative}".replace("//", "/")
            results[str(file_path)] = await self.sync_file(file_path, remote_path)

        return results

    def _should_exclude(self, path: str, patterns: List[str]) -> bool:
        """Check if path matches exclude patterns."""
        import fnmatch
        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern):
                return True
        return False

    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _upload_compressed(
        self, local_path: Path, remote_path: str, checksum: str
    ) -> None:
        """Upload compressed file."""
        with open(local_path, "rb") as f:
            compressed = gzip.compress(f.read())

        temp_path = local_path.with_suffix(".gz.tmp")
        with open(temp_path, "wb") as f:
            f.write(compressed)

        self.client.fput_object(
            self.bucket,
            remote_path + ".gz",
            str(temp_path),
            metadata={"sha256": checksum, "compressed": "true"},
        )
        temp_path.unlink()

    async def sync_p0_realtime(self) -> Dict[str, bool]:
        """Sync critical files (config, MEMORY.md, sessions)."""
        results = {}
        for pattern in P0_REALTIME:
            # Normalize pattern (remove trailing slash)
            clean_pattern = pattern.rstrip("/")
            path = self.workspace_dir / clean_pattern
            if path.is_file():
                results[str(path)] = await self.sync_file(path, f"realtime/{clean_pattern}")
            elif path.is_dir():
                results.update(await self.sync_directory(path, f"realtime/{clean_pattern}"))
        return results

    async def sync_p1_change(self) -> Dict[str, bool]:
        """Sync dialog and file_store."""
        results = {}
        for pattern in P1_CHANGE:
            clean_pattern = pattern.rstrip("/")
            path = self.workspace_dir / clean_pattern
            if path.is_file():
                results[str(path)] = await self.sync_file(path, f"change/{clean_pattern}", compress=True)
            elif path.is_dir():
                results.update(await self.sync_directory(
                    path, f"change/{clean_pattern}",
                    exclude_patterns=["*.tmp", "*.lock"]
                ))
        return results

    async def full_backup(self) -> Dict[str, Any]:
        """Full backup of workspace."""
        if not self.enabled:
            return {"error": "Backup not enabled"}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = {
            "timestamp": timestamp,
            "p0": await self.sync_p0_realtime(),
            "p1": await self.sync_p1_change(),
        }

        total = sum(len(r) for r in [results["p0"], results["p1"]])
        success = sum(sum(1 for v in r.values() if v) for r in [results["p0"], results["p1"]])
        results["stats"] = {"total": total, "success": success}

        logger.info(f"Backup completed: {success}/{total} files")
        return results

    async def start(self) -> None:
        """Start backup manager."""
        if self.enabled:
            await self.sync_p0_realtime()
            logger.info(f"BackupManager started for {self.agent_id}")

    async def stop(self) -> None:
        """Stop backup manager."""
        self._running = False
        logger.info(f"BackupManager stopped for {self.agent_id}")

    async def get_stats(self) -> Dict[str, Any]:
        """Get backup statistics."""
        if not self.enabled or not self.client:
            return {"enabled": False}

        try:
            objects = list(self.client.list_objects(self.bucket))
            total_size = sum(obj.size or 0 for obj in objects)
            return {
                "enabled": True,
                "bucket": self.bucket,
                "total_objects": len(objects),
                "total_size_mb": round(total_size / 1024 / 1024, 2),
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}
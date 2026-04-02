# -*- coding: utf-8 -*-
"""Backup Agent for Single Agent Workspace.

Handles backup of agent-unique resources:
- sessions/, dialog/, memory/
- agent.json, MEMORY.md, chats.json

Works with BackupCoordinator for:
- Shared resources deduplication
- Backup scheduling coordination
"""

import asyncio
import gzip
import hashlib
import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from minio import Minio
from minio.error import S3Error

if TYPE_CHECKING:
    from .backup_coordinator import BackupCoordinator

logger = logging.getLogger(__name__)


def get_content_type(file_path: Path) -> str:
    """Get content type based on file extension."""
    content_type, _ = mimetypes.guess_type(str(file_path))
    if content_type:
        return content_type
    # Fallback for common types
    suffix = file_path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    elif suffix == ".md":
        return "text/markdown"
    elif suffix == ".txt":
        return "text/plain"
    elif suffix == ".gz":
        return "application/gzip"
    else:
        return "application/octet-stream"


# Agent-unique resources (each agent has its own)
AGENT_UNIQUE_P0 = [
    "MEMORY.md",
    "memory/",
    "sessions/",
    "agent.json",
]

AGENT_UNIQUE_P1 = [
    "dialog/",
    "chats.json",
]


class BackupAgent:
    """Backup manager for a single agent workspace.

    Features:
    - Realtime sync of critical files (P0)
    - Change-triggered sync (P1)
    - Integration with BackupCoordinator for shared resources
    """

    def __init__(
        self,
        agent_id: str,
        workspace_dir: Path,
        client: Optional[Minio],
        bucket: str,
        coordinator: Optional["BackupCoordinator"] = None,
        compress_dialog: bool = True,
        compress_chats: bool = True,
    ):
        """Initialize backup agent.

        Args:
            agent_id: Agent identifier
            workspace_dir: Workspace directory path
            client: MinIO client (shared from coordinator)
            bucket: Agent bucket name (copaw-{agent_id})
            coordinator: BackupCoordinator reference
            compress_dialog: Compress dialog files (saves space, can't preview)
            compress_chats: Compress chats.json
        """
        self.agent_id = agent_id
        self.workspace_dir = Path(workspace_dir)
        self.client = client
        self.bucket = bucket
        self.coordinator = coordinator
        self.compress_dialog = compress_dialog
        self.compress_chats = compress_chats

        self._running = False
        self._last_sync: Dict[str, str] = {}  # path -> checksum

        logger.info(
            f"BackupAgent initialized: agent={agent_id}, "
            f"bucket={bucket}, workspace={workspace_dir}"
        )

    # ============================================================
    # File Sync Methods
    # ============================================================

    async def sync_file(
        self,
        local_path: Path,
        remote_path: str,
        compress: bool = False,
    ) -> bool:
        """Sync a single file to MinIO.

        Args:
            local_path: Local file path
            remote_path: Remote object path
            compress: Compress file before upload

        Returns:
            Success status
        """
        if not self.client or not local_path.exists():
            return False

        try:
            # Calculate checksum
            checksum = await self._calculate_checksum(local_path)

            # Check if unchanged (local cache)
            if str(local_path) in self._last_sync:
                if self._last_sync[str(local_path)] == checksum:
                    return True  # Unchanged

            # Check remote
            try:
                stat = self.client.stat_object(self.bucket, remote_path)
                if stat.metadata.get("x-amz-meta-sha256") == checksum:
                    self._last_sync[str(local_path)] = checksum
                    return True
            except S3Error:
                pass  # Need to upload

            # Upload
            if compress:
                await self._upload_compressed(local_path, remote_path, checksum)
            else:
                content_type = get_content_type(local_path)
                self.client.fput_object(
                    self.bucket,
                    remote_path,
                    str(local_path),
                    content_type=content_type,
                    metadata={
                        "sha256": checksum,
                        "agent_id": self.agent_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

            self._last_sync[str(local_path)] = checksum
            logger.debug(f"Synced: {local_path.name} -> {remote_path}")
            return True

        except Exception as e:
            logger.error(f"Sync failed: {local_path} -> {e}")
            return False

    async def sync_directory(
        self,
        local_dir: Path,
        remote_prefix: str,
        exclude_patterns: Optional[List[str]] = None,
        compress: bool = False,
    ) -> Dict[str, bool]:
        """Sync a directory to MinIO.

        Args:
            local_dir: Local directory path
            remote_prefix: Remote prefix path
            exclude_patterns: Patterns to exclude
            compress: Compress files

        Returns:
            Dict of file paths and success status
        """
        if not self.client or not local_dir.exists():
            return {}

        results = {}
        exclude_patterns = exclude_patterns or []
        remote_prefix = remote_prefix.rstrip("/")

        for file_path in local_dir.rglob("*"):
            if not file_path.is_file():
                continue

            # Check exclude
            relative = file_path.relative_to(local_dir)
            if self._should_exclude(str(relative), exclude_patterns):
                continue

            remote_path = f"{remote_prefix}/{relative}".replace("//", "/")
            results[str(file_path)] = await self.sync_file(file_path, remote_path, compress)

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
            content_type="application/gzip",
            metadata={"sha256": checksum, "compressed": "true"},
        )
        temp_path.unlink()

    # ============================================================
    # Priority Sync Methods
    # ============================================================

    async def sync_p0_realtime(self) -> Dict[str, bool]:
        """Sync P0 (realtime) files.

        Critical files: MEMORY.md, memory/, sessions/, agent.json
        """
        results = {}

        for pattern in AGENT_UNIQUE_P0:
            clean_pattern = pattern.rstrip("/")
            path = self.workspace_dir / clean_pattern

            if path.is_file():
                results[str(path)] = await self.sync_file(
                    path, f"realtime/{clean_pattern}"
                )
            elif path.is_dir():
                dir_results = await self.sync_directory(
                    path, f"realtime/{clean_pattern}"
                )
                results.update(dir_results)

        logger.info(f"P0 sync: {len(results)} files for {self.agent_id}")
        return results

    async def sync_p1_change(self) -> Dict[str, bool]:
        """Sync P1 (change-triggered) files.

        dialog/, chats.json
        """
        results = {}

        for pattern in AGENT_UNIQUE_P1:
            clean_pattern = pattern.rstrip("/")
            path = self.workspace_dir / clean_pattern

            # Determine compression based on file type and config
            if clean_pattern == "dialog":
                compress = self.compress_dialog
            elif clean_pattern == "chats.json":
                compress = self.compress_chats
            else:
                compress = True  # Default to compress for other P1 files

            if path.is_file():
                results[str(path)] = await self.sync_file(
                    path, f"change/{clean_pattern}", compress=compress
                )
            elif path.is_dir():
                dir_results = await self.sync_directory(
                    path, f"change/{clean_pattern}",
                    exclude_patterns=["*.tmp", "*.lock", "compact_invalid_*"],
                    compress=compress,
                )
                results.update(dir_results)

        logger.info(f"P1 sync: {len(results)} files for {self.agent_id}")
        return results

    # ============================================================
    # Backup Methods
    # ============================================================

    async def full_backup(self) -> Dict[str, Any]:
        """Full backup of agent workspace.

        Returns:
            Backup result with statistics
        """
        results = {
            "agent_id": self.agent_id,
            "bucket": self.bucket,
            "timestamp": datetime.now().isoformat(),
            "p0": await self.sync_p0_realtime(),
            "p1": await self.sync_p1_change(),
        }

        # Calculate statistics
        total = sum(len(r) for r in [results["p0"], results["p1"]])
        success = sum(
            sum(1 for v in r.values() if v)
            for r in [results["p0"], results["p1"]]
        )

        results["stats"] = {
            "total": total,
            "success": success,
            "failed": total - success,
        }

        logger.info(
            f"Full backup: {self.agent_id} -> {success}/{total} files"
        )
        return results

    async def incremental_backup(self) -> Dict[str, Any]:
        """Incremental backup (only changed files)."""
        results = {
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "p0": await self.sync_p0_realtime(),
            "p1": await self.sync_p1_change(),
        }

        return results

    # ============================================================
    # Restore Methods
    # ============================================================

    async def restore(
        self,
        backup_prefix: Optional[str] = None,
        target_dir: Optional[Path] = None,
        resources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Restore workspace from backup.

        Args:
            backup_prefix: Backup prefix (e.g., "realtime", "change")
                           If None, restore all
            target_dir: Target directory (default: workspace_dir)
            resources: Specific resources to restore (default: all)

        Returns:
            Restore result with statistics
        """
        if not self.client:
            return {"error": "MinIO not available", "agent_id": self.agent_id}

        target_dir = target_dir or self.workspace_dir
        resources = resources or AGENT_UNIQUE_P0 + AGENT_UNIQUE_P1

        results = {
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "restored": {},
            "errors": [],
        }

        try:
            # List objects in bucket
            objects = list(self.client.list_objects(self.bucket, recursive=True))

            for obj in objects:
                object_name = obj.object_name

                # Filter by backup_prefix if specified
                if backup_prefix and not object_name.startswith(backup_prefix):
                    continue

                # Check if object is for a resource we want
                should_restore = False
                for resource in resources:
                    clean_resource = resource.rstrip("/")
                    if clean_resource in object_name:
                        should_restore = True
                        break

                if not should_restore:
                    continue

                # Determine local path
                # realtime/MEMORY.md -> MEMORY.md
                # realtime/memory/2026-04-01.md -> memory/2026-04-01.md
                parts = object_name.split("/")
                if len(parts) >= 2:
                    # Remove prefix (realtime/, change/)
                    local_relative = "/".join(parts[1:])
                else:
                    local_relative = object_name

                local_path = target_dir / local_relative

                # Download
                try:
                    local_path.parent.mkdir(parents=True, exist_ok=True)

                    # Handle compressed files
                    if object_name.endswith(".gz"):
                        # Download to temp file
                        temp_path = local_path.with_suffix(".gz.tmp")
                        self.client.fget_object(
                            self.bucket, object_name, str(temp_path)
                        )

                        # Decompress
                        await self._decompress_file(temp_path, local_path)
                        temp_path.unlink()
                    else:
                        self.client.fget_object(
                            self.bucket, object_name, str(local_path)
                        )

                    results["restored"][object_name] = str(local_path)

                except Exception as e:
                    results["errors"].append(f"{object_name}: {str(e)}")

            # Statistics
            results["stats"] = {
                "restored": len(results["restored"]),
                "errors": len(results["errors"]),
            }

            logger.info(
                f"Restore completed: {self.agent_id} -> "
                f"{results['stats']['restored']} files, "
                f"{results['stats']['errors']} errors"
            )

            return results

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {"error": str(e), "agent_id": self.agent_id}

    async def _decompress_file(
        self, compressed_path: Path, target_path: Path
    ) -> None:
        """Decompress a gzipped file."""
        with open(compressed_path, "rb") as f:
            data = gzip.decompress(f.read())

        with open(target_path, "wb") as f:
            f.write(data)

    # ============================================================
    # Statistics
    # ============================================================

    async def get_stats(self) -> Dict[str, Any]:
        """Get backup statistics for this agent."""
        if not self.client:
            return {"enabled": False, "agent_id": self.agent_id}

        try:
            objects = list(self.client.list_objects(self.bucket))
            total_size = sum(o.size or 0 for o in objects)

            # Count by prefix
            by_prefix = {}
            for obj in objects:
                prefix = obj.object_name.split("/")[0]
                if prefix not in by_prefix:
                    by_prefix[prefix] = {"count": 0, "size": 0}
                by_prefix[prefix]["count"] += 1
                by_prefix[prefix]["size"] += obj.size or 0

            return {
                "enabled": True,
                "agent_id": self.agent_id,
                "bucket": self.bucket,
                "total_objects": len(objects),
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "by_prefix": by_prefix,
            }

        except Exception as e:
            return {"enabled": True, "agent_id": self.agent_id, "error": str(e)}

    # ============================================================
    # Lifecycle
    # ============================================================

    async def start(self) -> None:
        """Start backup agent."""
        if self.client:
            self._running = True
            await self.sync_p0_realtime()
            logger.info(f"BackupAgent started: {self.agent_id}")

    async def stop(self) -> None:
        """Stop backup agent."""
        self._running = False
        logger.info(f"BackupAgent stopped: {self.agent_id}")
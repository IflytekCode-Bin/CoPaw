# -*- coding: utf-8 -*-
"""Backup Coordinator for Multi-Agent CoPaw.

Manages backup across all agents in a single process:
- Shared resources deduplication
- Backup scheduling coordination
- Cross-agent resource sharing
"""

import asyncio
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


# Shared resources (process-level)
SHARED_RESOURCES = [
    "config.json",  # Process config (~/.copaw/config.json)
]

# Agent-unique resources
AGENT_UNIQUE_RESOURCES = [
    "sessions/",
    "dialog/",
    "memory/",
    "agent.json",
    "MEMORY.md",
    "chats.json",
]

# Deduplicatable resources (same content may exist in multiple agents)
DEDUP_RESOURCES = [
    "skills/",
    "active_skills/",
]


def instance_id_to_bucket_prefix(instance_id: str) -> str:
    """Convert instance_id (ip:port) to bucket-friendly prefix.

    Args:
        instance_id: Instance identifier like "192.168.100.103:8085"

    Returns:
        Bucket-friendly prefix like "192-168-100-103-8085"

    MinIO bucket naming rules:
        - 3-63 characters
        - Only lowercase letters, numbers, dots, hyphens
        - No consecutive dots
        - Cannot start or end with hyphen
    """
    # Replace dots and colons with hyphens, ensure lowercase
    return instance_id.replace(".", "-").replace(":", "-").lower()


def agent_id_to_bucket_suffix(agent_id: str) -> str:
    """Convert agent_id to bucket-friendly suffix.

    Args:
        agent_id: Agent identifier like "default" or "CoPaw_QA_Agent_0.1beta1"

    Returns:
        Bucket-friendly suffix like "default" or "copaw-qa-agent-0-1beta1"

    MinIO bucket naming rules:
        - 3-63 characters
        - Only lowercase letters, numbers, dots, hyphens
        - No underscores allowed
        - No consecutive dots
        - Cannot start or end with hyphen
    """
    # Replace underscores and dots with hyphens, ensure lowercase
    result = agent_id.replace("_", "-").replace(".", "-").lower()
    
    # Remove consecutive hyphens
    while "--" in result:
        result = result.replace("--", "-")
    
    # Remove leading/trailing hyphens
    result = result.strip("-")
    
    return result


class BackupCoordinator:
    """Global backup coordinator for multi-agent CoPaw.

    Features:
    - Manages multiple BackupAgent instances
    - Deduplicates shared resources
    - Coordinates backup scheduling
    - Provides cross-agent resource sharing
    """

    def __init__(
        self,
        minio_endpoint: str = "localhost:9000",
        minio_access_key: str = "minioadmin",
        minio_secret_key: str = "minioadmin123",
        minio_secure: bool = False,
        base_dir: Optional[Path] = None,
        instance_id: Optional[str] = None,
        compress_dialog: bool = True,
        compress_chats: bool = True,
    ):
        """Initialize backup coordinator.

        Args:
            minio_endpoint: MinIO endpoint
            minio_access_key: MinIO access key
            minio_secret_key: MinIO secret key
            minio_secure: Use HTTPS
            base_dir: Base directory (~/.copaw or similar)
            instance_id: CoPaw instance identifier (ip:port format like "192.168.100.103:8085")
                         Used to prefix bucket names to avoid collisions across different CoPaw instances.
                         If None, defaults to "localhost-unknown".
            compress_dialog: Compress dialog files (default True for space savings)
            compress_chats: Compress chats.json (default True)
        """
        self.endpoint = minio_endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = minio_access_key or os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = minio_secret_key or os.getenv("MINIO_SECRET_KEY", "minioadmin123")
        self.secure = minio_secure

        self.base_dir = base_dir or Path.home() / ".copaw"

        # Instance ID for bucket naming (prevents collision across CoPaw instances)
        self.instance_id = instance_id or "localhost-unknown"
        self.bucket_prefix = instance_id_to_bucket_prefix(self.instance_id)

        # Compression config
        self.compress_dialog = compress_dialog
        self.compress_chats = compress_chats

        self.client: Optional[Minio] = None

        # Buckets - prefixed with instance_id
        self.shared_bucket = f"copaw-{self.bucket_prefix}-shared"
        self.backup_bucket = f"copaw-{self.bucket_prefix}-backups"

        # Agent backup managers
        self.agent_managers: Dict[str, "BackupAgent"] = {}

        # Deduplication cache
        self._dedup_cache: Dict[str, str] = {}  # hash -> object_path

        self._running = False
        self._sync_task: Optional[asyncio.Task] = None

        self._init_minio()

    def _init_minio(self) -> None:
        """Initialize MinIO client and buckets."""
        try:
            self.client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )

            # Ensure shared bucket exists
            for bucket in [self.shared_bucket, self.backup_bucket]:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
                    logger.info(f"Created bucket: {bucket}")

            logger.info(
                f"BackupCoordinator initialized: "
                f"endpoint={self.endpoint}, shared_bucket={self.shared_bucket}"
            )

        except S3Error as e:
            logger.error(f"MinIO initialization failed: {e}")
            self.client = None

    # ============================================================
    # Agent Registration
    # ============================================================

    async def register_agent(
        self,
        agent_id: str,
        workspace_dir: Path,
    ) -> "BackupAgent":
        """Register an agent workspace for backup.

        Args:
            agent_id: Agent identifier
            workspace_dir: Workspace directory path

        Returns:
            BackupAgent instance
        """
        from .backup_agent import BackupAgent

        # MinIO bucket names must be lowercase and valid
        # Format: copaw-{instance_prefix}-{agent_id_suffix}
        # Use agent_id_to_bucket_suffix to handle special characters
        agent_suffix = agent_id_to_bucket_suffix(agent_id)
        bucket = f"copaw-{self.bucket_prefix}-{agent_suffix}"

        # Ensure agent bucket exists
        if self.client and not self.client.bucket_exists(bucket):
            self.client.make_bucket(bucket)
            logger.info(f"Created agent bucket: {bucket}")

        agent_manager = BackupAgent(
            agent_id=agent_id,
            workspace_dir=workspace_dir,
            client=self.client,
            bucket=bucket,
            coordinator=self,
            compress_dialog=self.compress_dialog,
            compress_chats=self.compress_chats,
        )

        self.agent_managers[agent_id] = agent_manager
        logger.info(f"Registered agent: {agent_id} -> {bucket}")

        return agent_manager

    async def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent."""
        if agent_id in self.agent_managers:
            await self.agent_managers[agent_id].stop()
            del self.agent_managers[agent_id]
            logger.info(f"Unregistered agent: {agent_id}")

    # ============================================================
    # Shared Resources
    # ============================================================

    async def sync_shared_resources(self) -> Dict[str, bool]:
        """Sync process-level shared resources.

        This includes:
        - Process config.json (~/.copaw/config.json)
        - Shared skills (deduplicated)
        """
        results = {}

        # Process config
        process_config = self.base_dir / "config.json"
        if process_config.exists():
            results["config.json"] = await self._upload_to_shared(
                process_config, "config/process_config.json"
            )

        logger.info(f"Shared resources sync: {len(results)} files")
        return results

    async def _upload_to_shared(
        self,
        local_path: Path,
        remote_path: str,
    ) -> bool:
        """Upload file to shared bucket."""
        if not self.client:
            return False

        try:
            checksum = await self._calculate_checksum(local_path)

            # Check if unchanged
            try:
                stat = self.client.stat_object(self.shared_bucket, remote_path)
                if stat.metadata.get("x-amz-meta-sha256") == checksum:
                    return True
            except S3Error:
                pass

            self.client.fput_object(
                self.shared_bucket,
                remote_path,
                str(local_path),
                metadata={"sha256": checksum},
            )
            logger.debug(f"Uploaded to shared: {local_path.name}")
            return True

        except Exception as e:
            logger.error(f"Upload to shared failed: {e}")
            return False

    # ============================================================
    # Deduplication
    # ============================================================

    async def deduplicate_and_upload(
        self,
        agent_id: str,
        resource_path: Path,
        resource_type: str,
    ) -> str:
        """Deduplicate and upload resource.

        If same content already exists in shared bucket,
        create reference instead of uploading again.

        Args:
            agent_id: Agent ID
            resource_path: Local resource path
            resource_type: Resource type (skills, active_skills)

        Returns:
            Object path (either in shared or agent bucket)
        """
        if not self.client:
            return ""

        # Calculate hash
        resource_hash = await self._calculate_dir_hash(resource_path)

        # Check if already exists in shared
        if resource_hash in self._dedup_cache:
            # Record reference
            reference_path = f"references/{agent_id}/{resource_type}"
            await self._record_reference(
                agent_id, resource_type, self._dedup_cache[resource_hash]
            )
            logger.info(
                f"Deduplicated: {agent_id}/{resource_type} -> "
                f"shared/{self._dedup_cache[resource_hash]}"
            )
            return self._dedup_cache[resource_hash]

        # Upload to shared bucket
        remote_path = f"{resource_type}/{resource_hash}"
        await self._upload_dir_to_shared(resource_path, remote_path)

        # Record in cache
        self._dedup_cache[resource_hash] = remote_path

        # Record reference for this agent
        await self._record_reference(agent_id, resource_type, remote_path)

        return remote_path

    async def _calculate_dir_hash(self, dir_path: Path) -> str:
        """Calculate hash of directory contents."""
        hasher = hashlib.sha256()

        for file_path in sorted(dir_path.rglob("*")):
            if file_path.is_file() and not file_path.name.endswith((".tmp", ".pyc")):
                file_hash = await self._calculate_checksum(file_path)
                hasher.update(file_hash.encode())

        return hasher.hexdigest()[:16]  # Use first 16 chars for brevity

    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _upload_dir_to_shared(
        self,
        local_dir: Path,
        remote_prefix: str,
    ) -> bool:
        """Upload directory to shared bucket."""
        if not local_dir.exists():
            return False

        for file_path in local_dir.rglob("*"):
            if not file_path.is_file():
                continue

            relative = file_path.relative_to(local_dir)
            remote_path = f"{remote_prefix}/{relative}"

            try:
                self.client.fput_object(
                    self.shared_bucket,
                    remote_path,
                    str(file_path),
                )
            except Exception as e:
                logger.error(f"Upload failed: {file_path} -> {e}")

        return True

    async def _record_reference(
        self,
        agent_id: str,
        resource_type: str,
        shared_path: str,
    ) -> None:
        """Record resource reference in agent bucket."""
        if not self.client:
            return

        reference_data = {
            "agent_id": agent_id,
            "resource_type": resource_type,
            "shared_path": shared_path,
            "timestamp": datetime.now().isoformat(),
        }

        # Upload reference JSON
        reference_json = Path(f"/tmp/ref_{agent_id}_{resource_type}.json")
        reference_json.write_text(str(reference_data))

        bucket = f"copaw-{agent_id}"
        self.client.fput_object(
            bucket,
            f"references/{resource_type}.json",
            str(reference_json),
        )
        reference_json.unlink()

    # ============================================================
    # Backup Coordination
    # ============================================================

    async def schedule_full_backup(self) -> Dict[str, Any]:
        """Schedule full backup for all agents.

        Strategy:
        1. Manager agent (default) first
        2. Worker agents in parallel
        3. Deduplicate shared resources
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "agents": {},
        }

        # Sync shared resources first
        results["shared"] = await self.sync_shared_resources()

        # Manager agent first (default)
        if "default" in self.agent_managers:
            logger.info("Starting manager agent backup...")
            results["agents"]["default"] = await self.agent_managers["default"].full_backup()

        # Worker agents in parallel
        worker_agents = [
            aid for aid in self.agent_managers.keys()
            if aid != "default"
        ]

        if worker_agents:
            logger.info(f"Starting worker agents backup: {worker_agents}")
            worker_results = await asyncio.gather(
                *[self.agent_managers[aid].full_backup() for aid in worker_agents],
                return_exceptions=True,
            )

            for aid, result in zip(worker_agents, worker_results):
                if isinstance(result, Exception):
                    results["agents"][aid] = {"error": str(result)}
                else:
                    results["agents"][aid] = result

        # Calculate totals
        total_files = sum(
            r.get("stats", {}).get("total", 0)
            for r in results["agents"].values()
            if isinstance(r, dict)
        )
        results["total_files"] = total_files

        logger.info(f"Full backup completed: {total_files} files across {len(self.agent_managers)} agents")
        return results

    async def incremental_backup(self) -> Dict[str, Any]:
        """Incremental backup for all agents."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "agents": {},
        }

        # All agents parallel incremental backup
        backup_tasks = [
            self.agent_managers[aid].incremental_backup()
            for aid in self.agent_managers
        ]

        if backup_tasks:
            agent_results = await asyncio.gather(*backup_tasks, return_exceptions=True)

            for aid, result in zip(self.agent_managers.keys(), agent_results):
                if isinstance(result, Exception):
                    results["agents"][aid] = {"error": str(result)}
                else:
                    results["agents"][aid] = result

        return results

    # ============================================================
    # Restore Methods
    # ============================================================

    async def restore_agent(
        self,
        agent_id: str,
        backup_prefix: Optional[str] = None,
        resources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Restore a specific agent from backup.

        Args:
            agent_id: Agent ID to restore
            backup_prefix: Backup prefix (realtime, change)
            resources: Specific resources to restore

        Returns:
            Restore result
        """
        if agent_id not in self.agent_managers:
            return {"error": f"Agent {agent_id} not registered"}

        agent_manager = self.agent_managers[agent_id]
        return await agent_manager.restore(backup_prefix=backup_prefix, resources=resources)

    async def restore_all(
        self,
        backup_prefix: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restore all agents from backup.

        Args:
            backup_prefix: Backup prefix (realtime, change)

        Returns:
            Restore results for all agents
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "agents": {},
        }

        # Restore all agents in parallel
        restore_tasks = [
            self.restore_agent(aid, backup_prefix)
            for aid in self.agent_managers
        ]

        if restore_tasks:
            agent_results = await asyncio.gather(*restore_tasks, return_exceptions=True)

            for aid, result in zip(self.agent_managers.keys(), agent_results):
                if isinstance(result, Exception):
                    results["agents"][aid] = {"error": str(result)}
                else:
                    results["agents"][aid] = result

        # Calculate totals
        total_restored = sum(
            r.get("stats", {}).get("restored", 0)
            for r in results["agents"].values()
            if isinstance(r, dict)
        )
        results["total_restored"] = total_restored

        return results

    # ============================================================
    # Scheduled Backup
    # ============================================================

    async def start_scheduled_backup(
        self,
        full_backup_cron: str = "0 2 * * *",
        incremental_interval: int = 3600,
    ) -> None:
        """Start scheduled backup tasks.

        Args:
            full_backup_cron: Cron expression for full backup (default: daily at 2am)
            incremental_interval: Interval in seconds for incremental backup (default: 1 hour)
        """
        from croniter import croniter

        self._running = True

        async def backup_loop():
            """Background backup loop."""
            last_incremental = datetime.now()

            while self._running:
                now = datetime.now()

                # Check if it's time for full backup
                try:
                    cron = croniter(full_backup_cron, now)
                    next_full = cron.get_next(datetime)

                    # If we're past the next scheduled time
                    if (next_full - now).total_seconds() < 60:
                        logger.info("Starting scheduled full backup")
                        await self.schedule_full_backup()
                except Exception as e:
                    logger.error(f"Full backup scheduling error: {e}")

                # Check if it's time for incremental backup
                if (now - last_incremental).total_seconds() >= incremental_interval:
                    logger.info("Starting scheduled incremental backup")
                    await self.incremental_backup()
                    last_incremental = now

                # Sleep for a minute before checking again
                await asyncio.sleep(60)

        self._sync_task = asyncio.create_task(backup_loop())
        logger.info(
            f"Scheduled backup started: full={full_backup_cron}, "
            f"incremental={incremental_interval}s"
        )

    # ============================================================
    # Lifecycle
    # ============================================================

    async def start(self) -> None:
        """Start backup coordinator."""
        if not self.client:
            logger.warning("BackupCoordinator not started: MinIO unavailable")
            return

        self._running = True

        # Initial sync
        await self.sync_shared_resources()

        # Start all agent managers
        for agent_manager in self.agent_managers.values():
            await agent_manager.start()

        logger.info(f"BackupCoordinator started: {len(self.agent_managers)} agents")

    async def stop(self) -> None:
        """Stop backup coordinator."""
        self._running = False

        # Cancel scheduled backup task
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        # Stop all agent managers
        for agent_manager in self.agent_managers.values():
            await agent_manager.stop()

        logger.info("BackupCoordinator stopped")

    async def get_stats(self) -> Dict[str, Any]:
        """Get backup statistics for all agents."""
        stats = {
            "coordinator": {
                "endpoint": self.endpoint,
                "shared_bucket": self.shared_bucket,
                "backup_bucket": self.backup_bucket,
            },
            "agents": {},
        }

        for agent_id, agent_manager in self.agent_managers.items():
            stats["agents"][agent_id] = await agent_manager.get_stats()

        # Shared bucket stats
        if self.client:
            try:
                objects = list(self.client.list_objects(self.shared_bucket))
                stats["shared"] = {
                    "total_objects": len(objects),
                    "total_size_mb": round(
                        sum(o.size or 0 for o in objects) / 1024 / 1024, 2
                    ),
                }
            except Exception as e:
                stats["shared"] = {"error": str(e)}

        return stats
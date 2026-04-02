# -*- coding: utf-8 -*-
"""MinIO Storage Manager for CoPaw.

Handles:
- Realtime sync of config/memory/sessions
- Scheduled backup of file-store/skills/media
- Large file storage
- Cross-agent resource sharing
"""

import asyncio
import gzip
import hashlib
import json
import logging
import tarfile
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from minio import Minio
from minio.error import S3Error
from watchfiles import awatch

from .constants import SYNC_STRATEGIES, CLEANUP_RULES, MINIO_BUCKET_TEMPLATE

logger = logging.getLogger(__name__)


class MinIOStorageManager:
    """MinIO-based storage manager for CoPaw agents.

    Features:
    - Automatic file sync based on priority
    - Scheduled backups
    - Large file storage with deduplication
    - Cross-agent resource sharing
    """

    def __init__(
        self,
        agent_id: str = "default",
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin123",
        secure: bool = False,
        working_dir: Optional[Path] = None,
    ):
        """Initialize MinIO storage manager.

        Args:
            agent_id: Agent identifier for bucket naming
            endpoint: MinIO server endpoint
            access_key: MinIO access key
            secret_key: MinIO secret key
            secure: Use HTTPS
            working_dir: Local working directory to sync
        """
        self.agent_id = agent_id
        self.endpoint = endpoint
        self.bucket = MINIO_BUCKET_TEMPLATE.format(agent_id=agent_id)
        self.working_dir = working_dir or Path.home() / ".copaw"

        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

        self._ensure_bucket()
        self._sync_tasks: Dict[str, asyncio.Task] = {}
        self._debounce_timers: Dict[str, asyncio.TimerHandle] = {}
        self._running = False

        logger.info(
            f"MinIOStorageManager initialized: bucket={self.bucket}, "
            f"endpoint={endpoint}"
        )

    def _ensure_bucket(self) -> None:
        """Create bucket if not exists."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created bucket: {self.bucket}")
        except S3Error as e:
            logger.error(f"Failed to create bucket: {e}")
            raise

    # ============================================================
    # File Upload Methods
    # ============================================================

    async def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        compress: bool = False,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload a file to MinIO.

        Args:
            local_path: Local file path
            remote_path: Remote object path
            compress: Gzip compress before upload
            metadata: Optional metadata

        Returns:
            Object URI
        """
        if not local_path.exists():
            raise FileNotFoundError(f"File not found: {local_path}")

        content_type = self._get_content_type(local_path)

        if compress:
            # Compress and upload
            with open(local_path, 'rb') as f:
                compressed = gzip.compress(f.read())

            await asyncio.to_thread(
                self.client.put_object,
                self.bucket,
                f"{remote_path}.gz",
                io.BytesIO(compressed),
                len(compressed),
                content_type='application/gzip',
                metadata=metadata,
            )
            return f"{remote_path}.gz"
        else:
            await asyncio.to_thread(
                self.client.fput_object,
                self.bucket,
                remote_path,
                str(local_path),
                content_type=content_type,
                metadata=metadata,
            )
            return remote_path

    async def upload_json(
        self,
        remote_path: str,
        data: Dict[str, Any],
        compress: bool = False,
    ) -> str:
        """Upload JSON data to MinIO.

        Args:
            remote_path: Remote object path
            data: JSON-serializable dict
            compress: Gzip compress

        Returns:
            Object URI
        """
        content = json.dumps(data, ensure_ascii=False, indent=2)

        if compress:
            compressed = gzip.compress(content.encode('utf-8'))
            await asyncio.to_thread(
                self.client.put_object,
                self.bucket,
                f"{remote_path}.gz",
                io.BytesIO(compressed),
                len(compressed),
                content_type='application/gzip',
            )
            return f"{remote_path}.gz"
        else:
            await asyncio.to_thread(
                self.client.put_object,
                self.bucket,
                remote_path,
                io.BytesIO(content.encode('utf-8')),
                len(content),
                content_type='application/json',
            )
            return remote_path

    async def upload_directory(
        self,
        local_dir: Path,
        remote_prefix: str,
        exclude_patterns: Optional[List[str]] = None,
    ) -> List[str]:
        """Upload a directory recursively.

        Args:
            local_dir: Local directory path
            remote_prefix: Remote path prefix
            exclude_patterns: Patterns to exclude

        Returns:
            List of uploaded object paths
        """
        exclude_patterns = exclude_patterns or []
        uploaded = []

        for file_path in local_dir.rglob('*'):
            if not file_path.is_file():
                continue

            # Check exclude patterns
            rel_path = file_path.relative_to(local_dir)
            if any(rel_path.match(p) for p in exclude_patterns):
                continue

            remote_path = f"{remote_prefix}/{rel_path}"
            await self.upload_file(file_path, remote_path)
            uploaded.append(remote_path)

        return uploaded

    # ============================================================
    # File Download Methods
    # ============================================================

    async def download_file(
        self,
        remote_path: str,
        local_path: Path,
        decompress: bool = False,
    ) -> Path:
        """Download a file from MinIO.

        Args:
            remote_path: Remote object path
            local_path: Local file path
            decompress: Decompress gzip

        Returns:
            Local file path
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if decompress or remote_path.endswith('.gz'):
            response = await asyncio.to_thread(
                self.client.get_object,
                self.bucket,
                remote_path,
            )
            compressed = response.read()
            data = gzip.decompress(compressed)

            # Remove .gz suffix from local path
            if local_path.suffix == '.gz':
                local_path = local_path.with_suffix('')

            with open(local_path, 'wb') as f:
                f.write(data)
        else:
            await asyncio.to_thread(
                self.client.fget_object,
                self.bucket,
                remote_path,
                str(local_path),
            )

        return local_path

    async def download_json(
        self,
        remote_path: str,
    ) -> Dict[str, Any]:
        """Download and parse JSON from MinIO.

        Args:
            remote_path: Remote object path

        Returns:
            Parsed JSON dict
        """
        response = await asyncio.to_thread(
            self.client.get_object,
            self.bucket,
            remote_path,
        )
        data = response.read()

        if remote_path.endswith('.gz'):
            data = gzip.decompress(data)

        return json.loads(data)

    # ============================================================
    # Sync Methods
    # ============================================================

    async def sync_config(self) -> None:
        """Sync config files (P0 realtime)."""
        config_dir = self.working_dir
        config_files = [
            ("config.json", "config/config.json"),
            ("chats.json", "config/chats.json"),
            ("skill.json", "config/skill.json"),
            ("token_usage.json", "config/token_usage.json"),
        ]

        for local_name, remote_path in config_files:
            local_path = config_dir / local_name
            if local_path.exists():
                await self.upload_file(local_path, remote_path)
                logger.debug(f"Synced config: {local_name}")

    async def sync_memory(self) -> None:
        """Sync memory files (P0 realtime)."""
        memory_dir = self.working_dir / "memory"
        if memory_dir.exists():
            await self.upload_directory(
                memory_dir,
                "memory/daily",
                exclude_patterns=["*.tmp"],
            )
            logger.debug("Synced memory directory")

        # Main MEMORY.md
        memory_md = self.working_dir / "MEMORY.md"
        if memory_md.exists():
            await self.upload_file(memory_md, "memory/MEMORY.md")

    async def sync_sessions(self) -> None:
        """Sync session files (P0 realtime)."""
        sessions_dir = self.working_dir / "sessions"
        if sessions_dir.exists():
            await self.upload_directory(
                sessions_dir,
                "sessions",
                exclude_patterns=["compact_invalid_*", "*.tmp"],
            )
            logger.debug("Synced sessions directory")

    async def sync_dialog(self) -> None:
        """Sync dialog history (P0 realtime)."""
        dialog_dir = self.working_dir / "dialog"
        if dialog_dir.exists():
            await self.upload_directory(
                dialog_dir,
                "dialog",
            )
            logger.debug("Synced dialog directory")

    async def backup_file_store(self) -> None:
        """Backup file-store with Chroma (P2 scheduled)."""
        file_store_dir = self.working_dir / "file_store"
        if not file_store_dir.exists():
            return

        # Create tarball
        date_str = datetime.now().strftime('%Y-%m-%d')
        tar_path = Path(f"/tmp/file_store_{date_str}.tar.gz")

        with tarfile.open(tar_path, 'w:gz') as tar:
            tar.add(file_store_dir, arcname='file_store')

        # Upload
        remote_path = f"exports/{date_str}/file_store.tar.gz"
        await self.upload_file(tar_path, remote_path)
        tar_path.unlink()

        logger.info(f"Backed up file-store to {remote_path}")

    async def backup_skills(self) -> None:
        """Backup skills (P2 scheduled)."""
        skills_dirs = [
            ("skill_pool", "skills/skill_pool"),
            ("customized_skills", "skills/customized_skills"),
        ]

        for dir_name, remote_prefix in skills_dirs:
            local_dir = self.working_dir / dir_name
            if local_dir.exists():
                await self.upload_directory(local_dir, remote_prefix)

        logger.info("Backed up skills")

    async def backup_media(self) -> None:
        """Backup media files (P2 scheduled)."""
        media_dir = self.working_dir / "media"
        if media_dir.exists():
            await self.upload_directory(media_dir, "media")
            logger.info("Backed up media")

    async def backup_full(self) -> None:
        """Create full workspace backup."""
        date_str = datetime.now().strftime('%Y-%m-%d')
        tar_path = Path(f"/tmp/copaw_backup_{date_str}.tar.gz")

        # Exclude large/temporary files
        exclude_patterns = [
            "copaw.log",
            "logs/*",
            "tool_result/*",
            "embedding_cache/*",
            "sessions/compact_invalid_*",
        ]

        with tarfile.open(tar_path, 'w:gz') as tar:
            for item in self.working_dir.iterdir():
                # Skip excluded patterns
                if any(item.name.match(p) for p in exclude_patterns):
                    continue
                tar.add(item, arcname=item.name)

        # Upload
        remote_path = f"exports/{date_str}/workspace.tar.gz"
        await self.upload_file(tar_path, remote_path)
        tar_path.unlink()

        logger.info(f"Created full backup: {remote_path}")

    # ============================================================
    # File Watching
    # ============================================================

    async def start_watching(self) -> None:
        """Start watching for file changes."""
        self._running = True

        # Watch paths with P0/P1 priority
        watch_paths = [
            self.working_dir / "config.json",
            self.working_dir / "chats.json",
            self.working_dir / "MEMORY.md",
            self.working_dir / "memory",
            self.working_dir / "sessions",
            self.working_dir / "dialog",
        ]

        async for changes in awatch(*[str(p) for p in watch_paths if p.exists()]):
            if not self._running:
                break

            for change_type, path_str in changes:
                path = Path(path_str)
                await self._handle_file_change(path, change_type)

    async def _handle_file_change(
        self,
        path: Path,
        change_type: Any,
    ) -> None:
        """Handle file change event."""
        rel_path = path.relative_to(self.working_dir)
        path_str = str(rel_path)

        # Determine sync strategy
        for prefix, strategy in SYNC_STRATEGIES.items():
            if path_str.startswith(prefix.rstrip('/')):
                debounce_ms = strategy.get('debounce_ms', 0)

                if debounce_ms > 0:
                    # Debounce
                    if path_str in self._debounce_timers:
                        self._debounce_timers[path_str].cancel()

                    loop = asyncio.get_event_loop()
                    self._debounce_timers[path_str] = loop.call_later(
                        debounce_ms / 1000,
                        lambda: asyncio.create_task(self._sync_file(path)),
                    )
                else:
                    # Immediate sync
                    await self._sync_file(path)
                break

    async def _sync_file(self, path: Path) -> None:
        """Sync a single file."""
        rel_path = path.relative_to(self.working_dir)
        remote_path = str(rel_path)

        try:
            await self.upload_file(path, remote_path)
            logger.debug(f"Synced: {rel_path}")
        except Exception as e:
            logger.error(f"Failed to sync {rel_path}: {e}")

    def stop_watching(self) -> None:
        """Stop watching for file changes."""
        self._running = False

        # Cancel debounce timers
        for timer in self._debounce_timers.values():
            timer.cancel()
        self._debounce_timers.clear()

    # ============================================================
    # Cleanup Methods
    # ============================================================

    async def cleanup_local(self) -> Dict[str, int]:
        """Clean up local files based on rules.

        Returns:
            Dict of {pattern: count} of cleaned files
        """
        cleaned = {}

        for pattern, rules in CLEANUP_RULES.items():
            count = 0

            # Parse pattern
            if '*' in pattern:
                # Glob pattern
                base_dir = self.working_dir / pattern.split('*')[0].rstrip('/')
                if base_dir.exists():
                    for file_path in self.working_dir.glob(pattern):
                        if self._should_clean(file_path, rules):
                            file_path.unlink()
                            count += 1

            cleaned[pattern] = count
            if count > 0:
                logger.info(f"Cleaned {count} files matching {pattern}")

        return cleaned

    def _should_clean(self, path: Path, rules: Dict[str, Any]) -> bool:
        """Check if a file should be cleaned based on rules."""
        import time

        if 'max_age_days' in rules:
            max_age = timedelta(days=rules['max_age_days'])
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if datetime.now() - mtime > max_age:
                return True

        if 'max_age_hours' in rules:
            max_age = timedelta(hours=rules['max_age_hours'])
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if datetime.now() - mtime > max_age:
                return True

        if 'max_size_mb' in rules:
            max_size = rules['max_size_mb'] * 1024 * 1024
            if path.stat().st_size > max_size:
                return True

        return False

    # ============================================================
    # Utility Methods
    # ============================================================

    def _get_content_type(self, path: Path) -> str:
        """Get content type from file extension."""
        content_types = {
            '.json': 'application/json',
            '.md': 'text/markdown',
            '.txt': 'text/plain',
            '.py': 'text/x-python',
            '.sh': 'text/x-shellscript',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf',
            '.sqlite3': 'application/x-sqlite3',
            '.tar.gz': 'application/gzip',
            '.gz': 'application/gzip',
        }
        return content_types.get(path.suffix.lower(), 'application/octet-stream')

    async def list_objects(
        self,
        prefix: str = "",
    ) -> List[Dict[str, Any]]:
        """List objects in bucket.

        Args:
            prefix: Path prefix to filter

        Returns:
            List of object info dicts
        """
        objects = await asyncio.to_thread(
            self.client.list_objects,
            self.bucket,
            prefix,
            recursive=True,
        )

        result = []
        for obj in objects:
            result.append({
                "name": obj.object_name,
                "size": obj.size,
                "last_modified": obj.last_modified,
                "etag": obj.etag,
            })

        return result

    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dict with total size, object count, etc.
        """
        objects = await self.list_objects()

        total_size = sum(obj['size'] for obj in objects)

        # Group by prefix
        by_prefix = {}
        for obj in objects:
            prefix = obj['name'].split('/')[0]
            if prefix not in by_prefix:
                by_prefix[prefix] = {"count": 0, "size": 0}
            by_prefix[prefix]['count'] += 1
            by_prefix[prefix]['size'] += obj['size']

        return {
            "bucket": self.bucket,
            "total_objects": len(objects),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "by_prefix": by_prefix,
        }
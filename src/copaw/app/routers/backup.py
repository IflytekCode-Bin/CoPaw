# -*- coding: utf-8 -*-
"""Backup API endpoints for triggering backup and getting status."""

from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel

router = APIRouter(prefix="/backup", tags=["backup"])


class TriggerBackupBody(BaseModel):
    """Request body for POST /backup/trigger."""

    full: bool = True


class AgentBackupResult(BaseModel):
    """Single agent backup result."""

    agent_id: str
    bucket: str = ""
    files_synced: List[str] = []
    files_failed: List[str] = []
    total: int = 0
    success: int = 0


class BackupResult(BaseModel):
    """Backup result response."""

    success: bool
    message: str
    files_backed_up: int = 0
    duration_ms: int = 0
    agents: List[AgentBackupResult] = []
    shared_files: List[str] = []


class BackupStatus(BaseModel):
    """Backup status response."""

    last_full_backup: str | None = None
    last_incremental_backup: str | None = None
    total_files: int = 0
    total_size: int = 0
    buckets: list[str] = []


class ConnectionTestResult(BaseModel):
    """Connection test result."""

    success: bool
    message: str


def _extract_files_from_result(result: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """Extract synced and failed files from backup result."""
    from pathlib import Path
    synced = []
    failed = []

    # P0 realtime files
    p0 = result.get("p0", {})
    for file, status in p0.items():
        # Extract just the filename from full path
        filename = Path(file).name if "/" in file else file
        if status:
            synced.append(f"realtime/{filename}")
        else:
            failed.append(f"realtime/{filename}")

    # P1 change files
    p1 = result.get("p1", {})
    for file, status in p1.items():
        # Extract just the filename from full path
        filename = Path(file).name if "/" in file else file
        if status:
            synced.append(f"change/{filename}")
        else:
            failed.append(f"change/{filename}")

    return synced, failed


@router.get(
    "/status",
    summary="Get backup status",
)
async def get_backup_status(request: Request) -> BackupStatus:
    """Get current backup status."""
    from ..agent_context import get_agent_for_request
    from ..backup.backup_coordinator import get_backup_coordinator

    agent = await get_agent_for_request(request)
    coordinator = get_backup_coordinator()

    if coordinator is None:
        return BackupStatus(
            last_full_backup=None,
            last_incremental_backup=None,
            total_files=0,
            total_size=0,
            buckets=[],
        )

    # Get status from coordinator
    status = await coordinator.get_status()
    return BackupStatus(**status)


@router.post(
    "/trigger",
    summary="Trigger manual backup",
)
async def trigger_backup(
    request: Request,
    body: TriggerBackupBody = Body(default=TriggerBackupBody()),
) -> BackupResult:
    """Trigger a manual backup and return detailed file list."""
    from ..agent_context import get_agent_for_request
    from ..backup.backup_coordinator import get_backup_coordinator
    import time

    agent = await get_agent_for_request(request)
    coordinator = get_backup_coordinator()

    if coordinator is None:
        return BackupResult(
            success=False,
            message="Backup coordinator not initialized",
        )

    start_time = time.time()
    try:
        result = await coordinator.trigger_backup(full=body.full)
        duration_ms = int((time.time() - start_time) * 1000)

        # Extract detailed file info
        agents_results = []
        total_files = 0

        # Process agent results
        for agent_id, agent_data in result.get("agents", {}).items():
            if isinstance(agent_data, dict) and "error" not in agent_data:
                synced, failed = _extract_files_from_result(agent_data)
                stats = agent_data.get("stats", {})
                agents_results.append(AgentBackupResult(
                    agent_id=agent_id,
                    bucket=agent_data.get("bucket", ""),
                    files_synced=synced,
                    files_failed=failed,
                    total=stats.get("total", len(synced) + len(failed)),
                    success=stats.get("success", len(synced)),
                ))
                total_files += len(synced)

        # Process shared files
        shared_result = result.get("shared", {})
        shared_files = []
        if isinstance(shared_result, dict):
            for file, status in shared_result.items():
                if status:
                    shared_files.append(file)

        backup_type = "全量备份" if body.full else "增量备份"
        message = f"{backup_type}完成: {total_files + len(shared_files)} 个文件"

        return BackupResult(
            success=True,
            message=message,
            files_backed_up=total_files + len(shared_files),
            duration_ms=duration_ms,
            agents=agents_results,
            shared_files=shared_files,
        )
    except Exception as e:
        return BackupResult(
            success=False,
            message=f"备份失败: {str(e)}",
        )


@router.post(
    "/test-connection",
    summary="Test MinIO connection",
)
async def test_connection(request: Request) -> ConnectionTestResult:
    """Test MinIO connection."""
    from ..agent_context import get_agent_for_request
    from ..backup.backup_coordinator import get_backup_coordinator

    agent = await get_agent_for_request(request)
    coordinator = get_backup_coordinator()

    if coordinator is None:
        return ConnectionTestResult(
            success=False,
            message="Backup coordinator not initialized",
        )

    try:
        success = await coordinator.test_connection()
        if success:
            return ConnectionTestResult(
                success=True,
                message="连接成功",
            )
        else:
            return ConnectionTestResult(
                success=False,
                message="连接失败",
            )
    except Exception as e:
        return ConnectionTestResult(
            success=False,
            message=f"连接测试失败: {str(e)}",
        )
# -*- coding: utf-8 -*-
"""Backup API endpoints for triggering backup and getting status."""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Body, Request
from pydantic import BaseModel

router = APIRouter(prefix="/backup", tags=["backup"])


class TriggerBackupBody(BaseModel):
    """Request body for POST /backup/trigger."""

    full: bool = True


class BackupResult(BaseModel):
    """Backup result response."""

    success: bool
    message: str
    files_backed_up: int = 0
    duration_ms: int = 0


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
    """Trigger a manual backup."""
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

        total_files = sum(1 for v in result.values() if v)
        return BackupResult(
            success=True,
            message=f"Backup completed successfully",
            files_backed_up=total_files,
            duration_ms=duration_ms,
        )
    except Exception as e:
        return BackupResult(
            success=False,
            message=f"Backup failed: {str(e)}",
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
                message="Connection successful",
            )
        else:
            return ConnectionTestResult(
                success=False,
                message="Connection failed",
            )
    except Exception as e:
        return ConnectionTestResult(
            success=False,
            message=f"Connection test failed: {str(e)}",
        )
# -*- coding: utf-8 -*-
"""Request/response schemas for config API endpoints."""

from typing import List, Optional

from pydantic import BaseModel, Field

from ...config.config import ActiveHoursConfig


class HeartbeatBody(BaseModel):
    """Request body for PUT /config/heartbeat."""

    enabled: bool = False
    every: str = "6h"
    target: str = "main"
    active_hours: Optional[ActiveHoursConfig] = Field(
        default=None,
        alias="activeHours",
    )

    model_config = {"populate_by_name": True, "extra": "allow"}


class BackupBody(BaseModel):
    """Request body for PUT /config/backup."""

    enabled: bool = False
    endpoint: str = "localhost:9000"
    access_key: str = Field(default="", alias="access_key")
    secret_key: str = Field(default="", alias="secret_key")
    secure: bool = False
    full_backup_schedule: str = "0 2 * * *"
    incremental_interval: int = 3600
    retention_days: int = 30
    dedup_enabled: bool = True
    dedup_resources: List[str] = Field(default_factory=lambda: ["skills/", "active_skills/"])
    compress_dialog: bool = True
    compress_chats: bool = True

    model_config = {"populate_by_name": True, "extra": "allow"}

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test BackupManager."""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, "/Data/CodeBase/iflycode/CoPaw/src")

from copaw.app.backup import BackupManager


async def test_backup():
    """Test backup manager."""
    bm = BackupManager(
        workspace_dir="/home/crazybin777/.copaw/workspaces/default",
        agent_id="default",
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin123",
        enabled=True,
    )
    # 强制启用（绕过环境变量检查）
    bm.enabled = True
    bm._init_minio()

    print(f"BackupManager enabled: {bm.enabled}")
    print(f"Bucket: {bm.bucket}")
    print(f"Client: {bm.client}")

    if bm.enabled and bm.client:
        # 测试 P0 同步
        print("\n=== Testing P0 Realtime Sync ===")
        results = await bm.sync_p0_realtime()
        print(f"Synced {len(results)} files")
        for path, success in list(results.items())[:10]:
            print(f"  {Path(path).name}: {'✓' if success else '✗'}")

        # 获取统计
        print("\n=== Backup Stats ===")
        stats = await bm.get_stats()
        print(f"Stats: {stats}")
    else:
        print("MinIO not available, testing skipped")


if __name__ == "__main__":
    asyncio.run(test_backup())
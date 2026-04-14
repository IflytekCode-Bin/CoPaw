#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test Multi-Agent Backup Coordinator."""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, "/Data/CodeBase/iflycode/CoPaw/src")

from copaw.app.backup import BackupCoordinator, BackupAgent


async def test_multi_agent_backup():
    """Test backup coordinator with multiple agents."""

    # Initialize coordinator
    coordinator = BackupCoordinator(
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin123",
        base_dir=Path.home() / ".copaw",
    )

    print(f"Coordinator initialized: {coordinator.client}")
    print(f"Shared bucket: {coordinator.shared_bucket}")

    # Register agents
    agents = {
        "default": Path.home() / ".copaw/workspaces/default",
        "mS7xfg": Path.home() / ".copaw/workspaces/mS7xfg",  # dev
        "HtgnSz": Path.home() / ".copaw/workspaces/HtgnSz",  # ops
        "cwcQko": Path.home() / ".copaw/workspaces/cwcQko",  # test
    }

    for agent_id, workspace_dir in agents.items():
        if workspace_dir.exists():
            await coordinator.register_agent(agent_id, workspace_dir)
            print(f"Registered: {agent_id}")

    # Start coordinator
    await coordinator.start()

    # Test full backup
    print("\n=== Full Backup ===")
    results = await coordinator.schedule_full_backup()

    print(f"Timestamp: {results['timestamp']}")
    print(f"Total files: {results['total_files']}")

    for agent_id, agent_result in results["agents"].items():
        stats = agent_result.get("stats", {})
        print(f"  {agent_id}: {stats.get('success', 0)}/{stats.get('total', 0)} files")

    # Get stats
    print("\n=== Backup Stats ===")
    stats = await coordinator.get_stats()

    print(f"Coordinator:")
    print(f"  Endpoint: {stats['coordinator']['endpoint']}")

    print(f"Shared bucket:")
    shared = stats.get("shared", {})
    print(f"  Objects: {shared.get('total_objects', 0)}")
    print(f"  Size: {shared.get('total_size_mb', 0)} MB")

    print(f"\nAgent buckets:")
    for agent_id, agent_stats in stats["agents"].items():
        print(f"  {agent_id}:")
        print(f"    Objects: {agent_stats.get('total_objects', 0)}")
        print(f"    Size: {agent_stats.get('total_size_mb', 0)} MB")

    # Stop
    await coordinator.stop()
    print("\nBackup test completed!")


if __name__ == "__main__":
    asyncio.run(test_multi_agent_backup())
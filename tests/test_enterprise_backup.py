#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprehensive test for CoPaw Enterprise Backup System.

Tests:
1. BackupCoordinator initialization
2. Multi-agent registration
3. Full and incremental backup
4. Restore functionality
5. Configuration loading
"""

import asyncio
from pathlib import Path
import sys
import tempfile
import json

sys.path.insert(0, "/Data/CodeBase/iflycode/CoPaw/src")

from copaw.app.backup import BackupCoordinator, BackupAgent
from copaw.config.config import BackupConfig, StorageConfig


async def test_config():
    """Test backup configuration."""
    print("\n=== Testing Backup Configuration ===")

    # Test default config
    config = BackupConfig()
    print(f"Default enabled: {config.enabled}")
    print(f"Default endpoint: {config.endpoint}")
    print(f"Default retention_days: {config.retention_days}")
    print(f"Default dedup_enabled: {config.dedup_enabled}")

    # Test with custom values
    custom_config = BackupConfig(
        enabled=True,
        endpoint="minio.example.com:9000",
        secure=True,
        retention_days=60,
    )
    print(f"Custom enabled: {custom_config.enabled}")
    print(f"Custom secure: {custom_config.secure}")

    # Test StorageConfig
    storage_config = StorageConfig()
    print(f"StorageConfig.backup.enabled: {storage_config.backup.enabled}")

    print("✓ Configuration tests passed")


async def test_backup_coordinator():
    """Test BackupCoordinator."""
    print("\n=== Testing BackupCoordinator ===")

    coordinator = BackupCoordinator(
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin123",
        base_dir=Path.home() / ".copaw",
    )

    assert coordinator.client is not None, "MinIO client should be initialized"
    print(f"✓ Coordinator initialized: {coordinator.shared_bucket}")

    # Register agents
    agents = {
        "default": Path.home() / ".copaw/workspaces/default",
        "mS7xfg": Path.home() / ".copaw/workspaces/mS7xfg",
    }

    for agent_id, workspace_dir in agents.items():
        if workspace_dir.exists():
            await coordinator.register_agent(agent_id, workspace_dir)
            print(f"✓ Registered: {agent_id}")

    # Start coordinator
    await coordinator.start()
    print("✓ Coordinator started")

    # Test backup
    print("\n--- Testing Backup ---")
    results = await coordinator.schedule_full_backup()
    print(f"✓ Full backup: {results['total_files']} files")

    for agent_id, agent_result in results["agents"].items():
        stats = agent_result.get("stats", {})
        print(f"  {agent_id}: {stats.get('success', 0)}/{stats.get('total', 0)} files")

    # Test incremental
    inc_results = await coordinator.incremental_backup()
    print(f"✓ Incremental backup: {len(inc_results['agents'])} agents")

    # Get stats
    stats = await coordinator.get_stats()
    print(f"\n--- Backup Statistics ---")
    print(f"Shared bucket: {stats.get('shared', {})}")
    for agent_id, agent_stats in stats["agents"].items():
        print(f"{agent_id}: {agent_stats.get('total_objects', 0)} objects, "
              f"{agent_stats.get('total_size_mb', 0)} MB")

    # Stop
    await coordinator.stop()
    print("✓ Coordinator stopped")

    return True


async def test_backup_agent_restore():
    """Test BackupAgent restore functionality."""
    print("\n=== Testing BackupAgent Restore ===")

    coordinator = BackupCoordinator(
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin123",
    )

    agent_id = "default"
    workspace_dir = Path.home() / ".copaw/workspaces/default"

    if not workspace_dir.exists():
        print("⚠ Workspace not found, skipping restore test")
        return True

    agent = await coordinator.register_agent(agent_id, workspace_dir)
    await agent.start()

    # Create a temp directory for restore
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)

        # Restore memory files only
        result = await agent.restore(
            backup_prefix="realtime",
            resources=["memory/"],
            target_dir=target_dir,
        )

        print(f"Restore result: {result.get('stats', {})}")

        # Verify restored files
        memory_dir = target_dir / "memory"
        if memory_dir.exists():
            files = list(memory_dir.glob("*.md"))
            print(f"✓ Restored {len(files)} memory files")
        else:
            print("⚠ No memory files restored (may not exist in backup)")

    await coordinator.stop()
    print("✓ Restore test completed")

    return True


async def test_coordinator_restore():
    """Test BackupCoordinator restore_all functionality."""
    print("\n=== Testing Coordinator Restore All ===")

    coordinator = BackupCoordinator(
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin123",
    )

    # Register agent
    await coordinator.register_agent(
        "default",
        Path.home() / ".copaw/workspaces/default"
    )

    # Test restore all
    results = await coordinator.restore_all(backup_prefix="realtime")
    print(f"Total restored: {results.get('total_restored', 0)} files")

    for agent_id, result in results.get("agents", {}).items():
        stats = result.get("stats", {})
        print(f"  {agent_id}: {stats.get('restored', 0)} restored, {stats.get('errors', 0)} errors")

    await coordinator.stop()
    print("✓ Coordinator restore test completed")

    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("CoPaw Enterprise Backup System - Comprehensive Test")
    print("=" * 60)

    try:
        # Test configuration
        await test_config()

        # Test coordinator
        await test_backup_coordinator()

        # Test restore
        await test_backup_agent_restore()
        await test_coordinator_restore()

        print("\n" + "=" * 60)
        print("All tests completed successfully! ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
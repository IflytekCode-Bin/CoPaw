## Summary

This PR adds an enterprise-grade backup system for CoPaw, enabling automatic backup of all agent workspaces to MinIO.

### Key Features

#### 1. BackupCoordinator (Process-level)
- Manages multiple BackupAgent instances
- Shared resources deduplication (skills/ directories)
- Backup scheduling coordination
- Cross-agent resource sharing via `copaw-shared` bucket

#### 2. BackupAgent (Agent-level)
- Realtime sync of critical files (P0: MEMORY.md, sessions/, agent.json)
- Change-triggered sync (P1: dialog/, chats.json)
- Restore functionality with selective resource recovery
- Checksum-based deduplication

#### 3. Storage Module
- **SQLiteMemoryManager**: Local fast queries with FTS5 full-text search
- **MinIOStorageManager**: Remote backup and large file storage
- **HybridStorageManager**: Combined approach
- **CJK-aware token estimation**: 1.5 tokens per CJK character (vs 0.25 naive)

#### 4. Configuration
```json
{
  "storage": {
    "backup": {
      "enabled": true,
      "endpoint": "minio.example.com:9000",
      "secure": true,
      "full_backup_schedule": "0 2 * * *",
      "incremental_interval": 3600,
      "retention_days": 30,
      "dedup_enabled": true
    }
  }
}
```

Environment variables for secrets:
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `BACKUP_ENABLED`

#### 5. Multi-Agent Integration
- Automatic agent registration in `MultiAgentManager`
- Backup lifecycle management (start/stop)
- Methods: `init_backup_coordinator()`, `start_backup()`, `trigger_backup()`, `get_backup_stats()`

### Architecture

```
BackupCoordinator (process-level)
├── copaw-shared bucket (shared resources)
├── BackupAgent (default) → copaw-default bucket
├── BackupAgent (dev)     → copaw-dev bucket
├── BackupAgent (ops)     → copaw-ops bucket
└── BackupAgent (test)    → copaw-test bucket
```

### Resource Priority

| Priority | Resources | Sync Strategy |
|----------|-----------|---------------|
| P0 | MEMORY.md, sessions/, agent.json | Realtime |
| P1 | dialog/, chats.json | Change-triggered |
| P2 | skills/, active_skills/ | Scheduled |
| P3 | exports/, media/ | Manual |

### Files Changed

**New Modules:**
- `src/copaw/app/backup/` - Backup system (Coordinator + Agent)
- `src/copaw/storage/` - Storage managers (SQLite + MinIO)

**Modified:**
- `src/copaw/app/multi_agent_manager.py` - Backup integration
- `src/copaw/config/config.py` - BackupConfig + StorageConfig

**Documentation:**
- `docs/enterprise-storage-integration.md` - Integration guide
- `docs/multi-agent-backup-design.md` - Architecture design
- `docs/storage-usage.md` - Usage guide

**Tests:**
- `tests/test_enterprise_backup.py` - Comprehensive tests
- `tests/test_multi_agent_backup.py` - Multi-agent tests
- `tests/test_storage.py` - Storage module tests

### Test Results

All tests passed:
- Backup configuration loading ✓
- BackupCoordinator initialization ✓
- Multi-agent registration ✓
- Full and incremental backup ✓
- Restore functionality ✓

### Usage

```python
# Enable backup in MultiAgentManager
manager = MultiAgentManager()
await manager.init_backup_coordinator()
await manager.start_backup()

# Trigger manual backup
results = await manager.trigger_backup(full=True)

# Get backup statistics
stats = await manager.get_backup_stats()
```

### Breaking Changes

None. This is a new feature with backward compatibility.

### Dependencies

- `minio` - MinIO Python SDK
- `watchfiles` - File watching (optional, for realtime sync)
- `croniter` - Cron scheduling (optional, for scheduled backup)
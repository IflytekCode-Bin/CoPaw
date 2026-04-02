# CoPaw Hybrid Storage Usage Guide

## Overview

CoPaw hybrid storage combines:
- **SQLite**: Fast local queries, FTS5 full-text search, relationship management
- **MinIO**: Remote backup, large file storage, cross-agent sharing

## Installation

```bash
pip install minio watchfiles
```

## Quick Start

### Basic Usage

```python
from copaw.storage import HybridStorageManager

# Initialize storage manager
storage = HybridStorageManager(
    working_dir="/path/to/workspace",
    agent_id="default",
    minio_enabled=True,
    minio_endpoint="localhost:9000",
    minio_access_key="minioadmin",
    minio_secret_key="minioadmin123",
)

# Create conversation
await storage.create_conversation(
    conversation_id="conv-001",
    session_id="session-001",
    channel="console",
    user_id="user-123",
    title="My Conversation",
)

# Ingest message
from agentscope.message import Msg

message = Msg(
    name="user",
    content="你好，这是一个测试消息",
    role="user",
)

token_count = await storage.ingest_message(
    message=message,
    conversation_id="conv-001",
)
print(f"Token count: {token_count}")  # Accurate CJK token counting

# Search messages
results = await storage.search(
    query="测试",
    conversation_id="conv-001",
    limit=10,
)
for msg in results:
    print(f"{msg['role']}: {msg['content']}")
```

### SQLite Only (No MinIO)

```python
from copaw.storage import SQLiteMemoryManager

# Use SQLite only
sqlite = SQLiteMemoryManager(
    working_dir="/path/to/workspace",
    agent_id="default",
)

# Insert message
token_count = sqlite.insert_message(
    message_id="msg-001",
    conversation_id="conv-001",
    role="user",
    content="Hello, world!",
)

# Full-text search
results = sqlite.search_messages("hello")

# Get token statistics
stats = sqlite.get_token_stats("conv-001")
print(f"Total tokens: {stats['total_tokens']}")
```

### MinIO Only

```python
from copaw.storage import MinIOStorageManager

# Initialize MinIO manager
minio = MinIOStorageManager(
    agent_id="default",
    endpoint="localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin123",
    working_dir=Path("/path/to/workspace"),
)

# Upload file
await minio.upload_file(
    local_path=Path("/path/to/file.pdf"),
    remote_path="files/document.pdf",
)

# Upload JSON
await minio.upload_json(
    remote_path="config/settings.json",
    data={"key": "value"},
)

# Download
await minio.download_file(
    remote_path="files/document.pdf",
    local_path=Path("/tmp/downloaded.pdf"),
)

# List objects
objects = await minio.list_objects(prefix="config/")
for obj in objects:
    print(f"{obj['name']}: {obj['size']} bytes")
```

## Features

### 1. CJK-Aware Token Counting

```python
from copaw.storage.sqlite_manager import estimate_tokens

# Accurate for Chinese
text = "你好世界，这是一段中文测试。"
tokens = estimate_tokens(text)
print(f"Estimated tokens: {tokens}")  # ~15 tokens

# vs. simple len/4 would give ~7 tokens (inaccurate)
```

### 2. FTS5 Full-Text Search

```python
# Search with FTS5 syntax
results = sqlite.search_messages('测试 AND 消息')

# Phrase search
results = sqlite.search_messages('"exact phrase"')

# Prefix search
results = sqlite.search_messages('test*')

# Time range search
from datetime import datetime, timedelta

results = sqlite.search_by_time_range(
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now(),
)
```

### 3. DAG-Based Summaries

```python
# Create leaf summary
sqlite.insert_summary(
    summary_id="summary-001",
    conversation_id="conv-001",
    kind="leaf",
    content="Discussion about project architecture",
    depth=0,
    source_messages=["msg-001", "msg-002", "msg-003"],
)

# Create condensed summary (higher depth)
sqlite.insert_summary(
    summary_id="summary-002",
    conversation_id="conv-001",
    kind="condensed",
    content="User asked about storage options. We decided on SQLite + MinIO.",
    depth=1,
    source_messages=["summary-001", "summary-002"],  # Can reference other summaries
    model="gpt-4",
)
```

### 4. Automatic Sync

```python
# Start background file watching
await storage.start()

# ... do work ...

# Stop when done
await storage.stop()
```

### 5. Backup & Restore

```python
# Create backup
backup_result = await storage.backup(full=True)
print(f"Backup created: {backup_result}")

# Restore from backup
success = await storage.restore(backup_date="2024-01-15")
```

### 6. Statistics

```python
stats = await storage.get_stats()
print(f"SQLite DB: {stats['sqlite']['db_size_mb']} MB")
print(f"Total tokens: {stats['sqlite']['token_stats']['total_tokens']}")
print(f"MinIO objects: {stats['minio']['total_objects']}")
print(f"MinIO size: {stats['minio']['total_size_mb']} MB")
```

## Sync Strategies

| Priority | Path | Strategy | Debounce |
|----------|------|----------|----------|
| P0 | config.json | Realtime | 100ms |
| P0 | MEMORY.md | Realtime | 500ms |
| P0 | memory/ | Realtime | 500ms |
| P0 | sessions/ | Realtime | 1000ms |
| P1 | dialog/ | Change-triggered | 5000ms |
| P1 | file_store/ | Change-triggered | 10000ms |
| P2 | skills/ | Scheduled | N/A |
| P2 | media/ | Scheduled | N/A |
| P3 | exports/ | Manual | N/A |
| P4 | logs/ | Local only | N/A |

## Integration with CoPaw

### In MemoryManager

```python
# copaw/memory/manager.py

from copaw.storage import HybridStorageManager

class MemoryManager:
    def __init__(self, working_dir: str, agent_id: str):
        self.storage = HybridStorageManager(
            working_dir=working_dir,
            agent_id=agent_id,
            minio_enabled=True,  # Configure via config
        )

    async def add_message(self, message: Msg, conversation_id: str):
        return await self.storage.ingest_message(message, conversation_id)

    async def search(self, query: str):
        return await self.storage.search(query)
```

### Configuration

```json
// config.json
{
  "storage": {
    "minio": {
      "enabled": true,
      "endpoint": "localhost:9000",
      "access_key": "minioadmin",
      "secret_key": "minioadmin123",
      "secure": false
    },
    "backup": {
      "schedule": "0 2 * * *",  // Daily at 2am
      "retention_days": 30
    }
  }
}
```

## MinIO Console

Access MinIO web console at http://localhost:9001

Login with:
- Username: `minioadmin`
- Password: `minioadmin123`

Buckets:
- `copaw-default` - Default agent
- `copaw-dev` - Dev agent
- `copaw-test` - Test agent
- `copaw-ops` - Ops agent
- `copaw-shared` - Cross-agent shared resources
- `copaw-backups` - Centralized backups

## Performance Tips

1. **Use SQLite for frequent queries** - It's local and fast
2. **Batch MinIO operations** - Reduce network overhead
3. **Use compression** - For large files and backups
4. **Clean up regularly** - Run `cleanup()` periodically
5. **Vacuum SQLite** - Run `sqlite.vacuum()` after large deletions

## Troubleshooting

### MinIO Connection Failed

```python
# Check if MinIO is running
docker ps | grep minio

# Start MinIO if needed
docker start copaw-minio

# Check connectivity
curl http://localhost:9000/minio/health/live
```

### SQLite Database Locked

```python
# Close connections properly
conn.close()

# Use WAL mode for better concurrency
conn.execute("PRAGMA journal_mode=WAL")
```

### Token Count Mismatch

The `estimate_tokens()` function is an approximation. For exact counts, use a tokenizer library like `tiktoken` or the model's actual tokenizer.
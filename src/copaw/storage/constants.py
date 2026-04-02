# -*- coding: utf-8 -*-
"""Storage constants and configuration."""

# Storage priority levels
STORAGE_PRIORITY = {
    "P0_REALTIME": 0,    # Immediate sync
    "P1_ON_CHANGE": 1,   # Sync on change (debounced)
    "P2_SCHEDULED": 2,   # Daily backup
    "P3_MANUAL": 3,      # User-triggered
    "P4_NO_SYNC": 4,     # Local only, no backup
}

# Sync strategies per path prefix
SYNC_STRATEGIES = {
    # P0: Realtime sync (immediate upload)
    "config/": {
        "priority": STORAGE_PRIORITY["P0_REALTIME"],
        "extensions": [".json"],
        "debounce_ms": 0,
    },
    "memory/": {
        "priority": STORAGE_PRIORITY["P0_REALTIME"],
        "extensions": [".md"],
        "debounce_ms": 0,
    },
    "sessions/": {
        "priority": STORAGE_PRIORITY["P0_REALTIME"],
        "extensions": [".json"],
        "debounce_ms": 0,
    },
    "dialog/": {
        "priority": STORAGE_PRIORITY["P0_REALTIME"],
        "extensions": [".jsonl"],
        "debounce_ms": 0,
    },

    # P1: On-change sync (debounced)
    "agent-definition/": {
        "priority": STORAGE_PRIORITY["P1_ON_CHANGE"],
        "extensions": [".md"],
        "debounce_ms": 5000,
    },
    "scripts/": {
        "priority": STORAGE_PRIORITY["P1_ON_CHANGE"],
        "extensions": [".py", ".sh"],
        "debounce_ms": 5000,
    },

    # P2: Scheduled backup
    "file-store/": {
        "priority": STORAGE_PRIORITY["P2_SCHEDULED"],
        "extensions": [".sqlite3", ".json", ""],
        "schedule": "0 3 * * *",  # Daily at 3 AM
    },
    "skills/": {
        "priority": STORAGE_PRIORITY["P2_SCHEDULED"],
        "extensions": [".json", ".md", ".tar.gz"],
        "schedule": "0 3 * * *",
    },
    "media/": {
        "priority": STORAGE_PRIORITY["P2_SCHEDULED"],
        "extensions": [".jpg", ".png", ".gif", ".mp3", ".mp4"],
        "schedule": "0 3 * * *",
    },

    # P3: Manual backup
    "embedding-cache/": {
        "priority": STORAGE_PRIORITY["P3_MANUAL"],
        "extensions": [".json"],
    },
}

# Local cleanup rules
CLEANUP_RULES = {
    # Log files: keep 7 days
    "logs/*.log": {
        "max_age_days": 7,
        "description": "Historical logs",
    },
    "copaw.log": {
        "max_size_mb": 50,
        "rotate": True,
        "keep_rotations": 5,
        "description": "Current log file",
    },

    # Tool results: cleanup after 1 hour
    "tool_result/*": {
        "max_age_hours": 1,
        "description": "Temporary tool outputs",
    },

    # Invalid compaction sessions: keep 3 days
    "sessions/compact_invalid_*.json": {
        "max_age_days": 3,
        "description": "Failed compaction sessions",
    },

    # Embedding cache: LRU eviction
    "embedding_cache/*": {
        "max_size_mb": 100,
        "lru_evict": True,
        "description": "Embedding cache with LRU",
    },
}

# MinIO bucket naming
MINIO_BUCKET_TEMPLATE = "copaw-{agent_id}"
MINIO_SHARED_BUCKET = "copaw-shared"
MINIO_BACKUP_BUCKET = "copaw-backups"

# SQLite database schema
SQLITE_SCHEMA = """
-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    session_id TEXT,
    channel TEXT,
    user_id TEXT,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    conversation_id TEXT,
    seq INTEGER,
    role TEXT,
    content TEXT,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
);

-- FTS5 full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content='messages',
    content_rowid='rowid',
    tokenize='unicode61'
);

-- Summaries table (DAG nodes)
CREATE TABLE IF NOT EXISTS summaries (
    summary_id TEXT PRIMARY KEY,
    conversation_id TEXT,
    kind TEXT CHECK(kind IN ('leaf', 'condensed')),
    depth INTEGER DEFAULT 0,
    content TEXT,
    token_count INTEGER,
    source_token_count INTEGER,
    model TEXT,
    earliest_at TIMESTAMP,
    latest_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
);

-- Summary edges table (DAG relationships)
CREATE TABLE IF NOT EXISTS summary_edges (
    edge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id TEXT,
    child_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES summaries(summary_id),
    FOREIGN KEY (child_id) REFERENCES summaries(summary_id),
    UNIQUE(parent_id, child_id)
);

-- Large files table
CREATE TABLE IF NOT EXISTS large_files (
    file_id TEXT PRIMARY KEY,
    conversation_id TEXT,
    message_id TEXT,
    filename TEXT,
    mime_type TEXT,
    byte_size INTEGER,
    storage_uri TEXT,
    exploration_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_summaries_conversation ON summaries(conversation_id);
CREATE INDEX IF NOT EXISTS idx_summaries_depth ON summaries(depth);
"""
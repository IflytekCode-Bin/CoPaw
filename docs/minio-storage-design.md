# CoPaw MinIO 存储方案设计

## 0. 工作区文件全景分析

### 当前工作区目录结构 (~/.copaw/)

```
~/.copaw/
├── 核心配置
│   ├── config.json              # Agent 主配置（模型、工具、MCP等）
│   ├── chats.json               # 聊天记录索引
│   ├── skill.json               # 技能配置
│   ├── token_usage.json         # Token 使用统计
│   └── copaw_file_metadata.json # 文件元数据
│
├── Agent 定义文件
│   ├── AGENTS.md                # Agent 行为规范
│   ├── SOUL.md                  # Agent 核心准则
│   ├── PROFILE.md               # 用户资料
│   ├── MEMORY.md                # 长期记忆
│   ├── BOOTSTRAP.md             # 启动引导
│   └── HEARTBEAT.md             # 心跳任务
│
├── 每日记录
│   ├── memory/                  # 每日笔记
│   │   └── YYYY-MM-DD.md
│   └── dialog/                  # 对话历史 JSONL
│   │   └── YYYY-MM-DD.jsonl
│
├── 技能系统
│   ├── skills/                  # 工作区技能（~17个）
│   ├── skill_pool/              # 技能池（4MB）
│   ├── active_skills/           # 激活的技能（已软链接）
│   └── customized_skills/       # 自定义技能
│
├── 会话数据
│   ├── sessions/                # 会话历史（3.3MB）
│   │   └── {session_id}.json
│   ├── file_store/              # 文件存储 + 向量索引（27MB）
│   │   └── {uuid}/
│   │       └── chroma.sqlite3   # Chroma 向量数据库
│   └── embedding_cache/         # 嵌入缓存
│
├── 媒体与临时文件
│   ├── media/                   # 媒体文件（3.3MB）
│   ├── tool_result/             # 工具执行结果（临时）
│   └── logs/                    # 日志（196KB，可清理）
│   │   └── {timestamp}.log
│   └── copaw.log                # 当前日志（11.8MB）
│
├── 脚本与扩展
│   ├── scripts/                 # 用户脚本
│   └── customized/              # 自定义配置
│
└── 运行时状态
    ├── .bootstrap_completed     # 启动标记
    ├── .telemetry_collected     # 遥测标记
    └── skill_scanner_blocked.json
```

### 文件大小分布

| 目录/文件 | 大小 | 存储优先级 | 说明 |
|-----------|------|------------|------|
| `file_store/` | 27MB | 高 | 包含向量索引，重建成本高 |
| `sessions/` | 3.3MB | 高 | 会话历史，核心数据 |
| `media/` | 3.3MB | 中 | 媒体文件，可重建 |
| `skill_pool/` | 4MB | 低 | 技能池，可从源码重建 |
| `copaw.log` | 11.8MB | 不存储 | 运行时日志，可清理 |
| `logs/` | 196KB | 不存储 | 历史日志，可清理 |
| `tool_result/` | 4KB | 不存储 | 临时结果，执行完可清理 |

### 存储策略分类

| 分类 | 文件类型 | 存储策略 | 原因 |
|------|----------|----------|------|
| **核心备份** | config.json, MEMORY.md, sessions/* | 实时同步 | 重建成本高，丢失影响大 |
| **定期备份** | file_store/, skill_pool/, media/ | 每日备份 | 体积大，可容忍延迟 |
| **配置备份** | AGENTS.md, SOUL.md, PROFILE.md | 变化时备份 | 修改频率低 |
| **不存储** | logs/, copaw.log, tool_result/ | 本地清理 | 临时文件，无备份价值 |

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CoPaw 混合存储架构                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    SQLite（本地高频查询）                      │  │
│  │                                                              │  │
│  │  ~/.copaw/memory.db                                          │  │
│  │  • conversations 表 - 会话元数据                              │  │
│  │  • messages 表 - 对话历史（支持 FTS5 全文搜索）               │  │
│  │  • summaries 表 - DAG 摘要节点                                │  │
│  │  • summary_edges 表 - DAG 边关系                              │  │
│  │                                                              │  │
│  │  特点：快速查询、关系 JOIN、聚合统计、零配置                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              ↑ 同步                                 │
│                              ↓                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    MinIO（远程大对象存储）                     │  │
│  │                                                              │  │
│  │  Bucket: copaw-{agent_id}                                    │  │
│  │  • conversations/{conv_id}/messages/{msg_id}.json             │  │
│  │  • conversations/{conv_id}/summaries/{sum_id}.json            │  │
│  │  • files/{file_id} - 大文件（图片、PDF、音频）                 │  │
│  │  • exports/{date}/backup.tar.gz - 定期备份                    │  │
│  │  • shared/{resource_id} - 跨 Agent 共享资源                   │  │
│  │                                                              │  │
│  │  特点：大对象、跨机器访问、高可用、S3 兼容                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    向量数据库（语义搜索）                      │  │
│  │                                                              │  │
│  │  Chroma / Qdrant / Milvus                                    │  │
│  │  • embedding vectors for messages                            │  │
│  │  • embedding vectors for summaries                           │  │
│  │                                                              │  │
│  │  或者使用 sqlite-vss 扩展                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. Bucket 设计

### 2.1 Bucket 命名规范

```
copaw-{agent_id}          # 每个 Agent 一个独立 Bucket
copaw-shared              # 跨 Agent 共享资源
copaw-backups             # 全局备份存储
```

### 2.2 对象路径设计（完整版）

```
copaw-default/
│
├── config/                           # 📁 核心配置（实时同步）
│   ├── agent.json                    # Agent 主配置
│   ├── chats.json                    # 聊天记录索引
│   ├── skill.json                    # 技能配置
│   ├── token_usage.json              # Token 使用统计
│   └── mcp.json                      # MCP 配置备份
│
├── agent-definition/                 # 📁 Agent 定义文件（变化时同步）
│   ├── AGENTS.md                     # Agent 行为规范
│   ├── SOUL.md                       # Agent 核心准则
│   ├── PROFILE.md                    # 用户资料
│   ├── MEMORY.md                     # 长期记忆
│   ├── BOOTSTRAP.md                  # 启动引导
│   └── HEARTBEAT.md                  # 心跳任务
│
├── memory/                           # 📁 记忆与日记（实时同步）
│   ├── MEMORY.md                     # 长期记忆文件
│   └── daily/
│       └── {YYYY-MM-DD}.md           # 每日笔记
│
├── dialog/                           # 📁 对话历史（实时同步）
│   └── {YYYY-MM-DD}.jsonl            # 对话 JSONL 记录
│
├── sessions/                         # 📁 会话数据（实时同步）
│   └── {session_id}.json             # 完整会话历史
│   └── matrix/
│       └── {matrix_session}.json     # Matrix 会话
│
├── conversations/                    # 📁 DAG 对话存储（压缩后）
│   └── {conversation_id}/
│       ├── meta.json                 # 会话元数据
│       ├── messages/
│       │   └── {msg_id}.json         # 单条消息
│       └── summaries/
│           ├── {sum_id}.json         # 摘要节点
│           └── edges.json            # DAG 边关系
│
├── file-store/                       # 📁 文件存储（定期备份）
│   ├── chroma.sqlite3.gz             # Chroma 向量索引（压缩）
│   └── {uuid}/                       # 文件目录
│       ├── data                      # 文件内容
│       └── meta.json                 # 文件元数据
│
├── skills/                           # 📁 技能系统（定期备份）
│   ├── active_skills.tar.gz          # 激活技能打包
│   ├── skill_pool/
│   │   └── skill.json                # 技能池配置
│   └── customized_skills/
│       └── {skill_name}/             # 自定义技能
│           └── SKILL.md
│
├── media/                            # 📁 媒体文件（定期备份）
│   └── {media_id}.{ext}              # 图片、音频等
│
├── scripts/                          # 📁 用户脚本（变化时备份）
│   └── {script_name}.py
│
├── embedding-cache/                  # 📁 嵌入缓存（可选备份）
│   └── {cache_key}.json
│
└── exports/                          # 📁 导出与备份
    └── {YYYY-MM-DD}/
        ├── workspace.tar.gz          # 完整工作区备份
        ├── sessions.tar.gz           # 会话备份
        └── chroma-backup.tar.gz      # 向量索引备份
```

### 2.3 存储优先级与同步策略

| 优先级 | 路径前缀 | 同步策略 | 触发条件 |
|--------|----------|----------|----------|
| **P0 实时** | config/, memory/, sessions/, dialog/ | 立即上传 | 文件变化 |
| **P1 变化** | agent-definition/, scripts/ | 延迟上传 | 文件修改后 5s |
| **P2 定期** | file-store/, skills/, media/ | 定时备份 | 每日 03:00 |
| **P3 可选** | embedding-cache/ | 手动备份 | 用户触发 |
| **P4 不存** | logs/, copaw.log, tool_result/ | 本地清理 | 不上传 |

### 2.4 文件清理策略

```python
# 本地文件清理规则
CLEANUP_RULES = {
    # 日志文件：保留 7 天
    "logs/*.log": {"max_age_days": 7},
    "copaw.log": {"max_size_mb": 50, "rotate": True},
    
    # 工具结果：执行完 1 小时后清理
    "tool_result/*": {"max_age_hours": 1},
    
    # 临时会话：已导出的清理
    "sessions/compact_invalid_*.json": {"max_age_days": 3},
    
    # 嵌入缓存：LRU 淘汰
    "embedding_cache/*": {"max_size_mb": 100},
}
```

## 3. 数据格式设计

### 3.1 会话元数据 (meta.json)

```json
{
  "conversation_id": "conv_abc123",
  "session_id": "sess_xyz789",
  "channel": "console",
  "user_id": "default",
  "title": "讨论 CoPaw 存储方案",
  "created_at": "2026-04-01T10:00:00+08:00",
  "updated_at": "2026-04-01T17:30:00+08:00",
  "message_count": 42,
  "total_tokens": 15420,
  "tags": ["minio", "storage", "design"]
}
```

### 3.2 消息格式 (messages/{msg_id}.json)

```json
{
  "message_id": "msg_001",
  "conversation_id": "conv_abc123",
  "seq": 1,
  "role": "user",
  "content": "帮我设计 CoPaw 的存储方案",
  "token_count": 15,
  "created_at": "2026-04-01T10:00:00+08:00",
  "parts": [
    {
      "type": "text",
      "content": "帮我设计 CoPaw 的存储方案"
    }
  ],
  "metadata": {
    "channel": "console",
    "user_id": "default"
  }
}
```

### 3.3 摘要格式 (summaries/{sum_id}.json)

```json
{
  "summary_id": "sum_leaf_001",
  "conversation_id": "conv_abc123",
  "kind": "leaf",
  "depth": 0,
  "content": "用户询问了 CoPaw 存储方案的设计...",
  "token_count": 120,
  "source_messages": ["msg_001", "msg_002", "msg_003"],
  "source_token_count": 450,
  "created_at": "2026-04-01T12:00:00+08:00",
  "earliest_at": "2026-04-01T10:00:00+08:00",
  "latest_at": "2026-04-01T11:30:00+08:00",
  "model": "gpt-4"
}
```

### 3.4 DAG 边关系 (summaries/edges.json)

```json
{
  "edges": [
    {
      "parent_id": "sum_condensed_001",
      "child_ids": ["sum_leaf_001", "sum_leaf_002", "sum_leaf_003"],
      "created_at": "2026-04-01T15:00:00+08:00"
    },
    {
      "parent_id": "sum_condensed_002",
      "child_ids": ["sum_leaf_004", "sum_leaf_005"],
      "created_at": "2026-04-01T16:00:00+08:00"
    }
  ]
}
```

### 3.5 大文件元数据 (files/{file_id}/meta.json)

```json
{
  "file_id": "file_abc123",
  "conversation_id": "conv_xyz",
  "message_id": "msg_042",
  "filename": "architecture-diagram.png",
  "mime_type": "image/png",
  "byte_size": 102400,
  "storage_uri": "files/file_abc123/data",
  "created_at": "2026-04-01T17:00:00+08:00",
  "exploration_summary": "架构图显示了三层存储结构..."
}
```

## 4. 同步策略

### 4.1 写入流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        消息写入流程                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Agent 收到消息                                               │
│     ↓                                                           │
│  2. SQLite 内存写入（立即）                                       │
│     • INSERT INTO messages ...                                  │
│     • 快速、可靠、支持事务                                        │
│     ↓                                                           │
│  3. MinIO 异步上传（后台任务）                                    │
│     • put_object(conversations/{conv_id}/messages/{msg_id}.json) │
│     • 不阻塞主流程                                               │
│     ↓                                                           │
│  4. 向量索引异步更新（可选）                                      │
│     • 计算 embedding → 存入向量库                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 压缩流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        DAG 压缩流程                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 检测上下文超阈值                                             │
│     ↓                                                           │
│  2. SQLite 查询待压缩消息                                        │
│     • SELECT messages WHERE ... ORDER BY seq                    │
│     ↓                                                           │
│  3. 调用 LLM 生成摘要                                            │
│     ↓                                                           │
│  4. SQLite 写入摘要节点                                          │
│     • INSERT INTO summaries ...                                 │
│     • INSERT INTO summary_edges ...                             │
│     ↓                                                           │
│  5. MinIO 上传摘要文件                                           │
│     • put_object(summaries/{sum_id}.json)                       │
│     • update_object(summaries/edges.json)                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 备份策略

```bash
# 每日备份脚本
#!/bin/bash
DATE=$(date +%Y-%m-%d)

# 1. SQLite 备份
gzip -c ~/.copaw/memory.db > /tmp/memory.db.gz

# 2. 上传到 MinIO
mc cp /tmp/memory.db.gz copaw-backups/daily/${DATE}/memory.db.gz

# 3. 对话导出
tar -czf /tmp/conversations.tar.gz ~/.copaw/conversations/
mc cp /tmp/conversations.tar.gz copaw-backups/daily/${DATE}/conversations.tar.gz
```

## 5. 搜索策略

### 5.1 本地搜索（SQLite FTS5）

```sql
-- 全文搜索
SELECT * FROM messages_fts 
WHERE messages_fts MATCH 'minio storage' 
ORDER BY rank LIMIT 10;

-- 时间范围搜索
SELECT * FROM messages 
WHERE created_at BETWEEN '2026-04-01' AND '2026-04-02'
AND conversation_id = 'conv_abc123';

-- Token 统计
SELECT SUM(token_count) FROM messages 
WHERE conversation_id = 'conv_abc123';
```

### 5.2 远程搜索（需要先同步到本地）

```python
# 从 MinIO 恢复历史数据到 SQLite
async def restore_conversation(conv_id: str):
    # 1. 下载消息列表
    objects = client.list_objects(bucket, f"conversations/{conv_id}/messages/")
    
    # 2. 批量导入 SQLite
    for obj in objects:
        data = client.get_object(bucket, obj.object_name)
        msg = json.loads(data.read())
        conn.execute("""
            INSERT OR REPLACE INTO messages 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (msg['message_id'], msg['conversation_id'], ...))
```

## 6. Python 实现

### 6.1 MinIO 存储管理器

```python
# copaw/storage/minio_manager.py

import json
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import io

from minio import Minio
from minio.error import S3Error


class MinIOStorageManager:
    """MinIO-based storage manager for CoPaw agents.
    
    Handles:
    - Conversation messages backup
    - Large file storage (images, PDFs)
    - Cross-agent resource sharing
    - Periodic backups
    """
    
    def __init__(
        self,
        endpoint: str = "localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin123",
        agent_id: str = "default",
        secure: bool = False,
    ):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self.agent_id = agent_id
        self.bucket = f"copaw-{agent_id}"
        self._ensure_bucket()
        
    def _ensure_bucket(self):
        """Create bucket if not exists."""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
            
    async def upload_message(
        self,
        conversation_id: str,
        message_id: str,
        message_data: Dict[str, Any],
    ) -> None:
        """Upload a single message to MinIO.
        
        Args:
            conversation_id: Conversation UUID
            message_id: Message UUID
            message_data: Message dict (role, content, tokens, etc.)
        """
        object_name = f"conversations/{conversation_id}/messages/{message_id}.json"
        data = json.dumps(message_data, ensure_ascii=False)
        
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            object_name,
            io.BytesIO(data.encode('utf-8')),
            len(data),
            content_type='application/json',
        )
        
    async def upload_summary(
        self,
        conversation_id: str,
        summary_id: str,
        summary_data: Dict[str, Any],
    ) -> None:
        """Upload a summary node to MinIO."""
        object_name = f"conversations/{conversation_id}/summaries/{summary_id}.json"
        data = json.dumps(summary_data, ensure_ascii=False)
        
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            object_name,
            io.BytesIO(data.encode('utf-8')),
            len(data),
            content_type='application/json',
        )
        
    async def upload_file(
        self,
        file_id: str,
        file_path: Path,
        metadata: Dict[str, Any],
    ) -> str:
        """Upload a large file (image, PDF, etc.) to MinIO.
        
        Args:
            file_id: Unique file identifier
            file_path: Local file path
            metadata: File metadata (filename, mime_type, size, etc.)
            
        Returns:
            Object URI: files/{file_id}/data
        """
        # Upload file content
        data_uri = f"files/{file_id}/data"
        await asyncio.to_thread(
            self.client.fput_object,
            self.bucket,
            data_uri,
            str(file_path),
            content_type=metadata.get('mime_type', 'application/octet-stream'),
        )
        
        # Upload metadata
        meta_uri = f"files/{file_id}/meta.json"
        meta_data = json.dumps(metadata, ensure_ascii=False)
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            meta_uri,
            io.BytesIO(meta_data.encode('utf-8')),
            len(meta_data),
            content_type='application/json',
        )
        
        return data_uri
        
    async def download_messages(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Download all messages for a conversation.
        
        Args:
            conversation_id: Conversation UUID
            limit: Max messages to download (None = all)
            
        Returns:
            List of message dicts
        """
        prefix = f"conversations/{conversation_id}/messages/"
        objects = await asyncio.to_thread(
            self.client.list_objects,
            self.bucket,
            prefix,
        )
        
        messages = []
        for obj in objects:
            if limit and len(messages) >= limit:
                break
            response = await asyncio.to_thread(
                self.client.get_object,
                self.bucket,
                obj.object_name,
            )
            data = response.read()
            messages.append(json.loads(data))
            
        # Sort by seq
        messages.sort(key=lambda m: m.get('seq', 0))
        return messages
        
    async def search_content(
        self,
        query: str,
        conversation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search messages by content (simple string match).
        
        Note: For full-text search, use SQLite FTS5 instead.
        This method is for remote/cross-agent search scenarios.
        
        Args:
            query: Search string
            conversation_id: Optional conversation filter
            
        Returns:
            List of matching messages
        """
        prefix = "conversations/"
        if conversation_id:
            prefix += f"{conversation_id}/messages/"
            
        objects = await asyncio.to_thread(
            self.client.list_objects,
            self.bucket,
            prefix,
            recursive=True,
        )
        
        results = []
        for obj in objects:
            if not obj.object_name.endswith('.json'):
                continue
            response = await asyncio.to_thread(
                self.client.get_object,
                self.bucket,
                obj.object_name,
            )
            data = response.read()
            msg = json.loads(data)
            if query.lower() in msg.get('content', '').lower():
                results.append(msg)
                
        return results
        
    async def backup_sqlite(
        self,
        db_path: Path,
        backup_date: str = None,
    ) -> None:
        """Backup SQLite database to MinIO.
        
        Args:
            db_path: Local SQLite file path
            backup_date: Date string (YYYY-MM-DD), defaults to today
        """
        if backup_date is None:
            backup_date = datetime.now().strftime('%Y-%m-%d')
            
        # Compress database
        import gzip
        with open(db_path, 'rb') as f:
            compressed = gzip.compress(f.read())
            
        object_name = f"exports/{backup_date}/memory.db.gz"
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            object_name,
            io.BytesIO(compressed),
            len(compressed),
            content_type='application/gzip',
        )
        
    async def restore_sqlite(
        self,
        backup_date: str,
        db_path: Path,
    ) -> None:
        """Restore SQLite database from MinIO backup.
        
        Args:
            backup_date: Date string (YYYY-MM-DD)
            db_path: Local path to restore to
        """
        object_name = f"exports/{backup_date}/memory.db.gz"
        response = await asyncio.to_thread(
            self.client.get_object,
            self.bucket,
            object_name,
        )
        
        import gzip
        compressed = response.read()
        data = gzip.decompress(compressed)
        
        with open(db_path, 'wb') as f:
            f.write(data)
```

### 6.2 配置集成

```python
# copaw/config/config.py 添加 MinIO 配置

MINIO_CONFIG = {
    "endpoint": os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    "access_key": os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    "secret_key": os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
    "secure": os.getenv("MINIO_SECURE", "false").lower() == "true",
    "bucket_prefix": "copaw-",
}
```

### 6.3 与 ReMeLightMemoryManager 集成

```python
# copaw/agents/memory/hybrid_memory_manager.py

class HybridMemoryManager(BaseMemoryManager):
    """Hybrid memory manager with SQLite + MinIO backends.
    
    SQLite: Local fast queries, FTS5, relationships
    MinIO: Remote backup, large files, cross-agent sharing
    """
    
    def __init__(self, working_dir: str, agent_id: str):
        super().__init__(working_dir=working_dir, agent_id=agent_id)
        
        # SQLite for local operations
        self.sqlite_manager = SQLiteMemoryManager(working_dir, agent_id)
        
        # MinIO for remote backup (optional)
        self.minio_manager = None
        if MINIO_ENABLED:
            self.minio_manager = MinIOStorageManager(agent_id=agent_id)
            
    async def ingest(self, msg: Msg):
        """Store message in both SQLite and MinIO."""
        # 1. SQLite (immediate, blocking)
        await self.sqlite_manager.ingest(msg)
        
        # 2. MinIO (async, non-blocking)
        if self.minio_manager:
            asyncio.create_task(
                self.minio_manager.upload_message(
                    self.current_conversation_id,
                    msg.id,
                    msg.to_dict(),
                )
            )
```

## 7. 环境变量配置

```bash
# .env or environment
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_SECURE=false
MINIO_ENABLED=true
```

## 8. Docker Compose 集成

```yaml
# docker-compose.yml
services:
  copaw:
    environment:
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=minioadmin
      - MINIO_SECRET_KEY=minioadmin123
      
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio-data:/data
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin123
      
volumes:
  minio-data:
```

## 9. 使用场景

### 场景 1: 本地快速查询
```python
# 使用 SQLite
recent_messages = sqlite_manager.get_recent_messages(limit=100)
token_count = sqlite_manager.get_total_tokens(conversation_id)
```

### 场景 2: 跨机器数据同步
```python
# 从 MinIO 恢复
messages = minio_manager.download_messages(conversation_id)
for msg in messages:
    sqlite_manager.insert_message(msg)
```

### 场景 3: 大文件处理
```python
# 存储用户上传的图片
file_uri = minio_manager.upload_file(
    file_id="img_001",
    file_path=Path("/tmp/uploaded_image.png"),
    metadata={"mime_type": "image/png", "size": 102400}
)
# SQLite 只存引用
sqlite_manager.insert_file_reference(msg_id, file_uri)
```

### 场景 4: 数据备份与恢复
```python
# 每日备份
await minio_manager.backup_sqlite(Path("~/.copaw/memory.db"))

# 恢复历史数据
await minio_manager.restore_sqlite("2026-04-01", Path("~/.copaw/memory.db"))
```

## 10. 总结

| 组件 | 用途 | 特点 |
|------|------|------|
| **SQLite** | 本地高频查询 | 快速、零配置、FTS5、关系查询 |
| **MinIO** | 远程大对象存储 | 大文件、跨机器、高可用、备份 |
| **向量库** | 语义搜索 | embedding 搜索、相似度匹配 |

**推荐策略**：
- 默认使用 SQLite 作为主存储
- MinIO 作为可选的备份/大文件存储
- 向量搜索根据需求选择（Chroma/Qdrant/sqlite-vss）
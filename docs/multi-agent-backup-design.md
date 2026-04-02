# CoPaw 多 Agent 备案架构设计

## 问题分析

### 当前遗漏

1. **单进程多智能体**: 一个 CoPaw 进程运行多个 Agent（MultiAgentManager）
2. **Agent 类型**: 
   - Manager Agent (default): 492MB，拥有最多技能
   - Worker Agents (dev/test/ops): 各 11MB
   - QA Agent: 2.9MB
3. **共享资源**: skills/ 目录内容可能相同，但存储位置不同
4. **备份协调**: 所有 Agent 同时备份会造成资源竞争

### 资源分类

| 资源类型 | Agent 独有 | 跨 Agent 共享 | 备注 |
|----------|-----------|---------------|------|
| sessions/ | ✅ | ❌ | 各 Agent 会话独立 |
| dialog/ | ✅ | ❌ | 各 Agent 对话独立 |
| memory/ | ✅ | ❌ | 各 Agent 记忆独立 |
| agent.json | ✅ | ❌ | 各 Agent 配置独立 |
| skills/ | ❓ | ❓ | 目录内容相同，但存储位置不同 |
| active_skills/ | ❓ | ❌ | default 300MB，其他 5MB |
| config.json | ❌ | ✅ | 进程级配置（~/.copaw/config.json） |

## 正确架构

```
┌─────────────────────────────────────────────────────┐
│              MultiAgentManager (进程级)             │
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │  BackupCoordinator (全局协调器)              │   │
│  │  ├─ 统一 MinIO 连接                          │   │
│  │  ├─ 共享资源管理 (copaw-shared bucket)       │   │
│  │  ├─ 备份调度 (避免同时全量备份)               │   │
│  │  ├─ 资源去重 (skills/ 只备份一次)            │   │
│  │  └─ 状态监控                                 │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
│  │  Workspace   │ │  Workspace   │ │  Workspace   ││
│  │  (default)   │ │  (dev)       │ │  (ops)       ││
│  │              │ │              │ │              ││
│  │ BackupAgent  │ │ BackupAgent  │ │ BackupAgent  ││
│  │ ├─ P0 实时   │ │ ├─ P0 实时   │ │ ├─ P0 实时   ││
│  │ ├─ P1 变化   │ │ ├─ P1 变化   │ │ ├─ P1 变化   ││
│  │ └─ 独有资源  │ │ └─ 独有资源  │ │ └─ 独有资源  ││
│  └──────────────┘ └──────────────┘ └──────────────┘│
│                                                      │
│  Buckets:                                            │
│  ├─ copaw-default    (default agent 独有)           │
│  ├─ copaw-dev        (dev agent 独有)               │
│  ├─ copaw-ops        (ops agent 独有)               │
│  ├─ copaw-test       (test agent 独有)              │
│  ├─ copaw-shared     (跨 Agent 共享资源)            │
│  └─ copaw-backups    (全局备份索引)                 │
└─────────────────────────────────────────────────────┘
```

## 实现方案

### 1. BackupCoordinator (进程级)

```python
class BackupCoordinator:
    """全局备份协调器，管理多 Agent 备份。"""
    
    def __init__(self, minio_config: dict):
        self.client = Minio(...)
        self.agent_managers: Dict[str, BackupAgent] = {}
        self.shared_bucket = "copaw-shared"
        self.backup_bucket = "copaw-backups"
        
    async def register_agent(self, agent_id: str, workspace_dir: Path):
        """注册 Agent 的备份管理器。"""
        self.agent_managers[agent_id] = BackupAgent(
            agent_id, workspace_dir, self.client
        )
        
    async def sync_shared_resources(self):
        """同步共享资源（进程级 config.json, 共享 skills）。"""
        # 进程级配置
        config_path = Path.home() / ".copaw" / "config.json"
        await self._upload_to_shared(config_path, "config/process_config.json")
        
        # 技能去重：选择一个 agent 的 skills 作为共享版本
        # 或检测内容相同的 skills 只上传一次
        
    async def schedule_backup(self):
        """调度备份，避免同时全量备份。"""
        # Manager 先备份
        await self.agent_managers["default"].full_backup()
        
        # Workers 并行增量备份
        await asyncio.gather(
            self.agent_managers["mS7xfg"].incremental_backup(),
            self.agent_managers["HtgnSz"].incremental_backup(),
            self.agent_managers["cwcQko"].incremental_backup(),
        )
```

### 2. BackupAgent (Agent 级)

```python
class BackupAgent:
    """单个 Agent 的备份管理器。"""
    
    # 独有资源
    UNIQUE_RESOURCES = [
        "sessions/", "dialog/", "memory/", 
        "agent.json", "chats.json"
    ]
    
    # 可能共享的资源（不在此处备份）
    SHARED_RESOURCES = [
        "skills/",  # 由 BackupCoordinator 处理
    ]
    
    async def sync_unique_resources(self):
        """只同步 Agent 独有资源。"""
        for resource in self.UNIQUE_RESOURCES:
            await self.sync(resource)
```

### 3. 资源去重策略

```python
async def deduplicate_skills(self):
    """检测各 Agent 的 skills 目录，只上传一次。"""
    
    # 比较各 Agent 的 skills 内容
    skills_hashes = {}
    for agent_id, workspace_dir in self.workspaces.items():
        skills_dir = workspace_dir / "skills"
        hash = await self._calculate_dir_hash(skills_dir)
        skills_hashes[agent_id] = hash
    
    # 如果 hash 相同，只上传一次到 shared bucket
    unique_hashes = set(skills_hashes.values())
    for hash in unique_hashes:
        # 选择第一个有此 hash 的 agent
        first_agent = next(a for a, h in skills_hashes.items() if h == hash)
        await self._upload_skills_to_shared(first_agent)
        
        # 其他 agent 记录引用
        for agent_id, h in skills_hashes.items():
            if h == hash and agent_id != first_agent:
                await self._record_skill_reference(agent_id, hash)
```

### 4. 备份优先级

```
P0 实时同步 (所有 Agent):
├─ config.json (进程级 → copaw-shared)
├─ sessions/  (各 Agent → 各 Agent bucket)
├─ memory/    (各 Agent → 各 Agent bucket)
└─ agent.json (各 Agent → 各 Agent bucket)

P1 变化触发 (所有 Agent):
├─ dialog/    (各 Agent → 各 Agent bucket)

P2 定时备份 (协调执行):
├─ Manager Agent 全量备份 (优先)
├─ Worker Agents 并行增量备份
└─ skills/ 去重备份 (→ copaw-shared)

P3 手动触发:
├─ 全进程备份快照
└─ 导出包
```

## 集成到 MultiAgentManager

```python
class MultiAgentManager:
    def __init__(self):
        self.agents: Dict[str, Workspace] = {}
        self.backup_coordinator: Optional[BackupCoordinator] = None
        
    async def start_backup(self, minio_config: dict):
        """启动全局备份协调器。"""
        self.backup_coordinator = BackupCoordinator(minio_config)
        
        # 注册所有 agent
        for agent_id, workspace in self.agents.items():
            await self.backup_coordinator.register_agent(
                agent_id, workspace.workspace_dir
            )
            
        # 启动后台同步
        await self.backup_coordinator.start()
```

## 配置设计

```json
{
  "storage": {
    "backup": {
      "enabled": true,
      "endpoint": "${MINIO_ENDPOINT}",
      "access_key": "${MINIO_ACCESS_KEY}",
      "secret_key": "${MINIO_SECRET_KEY}",
      
      "buckets": {
        "agent_template": "copaw-{agent_id}",
        "shared": "copaw-shared",
        "backups": "copaw-backups"
      },
      
      "schedule": {
        "full_backup": "0 2 * * *",
        "incremental_interval": 3600,
        "retention_days": 30
      },
      
      "deduplication": {
        "enabled": true,
        "resources": ["skills/", "active_skills/"]
      }
    }
  }
}
```

## 存储容量估算

**优化后存储：**
```
copaw-shared:      ~15MB (共享 skills + config)
copaw-default:     ~200MB (去除共享后的独有资源)
copaw-dev:         ~10MB (独有资源)
copaw-ops:         ~10MB (独有资源)
copaw-test:        ~10MB (独有资源)
copaw-backups:     ~50MB (备份索引和快照)
─────────────────────────────
总计: ~285MB (vs 原来可能 527MB * N)
```

## 待实现

1. BackupCoordinator 类
2. 资源去重逻辑
3. 备份调度策略
4. 集成到 MultiAgentManager
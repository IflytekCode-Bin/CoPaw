# CoPaw 企业级存储集成方案

## 状态分析

### 当前架构
- **ReMeLight** (reme-ai 0.3.1.6) 是核心记忆管理器
- **纯文件存储**：JSONL 对话、Chroma 向量库、本地文件
- **无远程备份**：所有数据只存在于本地磁盘
- **Agent 独立存储**：每个 agent 有独立工作区，无法共享

### 数据资产清单 (default agent)
```
总计: 527MB
├── active_skills/    300MB  — 技能代码（重要）
├── browser/          166MB  — 浏览器缓存（可清理）
├── file_store/       9.2MB  — 向量数据库（重要）
├── sessions/         4.5MB  — 会话状态（重要）
├── dialog/           4.3MB  — 对话历史（重要）
├── skills/           4.3MB  — 技能源码（重要）
├── tool_result/      1.8MB  — 工具结果（可清理）
├── logs/             288KB  — 日志（可清理）
├── memory/           92KB   — 记忆索引（重要）
├── agent.json        13KB   — Agent 配置（非常重要）
├── config.json       — 主配置（非常重要）
└── MEMORY.md         — 长期记忆（非常重要）
```

## 企业级需求

### 1. 数据可靠性
- ✅ 定期自动备份
- ✅ 多副本存储
- ✅ 数据校验（checksum）
- ✅ 版本控制

### 2. 灾难恢复
- ✅ 快速恢复能力
- ✅ 增量备份
- ✅ 时间点恢复
- ✅ 跨机房备份

### 3. 跨 Agent 协作
- ✅ 共享资源池
- ✅ 技能共享
- ✅ 知识库共享
- ✅ 配置模板共享

### 4. 性能优化
- ✅ 本地快速查询（SQLite）
- ✅ 远程大文件存储（MinIO）
- ✅ 搜索加速（FTS5）
- ✅ 去重存储

## 集成方案

### 方案 A：在 ReMeLight 之上添加备份层（推荐）

```
┌─────────────────────────────────────────────────────┐
│                    CoPaw Agent                       │
├─────────────────────────────────────────────────────┤
│  ReMeLight Memory Manager (核心，不动)              │
│  ├─ 本地文件存储 (dialog/, memory/, sessions/)      │
│  ├─ Chroma 向量库 (file_store/)                     │
│  └─ FTS5 全文搜索                                   │
├─────────────────────────────────────────────────────┤
│  MinIO Backup Manager (新增，备份层)                │
│  ├─ 实时同步 (config, MEMORY.md, sessions/)        │
│  ├─ 定时备份 (dialog/, file_store/, skills/)       │
│  ├─ 文件监控 (watchfiles)                           │
│  └─ 增量同步 (checksum + diff)                      │
├─────────────────────────────────────────────────────┤
│  SQLite Index (新增，索引层)                        │
│  ├─ Token 统计                                      │
│  ├─ DAG 摘要                                        │
│  └─ 快速查询                                        │
└─────────────────────────────────────────────────────┘
```

**优点**：
- 不破坏现有 ReMeLight 功能
- 渐进式集成，风险低
- 可以逐步启用功能

**实现步骤**：

1. **第一步：创建 BackupManager**（本周）
   - 在 `workspace.py` 添加 `backup_manager` 服务
   - 实现文件监控和实时同步
   - 配置项支持

2. **第二步：集成到启动流程**（本周）
   - Workspace 启动时初始化 BackupManager
   - 配置 MinIO 连接参数
   - 测试备份恢复

3. **第三步：定时任务**（下周）
   - 添加每日全量备份 cron
   - 添加增量备份机制
   - 添加清理过期备份

### 方案 B：替换 ReMeLight 存储层（风险高）

直接修改 ReMeLight 使用 MinIO 作为底层存储。

**风险**：
- ReMeLight 是外部包，修改困难
- 可能破坏现有功能
- 升级维护困难

**不推荐**。

### 方案 C：双写模式（过渡方案）

同时写入本地和 MinIO，本地优先读取。

**优点**：
- 最小改动
- 可以逐步迁移

**缺点**：
- 写入延迟增加
- 一致性维护复杂

## 配置设计

### config.json 新增配置项

```json
{
  "storage": {
    "backup": {
      "enabled": true,
      "provider": "minio",
      "endpoint": "minio.example.com:9000",
      "access_key": "${MINIO_ACCESS_KEY}",
      "secret_key": "${MINIO_SECRET_KEY}",
      "secure": true,
      "bucket_template": "copaw-{agent_id}",
      "sync_interval": 60,
      "backup_schedule": "0 2 * * *",
      "retention_days": 30
    },
    "priority": {
      "P0_realtime": ["config.json", "MEMORY.md", "memory/", "sessions/"],
      "P1_change": ["dialog/", "file_store/"],
      "P2_schedule": ["skills/", "active_skills/"],
      "P3_manual": ["exports/", "media/"],
      "P4_local_only": ["logs/", "tool_result/", "browser/"]
    }
  }
}
```

### 环境变量支持

```bash
# MinIO 配置（敏感信息用环境变量）
MINIO_ENDPOINT=minio.example.com:9000
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
MINIO_SECURE=true

# 备份策略
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 2 * * *"
BACKUP_RETENTION_DAYS=30
```

## 实现计划

### 第一阶段：核心备份（本周）

1. 创建 `BackupManager` 类
   - 路径：`/Data/CodeBase/iflycode/CoPaw/src/copaw/app/backup/`
   - 功能：文件监控、MinIO 同步、校验

2. 集成到 Workspace
   - 修改 `workspace.py` 添加 backup 服务
   - 配置加载

3. 测试验证
   - 本地测试
   - 多 Agent 测试
   - 恢复测试

### 第二阶段：增强功能（下周）

1. 定时备份任务
   - 全量备份
   - 增量备份
   - 过期清理

2. SQLite 索引
   - Token 统计
   - DAG 摘要
   - 快速搜索

3. 跨 Agent 共享
   - 共享 bucket
   - 技能共享
   - 配置模板

### 第三阶段：企业级特性（下周）

1. 数据校验
   - SHA256 checksum
   - 版本控制
   - 一致性检查

2. 灾难恢复
   - 时间点恢复
   - 跨机房备份
   - 自动恢复

3. 监控告警
   - 同步状态
   - 存储容量
   - 备份完整性

## 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| MinIO 不可用 | 中 | 自动降级到本地存储 |
| 同步延迟 | 低 | 异步同步，不影响主流程 |
| 数据一致性 | 低 | checksum 校验，增量同步 |
| 存储容量 | 低 | 定期清理，压缩存储 |
| 网络带宽 | 低 | 增量同步，压缩传输 |

## 建议

**立即行动**：
1. 验证现有 MinIO 实例正常运行
2. 创建 BackupManager 基础框架
3. 测试核心文件备份

**后续优化**：
1. 根据实际负载调整同步策略
2. 添加监控告警
3. 实现跨机房备份
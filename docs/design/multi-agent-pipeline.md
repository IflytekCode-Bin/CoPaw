# CoPaw 多 Agent Pipeline 设计方案

## 1. 概述

本设计方案旨在为 CoPaw 增加多 Agent 协作的 Pipeline 能力，参考 AgentScope 的设计理念，提供：

- **Pipeline 编排**：Sequential、Fanout、Conditional、Loop 等多种编排模式
- **MsgHub 消息广播**：多 Agent 间自动消息分发和订阅
- **状态管理**：Pipeline 执行状态追踪、持久化和恢复
- **Hook 机制**：Pipeline 级别的生命周期钩子

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    CoPaw Multi-Agent System                  │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Pipeline Orchestration Layer             │  │
│  │  - SequentialPipeline                                 │  │
│  │  - FanoutPipeline                                     │  │
│  │  - ConditionalPipeline                                │  │
│  │  - LoopPipeline                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↕                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              MsgHub Communication Layer               │  │
│  │  - Message Broadcasting                               │  │
│  │  - Agent Subscription                                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↕                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              State Management Layer                   │  │
│  │  - Pipeline State Tracking                            │  │
│  │  - Checkpoint & Resume                                │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↕                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  Hook System Layer                    │  │
│  │  - pre_pipeline / post_pipeline                       │  │
│  │  - pre_agent_call / post_agent_call                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### 2.2.1 Pipeline 基类

位置：`src/copaw/pipeline/base.py`

核心功能：
- 定义 Pipeline 的基本接口
- 管理 Agent 列表
- Hook 注册和执行
- 状态管理集成

# CoPaw Multi-Agent Pipeline

多 Agent 协作的 Pipeline 编排系统，基于 AgentScope 设计理念。

## 功能特性

### 1. Pipeline 类型

- **SequentialPipeline**: 顺序执行，Agent 依次处理
- **FanoutPipeline**: 并行广播，多个 Agent 同时处理
- **ConditionalPipeline**: 条件分支，根据条件选择执行路径
- **LoopPipeline**: 循环执行，迭代优化直到满足条件

### 2. MsgHub 消息广播

- 自动消息分发和订阅
- 消息过滤（per-agent）
- 优先级队列
- 消息历史追踪

### 3. 状态管理

- 检查点保存（每步自动保存）
- 失败恢复（从检查点恢复）
- 执行历史查询
- SQLite / JSON 存储

### 4. Hook 系统

- `pre_pipeline` / `post_pipeline`
- `pre_agent_call` / `post_agent_call`
- `on_error` / `on_timeout`
- `on_state_change`

## 快速开始

### Sequential Pipeline

```python
from copaw.pipeline import SequentialPipeline
from agentscope.message import Msg

pipeline = SequentialPipeline(
    name="report_gen",
    agents=[analyst, writer, reviewer],
)

result = await pipeline.execute(
    msg=Msg("user", "Analyze Q4 sales", "user")
)
```

### Fanout Pipeline

```python
from copaw.pipeline import FanoutPipeline

pipeline = FanoutPipeline(
    name="code_review",
    agents=[security_expert, perf_expert, style_expert],
    enable_gather=True,  # 并行执行
)

results = await pipeline.execute(msg=code_msg)
```

### Conditional Pipeline

```python
from copaw.pipeline import ConditionalPipeline, SequentialPipeline

def is_complex(msg):
    return len(str(msg.content)) > 500

pipeline = ConditionalPipeline(
    name="task_router",
    condition=is_complex,
    true_branch=SequentialPipeline("complex", [planner, exec, val]),
    false_branch=SequentialPipeline("simple", [simple_agent]),
)

result = await pipeline.execute(msg=user_msg)
```

### Loop Pipeline

```python
from copaw.pipeline import LoopPipeline

def should_stop(msg, iteration):
    return iteration >= 3 or "APPROVED" in str(msg.content)

pipeline = LoopPipeline(
    name="refine",
    agents=[drafter, critic],
    exit_condition=should_stop,
    max_iterations=5,
)

result = await pipeline.execute(msg=task_msg)
```

### MsgHub 使用

```python
from copaw.pipeline import CoPawMsgHub
from agentscope.message import Msg

# 基础用法
async with CoPawMsgHub(
    participants=[alice, bob, charlie],
    announcement=Msg("system", "Welcome!", "system"),
) as hub:
    await alice()
    await bob()
    await charlie()

# 带过滤器
def only_code_msgs(msg, agent):
    return "```" in str(msg.content)

async with CoPawMsgHub(
    participants=[alice, bob],
    message_filter=only_code_msgs,
) as hub:
    await alice()
```

### 使用 Hooks

```python
async def log_agent_call(pipeline, agent, step, msg, **kwargs):
    print(f"[{pipeline.name}] Step {step}: {agent.agent_id}")

async def handle_error(pipeline, agent, error, **kwargs):
    print(f"Error in {agent.agent_id}: {error}")

pipeline = SequentialPipeline(
    name="my_pipeline",
    agents=[agent1, agent2, agent3],
)

pipeline.register_hook("pre_agent_call", log_agent_call)
pipeline.register_hook("on_error", handle_error)

result = await pipeline.execute(msg=user_msg)
```

### 状态管理

```python
from copaw.pipeline import StateManager

# 创建 state manager
sm = StateManager(storage_type="sqlite")

pipeline = SequentialPipeline(
    name="long_task",
    agents=[agent1, agent2, agent3],
    state_manager=sm,
)

# 执行（自动保存检查点）
try:
    result = await pipeline.execute(msg=user_msg)
except Exception as e:
    # 从检查点恢复
    checkpoint = await sm.load_checkpoint(pipeline.pipeline_id)
    print(f"Last successful step: {checkpoint['step']}")

# 查看历史
history = await sm.get_pipeline_history(pipeline.pipeline_id)
for step in history:
    print(f"Step {step['step']}: {step['agent_id']}")
```

## 架构设计

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

## 文件结构

```
src/copaw/pipeline/
├── __init__.py           # 模块导出
├── base.py               # Pipeline 基类
├── sequential.py         # 顺序 Pipeline
├── fanout.py             # 扇出 Pipeline
├── conditional.py        # 条件 Pipeline
├── loop.py               # 循环 Pipeline
├── msghub.py             # 增强的 MsgHub
└── state_manager.py      # 状态管理器

docs/design/
└── multi-agent-pipeline.md  # 详细设计文档

examples/
└── pipeline_sequential.py   # 示例代码
```

## 与现有功能集成

### 与 multi_agent_collaboration skill 集成

现有的 `multi_agent_collaboration` skill 提供了基于 CLI 的 agent 间通信，
而 Pipeline 系统提供了编程式的 agent 编排。两者可以结合使用：

```python
# 在 Pipeline 中调用其他 agent
from copaw.pipeline import SequentialPipeline

async def call_remote_agent(pipeline, agent, step, msg, **kwargs):
    """Hook: 调用远程 agent"""
    # 使用 copaw agents chat 命令
    import subprocess
    result = subprocess.run([
        "copaw", "agents", "chat",
        "--from-agent", agent.agent_id,
        "--to-agent", "remote_agent",
        "--text", str(msg.content),
    ], capture_output=True, text=True)
    # 处理结果...

pipeline = SequentialPipeline(
    name="hybrid",
    agents=[local_agent1, local_agent2],
)
pipeline.register_hook("post_agent_call", call_remote_agent)
```

## 开发计划

- [x] Phase 1: 基础 Pipeline（SequentialPipeline, FanoutPipeline）
- [x] Phase 2: 高级 Pipeline（ConditionalPipeline, LoopPipeline）
- [x] Phase 3: MsgHub 增强
- [x] Phase 4: State Management
- [ ] Phase 5: CLI 命令集成
- [ ] Phase 6: 测试和文档

## 参考资料

- [AgentScope Pipeline 文档](https://doc.agentscope.io/tutorial/task_pipeline.html)
- [AgentScope MsgHub 文档](https://doc.agentscope.io/tutorial/workflow_conversation.html)
- [CoPaw 架构文档](../src/copaw/agents/react_agent.py)

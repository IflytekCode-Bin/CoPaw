# Pipeline Canvas Editor Design

## 1. Overview

Replace the current form-based `PipelineManagementDrawer` CRUD with a visual drag-and-drop canvas editor for building Agent Pipelines. Users can drag nodes onto a ReactFlow canvas, connect them, and configure parameters through a side panel.

## 2. Technical Stack

| Layer | Technology | Reason |
|-------|-----------|--------|
| Canvas Engine | `@xyflow/react` (v12) | Industry standard, Dify uses v11, we use v12 |
| Auto Layout | `dagre` | Graph layout for auto-arranging nodes |
| UI Components | Ant Design (existing) | Consistent with CoPaw console |

## 3. Node Types

| Type | Description | Handles | Config |
|------|-------------|---------|--------|
| **Start** | Pipeline entry point | 1 output | - |
| **End** | Pipeline exit point | 1 input | - |
| **Agent** | Single agent execution | 1 in, 1 out | agent_id |
| **Parallel** | Fork execution into parallel branches | 1 in, N out | branch configs |
| **Branch** | Conditional routing | 1 in, N out (labeled) | conditions |
| **Loop** | Container for iterative sub-graph | 1 in, 1 out | max_iterations, exit_condition |
| **Sub-Pipeline** | Reference to another pipeline | 1 in, 1 out | sub_pipeline_id |

## 4. Data Structure

```typescript
interface PipelineCanvasData {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
  viewport: { x: number; y: number; zoom: number };
}

interface CanvasNode {
  id: string;           // uuid
  type: NodeType;       // 'start' | 'end' | 'agent' | 'parallel' | 'branch' | 'loop' | 'sub_pipeline'
  position: { x: number; y: number };
  data: {
    label: string;
    agent_id?: string;
    condition?: string;
    max_iterations?: number;
    sub_pipeline_id?: string;
    children?: string[];  // node IDs inside container
  };
}

interface CanvasEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;  // for branch/parallel multi-outputs
  label?: string;         // condition label for branch edges
}
```

## 5. Backend Mapping

The canvas data is serialized into the existing Pipeline JSON:
- `nodes` → `pipeline.nodes[]` with type, config, position
- `edges` → `pipeline.edges[]` with source/target/label
- Existing fields (`owner_agent_id`, `description`, `sub_pipelines`) preserved
- Backward compatible: if `nodes` is empty, fall back to legacy `agents[]` array

## 6. Component Architecture

```
PipelineCanvasEditor/
├── index.tsx                    # Main container (Drawer replacement)
├── NodePalette.tsx              # Left sidebar: draggable node types
├── Canvas/
│   ├── index.tsx                # ReactFlow wrapper
│   ├── nodes/
│   │   ├── AgentNode.tsx
│   │   ├── ParallelNode.tsx
│   │   ├── BranchNode.tsx
│   │   ├── LoopNode.tsx
│   │   ├── SubPipelineNode.tsx
│   │   └── StartEndNode.tsx
│   └── edges/
│       └── ConditionEdge.tsx
├── ConfigPanel/
│   ├── index.tsx                # Right side config drawer
│   ├── AgentConfig.tsx
│   ├── BranchConfig.tsx
│   ├── LoopConfig.tsx
│   └── SubPipelineConfig.tsx
└── Toolbar.tsx                  # Top bar: save, run, zoom, fit-view
```

## 7. Key Interactions

- **Add Node**: Drag from left palette onto canvas, or double-click to add
- **Connect**: Drag from output handle to input handle
- **Delete**: Select node/edge + Delete key, or right-click context menu
- **Configure**: Click node → open right config panel (Ant Design Form)
- **Save**: Serialize canvas → POST to existing pipeline API
- **Auto Layout**: Button to run dagre auto-arrange
- **Container Nodes**: Loop/Parallel render as resizable containers with inner canvas

## 8. Implementation Phases

### Phase 1: Foundation
- Install `@xyflow/react`, `dagre`
- Basic ReactFlow canvas with Start + End nodes
- Node palette with drag-to-add
- Basic edge creation

### Phase 2: Configuration & Persistence
- Right-side config panel per node type
- Serialize canvas data to Pipeline JSON
- Load existing pipeline into canvas
- Save/update via existing API

### Phase 3: Advanced Features
- Branch node with multiple labeled outputs
- Loop container with inner canvas
- Sub-pipeline reference node
- Auto-layout (dagre)
- Condition edge labels

## 9. Constraints

- All config forms must use Ant Design components (Form, Input, Select, etc.)
- Maintain backward compatibility with legacy `agents[]` pipeline format
- No changes to AgentScope底层框架
- Canvas editor replaces the old form modal in `PipelineManagementDrawer`

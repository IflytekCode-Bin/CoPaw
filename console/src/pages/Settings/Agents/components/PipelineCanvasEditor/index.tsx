/**
 * Pipeline Canvas Editor - main visual editor component.
 * Replaces the form-based PipelineManagementDrawer CRUD.
 *
 * Phase 1: Foundation - basic ReactFlow canvas with drag-to-add, edges, and node rendering.
 */

import { memo, useState, useCallback, useRef, useEffect } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  addEdge,
  useNodesState,
  useEdgesState,
  type OnConnect,
  type OnNodesDelete,
  type OnEdgesDelete,
  MarkerType,
  Panel,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Drawer, Button, message, Space } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { Pipeline, AgentSummary } from '../../../../api/types/agents';
import type { Pipeline as PipelineType } from '../../../../api/modules/pipeline';
import { pipelineApi } from '../../../../api/modules/pipeline';
import type { CanvasNodeType, CanvasNodeData } from './types';
import { NodePalette } from './NodePalette';
import { Toolbar } from './Toolbar';
import { ConfigPanel } from './ConfigPanel';
import { StartNodeComponent } from './nodes/StartEndNode';
import { AgentNodeComponent } from './nodes/AgentNode';
import { BranchNodeComponent } from './nodes/BranchNode';
import { LoopNodeComponent, ParallelNodeComponent } from './nodes/ContainerNodes';
import { SubPipelineNodeComponent } from './nodes/SubPipelineNode';
import { ConditionEdgeComponent } from './edges/ConditionEdge';
import styles from './index.module.less';

// ── Custom node type map ───────────────────────────────────────────

const nodeTypes = {
  start: StartNodeComponent,
  end: StartNodeComponent, // reuse styling, different handle
  agent: AgentNodeComponent,
  branch: BranchNodeComponent,
  loop: LoopNodeComponent,
  parallel: ParallelNodeComponent,
  sub_pipeline: SubPipelineNodeComponent,
};

const edgeTypes = {
  condition: ConditionEdgeComponent,
};

// ── Helper: generate unique ID ─────────────────────────────────────

let nodeIdCounter = 0;
const generateId = () => `node_${Date.now()}_${++nodeIdCounter}`;

// ── Default nodes for a new pipeline ───────────────────────────────

const defaultNodes = [
  {
    id: 'start',
    type: 'start',
    position: { x: 250, y: 50 },
    data: { label: '开始' },
  },
  {
    id: 'end',
    type: 'end',
    position: { x: 250, y: 400 },
    data: { label: '结束' },
  },
];

// ── Main Editor Component ──────────────────────────────────────────

interface PipelineCanvasEditorProps {
  open: boolean;
  pipeline: PipelineType | null;
  allAgents: AgentSummary[];
  allPipelines: PipelineType[];
  onClose: () => void;
  onSaveSuccess: () => void;
}

function PipelineCanvasEditorInner({
  open,
  pipeline,
  allAgents,
  allPipelines,
  onClose,
  onSaveSuccess,
}: PipelineCanvasEditorProps) {
  const { t } = useTranslation();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState(defaultNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [showPalette, setShowPalette] = useState(true);
  const [showConfig, setShowConfig] = useState(false);
  const [saving, setSaving] = useState(false);

  const { fitView, screenToFlowPosition } = useReactFlow();

  // ── Load pipeline data into canvas ─────────────────────────────

  useEffect(() => {
    if (pipeline && open) {
      const config = pipeline.config as any;
      if (config?.canvasData?.nodes) {
        setNodes(config.canvasData.nodes);
        setEdges(config.canvasData.edges || []);
      } else {
        // Fallback: create nodes from legacy agents[] array
        const fallbackNodes = [
          {
            id: 'start',
            type: 'start',
            position: { x: 250, y: 50 },
            data: { label: '开始' },
          },
          ...(pipeline.agents || []).map((agentId: string, i: number) => ({
            id: generateId(),
            type: 'agent' as const,
            position: { x: 250, y: 150 + i * 120 },
            data: {
              label: allAgents.find((a) => a.id === agentId)?.name || agentId,
              agent_id: agentId,
            },
          })),
          {
            id: 'end',
            type: 'end',
            position: { x: 250, y: 150 + (pipeline.agents?.length || 0) * 120 + 100 },
            data: { label: '结束' },
          },
        ];
        setNodes(fallbackNodes);
        // Auto-connect sequential edges
        const fallbackEdges: any[] = [];
        for (let i = 0; i < fallbackNodes.length - 1; i++) {
          fallbackEdges.push({
            id: `e-${fallbackNodes[i].id}-${fallbackNodes[i + 1].id}`,
            source: fallbackNodes[i].id,
            target: fallbackNodes[i + 1].id,
            sourceHandle: 'out',
            targetHandle: 'in',
          });
        }
        setEdges(fallbackEdges);
      }
    } else if (!pipeline && open) {
      // New pipeline: reset to defaults
      setNodes(defaultNodes);
      setEdges([]);
    }
  }, [pipeline, open]);

  // ── Drag from palette ──────────────────────────────────────────

  const onDragStart = useCallback(
    (event: React.DragEvent, nodeType: CanvasNodeType) => {
      event.dataTransfer.setData('application/reactflow', nodeType);
      event.dataTransfer.effectAllowed = 'move';
    },
    [],
  );

  // ── Drop onto canvas ───────────────────────────────────────────

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const nodeType = event.dataTransfer.getData('application/reactflow') as CanvasNodeType;
      if (!nodeType || !reactFlowWrapper.current) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const labelMap: Record<CanvasNodeType, string> = {
        start: '开始',
        end: '结束',
        agent: '智能体',
        branch: '分支',
        loop: '循环',
        parallel: '并行',
        sub_pipeline: '子编排',
      };

      const newNode = {
        id: generateId(),
        type: nodeType,
        position,
        data: { label: labelMap[nodeType] },
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [screenToFlowPosition, setNodes],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  // ── Edge connection ────────────────────────────────────────────

  const onConnect: OnConnect = useCallback(
    (params) => {
      const edge = {
        ...params,
        type: 'condition',
        markerEnd: { type: MarkerType.ArrowClosed, width: 20, height: 20 },
      };
      setEdges((eds) => addEdge(edge, eds));
    },
    [setEdges],
  );

  // ── Node selection ─────────────────────────────────────────────

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: any) => {
      setSelectedNode(node);
      setShowConfig(true);
    },
    [],
  );

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
    setShowConfig(false);
  }, []);

  // ── Delete nodes/edges ─────────────────────────────────────────

  const onNodesDelete: OnNodesDelete = useCallback(
    (deleted) => {
      const deletedIds = new Set(deleted.map((n) => n.id));
      setEdges((eds) => eds.filter((e) => !deletedIds.has(e.source) && !deletedIds.has(e.target)));
      if (selectedNode && deletedIds.has(selectedNode.id)) {
        setSelectedNode(null);
        setShowConfig(false);
      }
    },
    [selectedNode, setEdges],
  );

  const onEdgesDelete: OnEdgesDelete = useCallback(() => {
    // edges already removed by reactflow
  }, []);

  // ── Update node data ───────────────────────────────────────────

  const handleNodeUpdate = useCallback(
    (nodeId: string, data: Record<string, any>) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            const updatedData = { ...node.data, ...data };
            // Update label for agent node based on selected agent
            if (data.agent_id) {
              const agent = allAgents.find((a) => a.id === data.agent_id);
              updatedData.label = agent?.name || data.agent_id;
            }
            return { ...node, data: updatedData };
          }
          return node;
        }),
      );
      // Update selected node reference
      setSelectedNode((prev: any) => {
        if (prev && prev.id === nodeId) {
          return { ...prev, data: { ...prev.data, ...data } };
        }
        return prev;
      });
      message.success(t('pipeline.saveSuccess', '配置已更新'));
    },
    [setNodes, allAgents, t],
  );

  // ── Save pipeline ──────────────────────────────────────────────

  const handleSave = useCallback(async () => {
    if (!pipeline) return;
    setSaving(true);
    try {
      const canvasData = { nodes, edges };
      // Extract agent IDs from agent nodes for backward compatibility
      const agentIds = nodes
        .filter((n) => n.type === 'agent' && n.data?.agent_id)
        .map((n) => n.data.agent_id as string);

      await pipelineApi.update(pipeline.id, {
        name: pipeline.name,
        type: (pipeline.type as any) || 'sequential',
        agents: agentIds,
        description: pipeline.description,
        config: { ...pipeline.config, canvasData },
      });
      message.success(t('pipeline.saveSuccess', '保存成功'));
      onSaveSuccess();
    } catch (error) {
      message.error(t('pipeline.saveError', '保存失败'));
    } finally {
      setSaving(false);
    }
  }, [pipeline, nodes, edges, onSaveSuccess, t]);

  // ── Run pipeline ───────────────────────────────────────────────

  const handleRun = useCallback(async () => {
    if (!pipeline) return;
    try {
      await pipelineApi.execute(pipeline.id, {
        message: 'Execute pipeline from canvas',
      });
      message.success(t('pipeline.executeSuccess', '已开始执行'));
    } catch (error) {
      message.error(t('pipeline.executeError', '执行失败'));
    }
  }, [pipeline, t]);

  // ── Auto layout (simple vertical arrange) ──────────────────────

  const handleAutoLayout = useCallback(() => {
    const nodeWidth = 200;
    const nodeGap = 120;
    const sortedNodes = [...nodes].sort((a, b) => a.position.y - b.position.y);
    const newNodes = sortedNodes.map((node, i) => ({
      ...node,
      position: { x: 250, y: 50 + i * nodeGap },
    }));
    setNodes(newNodes);
    fitView({ padding: 0.2, duration: 500 });
  }, [nodes, setNodes, fitView]);

  // ── Delete selected ────────────────────────────────────────────

  const handleDeleteSelected = useCallback(() => {
    if (selectedNode) {
      setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
      setSelectedNode(null);
      setShowConfig(false);
    }
  }, [selectedNode, setNodes]);

  return (
    <Drawer
      title={
        <Space>
          <span>
            {pipeline ? t('pipeline.editPipeline', '编辑编排') : t('pipeline.createPipeline', '创建编排')}
          </span>
          {pipeline && <span style={{ color: 'rgba(0,0,0,0.45)', fontSize: 12 }}>{pipeline.name}</span>}
        </Space>
      }
      open={open}
      onClose={onClose}
      width="100%"
      styles={{ body: { padding: 0, height: 'calc(100vh - 200px)', overflow: 'hidden' } }}
    >
      <div className={styles.editorLayout}>
        {/* Left: Node Palette */}
        {showPalette && (
          <NodePalette onDragStart={onDragStart} />
        )}
        <Button
          type="text"
          icon={showPalette ? <LeftOutlined /> : <RightOutlined />}
          onClick={() => setShowPalette(!showPalette)}
          style={{ position: 'absolute', left: showPalette ? 200 : 0, top: '50%', zIndex: 10 }}
        />

        {/* Center: Canvas Area */}
        <div className={styles.canvasArea}>
          <Toolbar
            onSave={handleSave}
            onRun={handleRun}
            onAutoLayout={handleAutoLayout}
            onDeleteSelected={handleDeleteSelected}
            saving={saving}
            hasSelection={!!selectedNode}
          />
          <div ref={reactFlowWrapper} style={{ flex: 1, position: 'relative' }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onPaneClick={onPaneClick}
              onNodesDelete={onNodesDelete}
              onEdgesDelete={onEdgesDelete}
              onDrop={onDrop}
              onDragOver={onDragOver}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              defaultEdgeOptions={{
                type: 'condition',
                markerEnd: { type: MarkerType.ArrowClosed, width: 20, height: 20 },
              }}
              className={styles.pipelineCanvas}
            >
              <Controls />
              <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
            </ReactFlow>
          </div>
        </div>

        {/* Right: Config Panel */}
        {showConfig && selectedNode && (
          <>
            <ConfigPanel
              node={selectedNode}
              allAgents={allAgents.map((a) => ({ id: a.id, name: a.name }))}
              allPipelines={allPipelines.map((p) => ({ id: p.id, name: p.name }))}
              onUpdate={handleNodeUpdate}
              onClose={() => {
                setShowConfig(false);
                setSelectedNode(null);
              }}
            />
          </>
        )}
      </div>
    </Drawer>
  );
}

export const PipelineCanvasEditor = memo(PipelineCanvasEditorInner);

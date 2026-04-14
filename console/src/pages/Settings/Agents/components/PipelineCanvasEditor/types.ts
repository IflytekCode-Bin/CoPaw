/**
 * Pipeline Canvas Editor type definitions.
 * Maps visual canvas nodes/edges to backend Pipeline data.
 */

export type CanvasNodeType =
  | 'start'
  | 'end'
  | 'agent'
  | 'parallel'
  | 'branch'
  | 'loop'
  | 'sub_pipeline';

export interface CanvasNodeData {
  label: string;
  agent_id?: string;
  condition?: string;
  max_iterations?: number;
  sub_pipeline_id?: string;
  children?: string[]; // node IDs inside container (loop/parallel)
  description?: string;
}

/**
 * ReactFlow Node type alias.
 * We use the generic xyflow Node but with our data shape.
 */
export type PipelineCanvasNode = import('@xyflow/react').Node<CanvasNodeData, CanvasNodeType>;

/**
 * ReactFlow Edge type alias with optional label.
 */
export interface PipelineCanvasEdge extends import('@xyflow/react').Edge {
  label?: string;
}

/**
 * Serialized pipeline data stored in backend.
 * Extends the existing Pipeline type with canvas-specific fields.
 */
export interface PipelineCanvasData {
  nodes: PipelineCanvasNode[];
  edges: PipelineCanvasEdge[];
  viewport?: { x: number; y: number; zoom: number };
}

/**
 * Node palette item (draggable from left sidebar).
 */
export interface NodePaletteItem {
  type: CanvasNodeType;
  label: string;
  description: string;
  icon: string;
}

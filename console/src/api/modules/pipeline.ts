import { request } from "../request";

export interface Pipeline {
  id: string;
  name: string;
  type: "sequential" | "fanout" | "conditional" | "loop";
  agents: string[];
  description?: string;
  status: "pending" | "running" | "completed" | "failed";
  config: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface PipelineCreate {
  name: string;
  type: string;
  agents: string[];
  description?: string;
  config?: Record<string, any>;
}

export interface PipelineUpdate {
  name?: string;
  agents?: string[];
  description?: string;
  config?: Record<string, any>;
}

export interface PipelineExecute {
  input: string;
  kwargs?: Record<string, any>;
}

export interface PipelineExecution {
  pipeline_id: string;
  execution_id: string;
  status: string;
  started_at: string;
  completed_at?: string;
  result?: any;
  error?: string;
}

export const pipelineApi = {
  // List all pipelines
  list: () => request<Pipeline[]>("/pipelines/"),

  // Create a new pipeline
  create: (data: PipelineCreate) =>
    request<Pipeline>("/pipelines/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Get pipeline by ID
  get: (pipelineId: string) => request<Pipeline>(`/pipelines/${pipelineId}`),

  // Update pipeline
  update: (pipelineId: string, data: PipelineUpdate) =>
    request<Pipeline>(`/pipelines/${pipelineId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // Delete pipeline
  delete: (pipelineId: string) =>
    request<{ message: string }>(`/pipelines/${pipelineId}`, {
      method: "DELETE",
    }),

  // Execute pipeline
  execute: (pipelineId: string, data: PipelineExecute) =>
    request<PipelineExecution>(`/pipelines/${pipelineId}/execute`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Get pipeline execution history
  getHistory: (pipelineId: string) =>
    request<any[]>(`/pipelines/${pipelineId}/history`),

  // List all executions
  listExecutions: () => request<any[]>("/pipelines/executions/list"),
};

import { apiClient } from "../client";

export interface Pipeline {
  id: string;
  name: string;
  type: "sequential" | "fanout" | "conditional" | "loop";
  agents: string[];
  description?: string;
  config?: Record<string, any>;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface CreatePipelineRequest {
  name: string;
  type: string;
  agents: string[];
  description?: string;
  config?: Record<string, any>;
}

export interface UpdatePipelineRequest {
  name?: string;
  description?: string;
  config?: Record<string, any>;
}

export interface ExecutePipelineRequest {
  message: string;
  context?: Record<string, any>;
}

export interface PipelineExecution {
  id: string;
  pipeline_id: string;
  status: string;
  result?: any;
  error?: string;
  started_at: string;
  completed_at?: string;
}

export const pipelineApi = {
  list: async (): Promise<Pipeline[]> => {
    const response = await apiClient.get("/pipelines/");
    return response.data;
  },

  get: async (id: string): Promise<Pipeline> => {
    const response = await apiClient.get(`/pipelines/${id}`);
    return response.data;
  },

  create: async (data: CreatePipelineRequest): Promise<Pipeline> => {
    const response = await apiClient.post("/pipelines/", data);
    return response.data;
  },

  update: async (
    id: string,
    data: UpdatePipelineRequest
  ): Promise<Pipeline> => {
    const response = await apiClient.put(`/pipelines/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/pipelines/${id}`);
  },

  execute: async (
    id: string,
    data: ExecutePipelineRequest
  ): Promise<PipelineExecution> => {
    const response = await apiClient.post(`/pipelines/${id}/execute`, data);
    return response.data;
  },

  history: async (id: string): Promise<PipelineExecution[]> => {
    const response = await apiClient.get(`/pipelines/${id}/history`);
    return response.data;
  },
};

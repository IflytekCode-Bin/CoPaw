import { request } from "../request";

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
    return request<Pipeline[]>("/pipelines/");
  },

  get: async (id: string): Promise<Pipeline> => {
    return request<Pipeline>(`/pipelines/${id}`);
  },

  create: async (data: CreatePipelineRequest): Promise<Pipeline> => {
    return request<Pipeline>("/pipelines/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update: async (
    id: string,
    data: UpdatePipelineRequest
  ): Promise<Pipeline> => {
    return request<Pipeline>(`/pipelines/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  delete: async (id: string): Promise<void> => {
    return request<void>(`/pipelines/${id}`, {
      method: "DELETE",
    });
  },

  execute: async (
    id: string,
    data: ExecutePipelineRequest
  ): Promise<PipelineExecution> => {
    return request<PipelineExecution>(`/pipelines/${id}/execute`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  history: async (id: string): Promise<PipelineExecution[]> => {
    return request<PipelineExecution[]>(`/pipelines/${id}/history`);
  },
};

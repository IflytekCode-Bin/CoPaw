import { request } from "../request";

export interface Pipeline {
  id: string;
  name: string;
  type: "sequential" | "fanout" | "conditional" | "loop";
  agents: string[];
  description?: string;
  config?: Record<string, any>;
  status?: string;
  owner_agent_id?: string;
  sub_pipelines?: string[];
  parent_pipeline_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface ListPipelinesParams {
  owner_agent_id?: string;
  parent_pipeline_id?: string;
}

export interface CreatePipelineRequest {
  name: string;
  type: string;
  agents: string[];
  description?: string;
  config?: Record<string, any>;
  owner_agent_id?: string;
  sub_pipelines?: string[];
  parent_pipeline_id?: string | null;
}

export interface UpdatePipelineRequest {
  name?: string;
  type?: string;
  agents?: string[];
  description?: string;
  config?: Record<string, any>;
  sub_pipelines?: string[];
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
  list: async (params?: ListPipelinesParams): Promise<Pipeline[]> => {
    const qs = new URLSearchParams();
    if (params?.owner_agent_id) qs.set("owner_agent_id", params.owner_agent_id);
    if (params?.parent_pipeline_id) qs.set("parent_pipeline_id", params.parent_pipeline_id);
    const query = qs.toString();
    return request<Pipeline[]>(query ? `/pipelines/?${query}` : "/pipelines/");
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

  getSelectOptions: async (excludeId?: string): Promise<Array<{
    value: string;
    label: string;
    owner_agent_id?: string;
    sub_pipeline_count: number;
  }>> => {
    const qs = excludeId ? `?exclude_id=${excludeId}` : '';
    return request(`/pipelines/select-options${qs}`);
  },

  getNestingDepth: async (id: string): Promise<{ pipeline_id: string; depth: number }> => {
    return request(`/pipelines/${id}/depth`);
  },
};

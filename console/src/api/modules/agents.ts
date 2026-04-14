import { request } from "../request";
import type {
  AgentListResponse,
  AgentProfileConfig,
  CreateAgentRequest,
  AgentProfileRef,
  ReorderAgentsResponse,
} from "../types/agents";
import type { MdFileInfo, MdFileContent } from "../types/workspace";

// Multi-agent management API
export const agentsApi = {
  // List all agents
  listAgents: () => request<AgentListResponse>("/agents"),

  // Get agent details
  getAgent: (agentId: string) =>
    request<AgentProfileConfig>(`/agents/${agentId}`),

  // Create new agent
  createAgent: (agent: CreateAgentRequest) =>
    request<AgentProfileRef>("/agents", {
      method: "POST",
      body: JSON.stringify(agent),
    }),

  // Update agent configuration
  updateAgent: (agentId: string, agent: AgentProfileConfig) =>
    request<AgentProfileConfig>(`/agents/${agentId}`, {
      method: "PUT",
      body: JSON.stringify(agent),
    }),

  // Delete agent
  deleteAgent: (agentId: string) =>
    request<{ success: boolean; agent_id: string }>(`/agents/${agentId}`, {
      method: "DELETE",
    }),

  // Persist ordered agent ids
  reorderAgents: (agentIds: string[]) =>
    request<ReorderAgentsResponse>("/agents/order", {
      method: "PUT",
      body: JSON.stringify({ agent_ids: agentIds }),
    }),

  // Toggle agent enabled state
  toggleAgentEnabled: (agentId: string, enabled: boolean) =>
    request<{ success: boolean; agent_id: string; enabled: boolean }>(
      `/agents/${agentId}/toggle`,
      {
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      },
    ),

  // Agent workspace files
  listAgentFiles: (agentId: string) =>
    request<MdFileInfo[]>(`/agents/${agentId}/files`),

  readAgentFile: (agentId: string, filename: string) =>
    request<MdFileContent>(
      `/agents/${agentId}/files/${encodeURIComponent(filename)}`,
    ),

  writeAgentFile: (agentId: string, filename: string, content: string) =>
    request<{ written: boolean; filename: string }>(
      `/agents/${agentId}/files/${encodeURIComponent(filename)}`,
      {
        method: "PUT",
        body: JSON.stringify({ content }),
      },
    ),

  // Agent memory files
  listAgentMemory: (agentId: string) =>
    request<MdFileInfo[]>(`/agents/${agentId}/memory`),

  // Leader agent
  setLeaderAgent: (leaderId: string | null) =>
    request<{ success: boolean; leader_agent: string | null }>("/agents/leader", {
      method: "PUT",
      body: JSON.stringify({ leader_agent: leaderId }),
    }),

  // Per-agent leader operations
  setLeader: (agentId: string) =>
    request<{ success: boolean; agent_id: string; is_leader: boolean }>(
      `/agents/${agentId}/set-leader`,
      { method: "POST" },
    ),
  removeLeader: (agentId: string) =>
    request<{ success: boolean; agent_id: string; is_leader: boolean; was_leader: boolean }>(
      `/agents/${agentId}/remove-leader`,
      { method: "POST" },
    ),
};

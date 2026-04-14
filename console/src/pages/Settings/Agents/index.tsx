import { useState, useRef } from "react";
import { Card, Button, Form } from "antd";
import { useAppMessage } from "../../../hooks/useAppMessage";
import { PlusOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { agentsApi } from "../../../api/modules/agents";
import type { AgentSummary } from "../../../api/types/agents";
import { useAgentStore } from "../../../stores/agentStore";
import { useAgents } from "./useAgents";
import { AgentTable, AgentModal, PipelineManagementDrawer } from "./components";
import { PageHeader } from "@/components/PageHeader";
import { reorderAgents } from "./reorder";
import styles from "./index.module.less";

export default function AgentsPage() {
  const { t } = useTranslation();
  const { agents, loading, deleteAgent, toggleAgent, loadAgents, setAgents, leaderAgent, setLeader, removeLeader } =
    useAgents();
  const { selectedAgent, setSelectedAgent } = useAgentStore();
  const [modalVisible, setModalVisible] = useState(false);
  const [pipelineDrawerAgent, setPipelineDrawerAgent] = useState<AgentSummary | null>(null);
  const [editingAgent, setEditingAgent] = useState<AgentSummary | null>(null);
  const [reordering, setReordering] = useState(false);
  const [form] = Form.useForm();
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const installedSkillsRef = useRef<string[]>([]);
  const { message } = useAppMessage();

  const handleCreate = () => {
    setEditingAgent(null);
    form.resetFields();
    form.setFieldsValue({
      workspace_dir: "",
    });
    setSelectedSkills([]);
    installedSkillsRef.current = [];
    setModalVisible(true);
  };

  const handleEdit = async (agent: AgentSummary) => {
    try {
      const config = await agentsApi.getAgent(agent.id);
      setEditingAgent(agent);
      form.setFieldsValue(config);
      setModalVisible(true);
    } catch (error) {
      console.error("Failed to load agent config:", error);
      message.error(t("agent.loadConfigFailed"));
    }
  };

  const handleDelete = async (agentId: string) => {
    try {
      await deleteAgent(agentId);

      if (selectedAgent === agentId) {
        setSelectedAgent("default");
        message.info(t("agent.switchedToDefault"));
      }
    } catch {
      message.error(t("agent.deleteFailed"));
    }
  };

  const handleToggle = async (agentId: string, currentEnabled: boolean) => {
    const newEnabled = !currentEnabled;
    try {
      await toggleAgent(agentId, newEnabled);

      if (!newEnabled && selectedAgent === agentId) {
        setSelectedAgent("default");
        message.info(t("agent.switchedToDefault"));
      }
    } catch {
      // Error already handled in hook
    }
  };

  const handleInstalledSkillsLoaded = (skills: string[]) => {
    installedSkillsRef.current = skills;
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const workspaceRaw = values.workspace_dir;
      const workspace_dir =
        typeof workspaceRaw === "string"
          ? workspaceRaw.trim() || undefined
          : workspaceRaw;
      const payload = { ...values, workspace_dir };

      if (editingAgent) {
        await agentsApi.updateAgent(editingAgent.id, payload);
        message.success(t("agent.updateSuccess"));
      } else {
        const result = await agentsApi.createAgent({
          ...payload,
          skill_names: selectedSkills,
        });
        message.success(`${t("agent.createSuccess")} (ID: ${result.id})`);
      }

      setModalVisible(false);
      await loadAgents();
    } catch (error: any) {
      console.error("Failed to save agent:", error);
      message.error(error.message || t("agent.saveFailed"));
    }
  };

  const handleReorder = async (activeId: string, overId: string) => {
    const nextAgents = reorderAgents(agents, activeId, overId);
    if (nextAgents === agents) {
      return;
    }

    const previousAgents = agents;
    setAgents(nextAgents);
    setReordering(true);

    try {
      await agentsApi.reorderAgents(nextAgents.map((agent) => agent.id));
      message.success(t("agent.reorderSuccess"));
    } catch (error) {
      console.error("Failed to reorder agents:", error);
      setAgents(previousAgents);
      message.error(t("agent.reorderFailed"));
    } finally {
      setReordering(false);
    }
  };

  const handleOrchestration = (agent: AgentSummary) => {
    setPipelineDrawerAgent(agent);
  };

  const handleSetLeader = async (agentId: string) => {
    await setLeader(agentId);
  };

  const handleRemoveLeader = async (agentId: string) => {
    await removeLeader(agentId);
  };

  return (
    <div className={styles.agentsPage}>
      <PageHeader
        parent={t("agent.parent")}
        current={t("agent.agents")}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleCreate}
          >
            {t("agent.create")}
          </Button>
        }
      />

      <Card className={styles.tableCard}>
        <AgentTable
          agents={agents}
          loading={loading || reordering}
          reordering={reordering}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onToggle={handleToggle}
          onReorder={handleReorder}
          onSetLeader={handleSetLeader}
          onRemoveLeader={handleRemoveLeader}
          onOrchestration={handleOrchestration}
        />
      </Card>

      <AgentModal
        open={modalVisible}
        editingAgent={editingAgent}
        form={form}
        selectedSkills={selectedSkills}
        onSelectedSkillsChange={setSelectedSkills}
        onInstalledSkillsLoaded={handleInstalledSkillsLoaded}
        onSave={handleSubmit}
        onCancel={() => setModalVisible(false)}
      />

      <PipelineManagementDrawer
        open={!!pipelineDrawerAgent}
        ownerAgent={pipelineDrawerAgent}
        allAgents={agents}
        leaderAgent={leaderAgent}
        onClose={() => setPipelineDrawerAgent(null)}
        onPipelineSuccess={() => {
          setPipelineDrawerAgent(null);
          message.success(t("pipeline.saveSuccess", "Pipeline saved successfully"));
        }}
      />
    </div>
  );
}

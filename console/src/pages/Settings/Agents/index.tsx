import { useState, useRef } from "react";
import { Card, Button, Form, message, Space } from "antd";
import { PlusOutlined, CrownOutlined, ApartmentOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { agentsApi } from "../../../api/modules/agents";
import type { AgentSummary } from "../../../api/types/agents";
import { useAgents } from "./useAgents";
import { useAgentStore } from "../../../stores/agentStore";
import { AgentTable, AgentModal } from "./components";
import { PipelineOrchestrationModal } from "./components/PipelineOrchestrationModal";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

export default function AgentsPage() {
  const { t } = useTranslation();
  const { agents, loading, deleteAgent, toggleAgent, loadAgents } = useAgents();
  const { selectedAgent, setSelectedAgent } = useAgentStore();
  const [modalVisible, setModalVisible] = useState(false);
  const [orchestrationModalVisible, setOrchestrationModalVisible] = useState(false);
  const [editingAgent, setEditingAgent] = useState<AgentSummary | null>(null);
  const [form] = Form.useForm();
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const installedSkillsRef = useRef<string[]>([]);
  const [leaderAgent, setLeaderAgent] = useState<string | null>(null);

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

  const handleSetLeader = () => {
    if (!selectedAgent) {
      message.warning(t("agent.selectAgentFirst", "Please select an agent first"));
      return;
    }
    setLeaderAgent(selectedAgent);
    message.success(
      t("agent.leaderSet", `Agent ${selectedAgent} set as leader agent`)
    );
  };

  const handleOrchestration = () => {
    if (!leaderAgent) {
      message.warning(
        t("agent.setLeaderFirst", "Please set a leader agent first")
      );
      return;
    }
    setOrchestrationModalVisible(true);
  };

  return (
    <div className={styles.agentsPage}>
      <PageHeader
        parent={t("agent.parent")}
        current={t("agent.agents")}
        extra={
          <Space>
            <Button
              icon={<CrownOutlined />}
              onClick={handleSetLeader}
              disabled={!selectedAgent}
            >
              {t("agent.setLeader", "Set as Leader")}
            </Button>
            <Button
              icon={<ApartmentOutlined />}
              onClick={handleOrchestration}
              disabled={!leaderAgent}
            >
              {t("agent.orchestration", "Orchestration")}
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleCreate}
            >
              {t("agent.create")}
            </Button>
          </Space>
        }
      />

      <Card className={styles.tableCard}>
        <AgentTable
          agents={agents}
          loading={loading}
          leaderAgent={leaderAgent}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onToggle={handleToggle}
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

      <PipelineOrchestrationModal
        open={orchestrationModalVisible}
        leaderAgent={leaderAgent}
        agents={agents.filter((a) => a.id !== leaderAgent)}
        onCancel={() => setOrchestrationModalVisible(false)}
        onSuccess={() => {
          setOrchestrationModalVisible(false);
          message.success(t("pipeline.saveSuccess", "Pipeline saved successfully"));
        }}
      />
    </div>
  );
}

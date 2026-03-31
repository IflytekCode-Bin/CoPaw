import { useState, useEffect } from "react";
import {
  Modal,
  Form,
  Input,
  Select,
  Button,
  Space,
  Card,
  Tag,
  message,
} from "antd";
import { PlusOutlined, DeleteOutlined, ArrowDownOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { pipelineApi } from "../../../../api/modules/pipeline";
import type { AgentSummary } from "../../../../api/types/agents";
import styles from "./PipelineOrchestrationModal.module.less";

interface Props {
  open: boolean;
  leaderAgent: string | null;
  agents: AgentSummary[];
  onCancel: () => void;
  onSuccess: () => void;
}

interface AgentNode {
  id: string;
  agentId: string;
  order: number;
}

export function PipelineOrchestrationModal({
  open,
  leaderAgent,
  agents,
  onCancel,
  onSuccess,
}: Props) {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [pipelineType, setPipelineType] = useState<string>("sequential");
  const [selectedAgents, setSelectedAgents] = useState<AgentNode[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      form.resetFields();
      setSelectedAgents([]);
      setPipelineType("sequential");
    }
  }, [open, form]);

  const handleAddAgent = () => {
    const newNode: AgentNode = {
      id: `node_${Date.now()}`,
      agentId: "",
      order: selectedAgents.length,
    };
    setSelectedAgents([...selectedAgents, newNode]);
  };

  const handleRemoveAgent = (id: string) => {
    setSelectedAgents(selectedAgents.filter((node) => node.id !== id));
  };

  const handleAgentChange = (nodeId: string, agentId: string) => {
    setSelectedAgents(
      selectedAgents.map((node) =>
        node.id === nodeId ? { ...node, agentId } : node
      )
    );
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();

      if (selectedAgents.length === 0) {
        message.warning(
          t("pipeline.selectAgentsWarning", "Please select at least one agent")
        );
        return;
      }

      const invalidAgents = selectedAgents.filter((node) => !node.agentId);
      if (invalidAgents.length > 0) {
        message.warning(
          t("pipeline.fillAllAgents", "Please fill all agent selections")
        );
        return;
      }

      setSaving(true);

      const agentIds = selectedAgents.map((node) => node.agentId);

      await pipelineApi.create({
        name: values.name,
        type: pipelineType,
        agents: agentIds,
        description: values.description,
        config: {
          leader_agent: leaderAgent,
        },
      });

      message.success(t("pipeline.createSuccess", "Pipeline created successfully"));
      onSuccess();
    } catch (error: any) {
      console.error("Failed to save pipeline:", error);
      message.error(error.message || t("pipeline.saveFailed", "Failed to save pipeline"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={t("agent.orchestration", "Agent Orchestration")}
      open={open}
      onCancel={onCancel}
      width={800}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          {t("common.cancel", "Cancel")}
        </Button>,
        <Button
          key="save"
          type="primary"
          loading={saving}
          onClick={handleSave}
        >
          {t("common.save", "Save")}
        </Button>,
      ]}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          name="name"
          label={t("pipeline.name", "Pipeline Name")}
          rules={[{ required: true, message: t("pipeline.nameRequired", "Please enter pipeline name") }]}
        >
          <Input placeholder={t("pipeline.namePlaceholder", "Enter pipeline name")} />
        </Form.Item>

        <Form.Item
          label={t("pipeline.type", "Pipeline Type")}
        >
          <Select
            value={pipelineType}
            onChange={setPipelineType}
            options={[
              { value: "sequential", label: t("pipeline.type.sequential", "Sequential") },
              { value: "fanout", label: t("pipeline.type.fanout", "Fanout") },
              { value: "conditional", label: t("pipeline.type.conditional", "Conditional") },
              { value: "loop", label: t("pipeline.type.loop", "Loop") },
            ]}
          />
        </Form.Item>

        <Form.Item
          name="description"
          label={t("pipeline.description", "Description")}
        >
          <Input.TextArea
            rows={3}
            placeholder={t("pipeline.descriptionPlaceholder", "Enter description")}
          />
        </Form.Item>

        <Form.Item label={t("pipeline.leaderAgent", "Leader Agent")}>
          <Tag color="blue">{leaderAgent}</Tag>
        </Form.Item>

        <Form.Item label={t("pipeline.agentFlow", "Agent Flow")}>
          <Card className={styles.flowCard}>
            <Space direction="vertical" style={{ width: "100%" }} size="middle">
              {selectedAgents.map((node, index) => (
                <div key={node.id}>
                  <Space style={{ width: "100%" }}>
                    <span className={styles.stepNumber}>{index + 1}</span>
                    <Select
                      style={{ flex: 1, minWidth: 200 }}
                      placeholder={t("pipeline.selectAgent", "Select agent")}
                      value={node.agentId || undefined}
                      onChange={(value) => handleAgentChange(node.id, value)}
                      options={agents.map((agent) => ({
                        value: agent.id,
                        label: agent.id,
                        disabled: selectedAgents.some(
                          (n) => n.id !== node.id && n.agentId === agent.id
                        ),
                      }))}
                    />
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleRemoveAgent(node.id)}
                    />
                  </Space>
                  {index < selectedAgents.length - 1 && (
                    <div className={styles.arrow}>
                      <ArrowDownOutlined />
                    </div>
                  )}
                </div>
              ))}

              <Button
                type="dashed"
                icon={<PlusOutlined />}
                onClick={handleAddAgent}
                block
              >
                {t("pipeline.addAgent", "Add Agent")}
              </Button>
            </Space>
          </Card>
        </Form.Item>
      </Form>
    </Modal>
  );
}

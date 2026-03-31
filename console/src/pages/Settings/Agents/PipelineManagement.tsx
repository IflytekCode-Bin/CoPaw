import { useState, useEffect } from "react";
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  message,
  Popconfirm,
  Modal,
  Form,
  Input,
  Select,
} from "antd";
import { EditOutlined, DeleteOutlined, ReloadOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { pipelineApi, type Pipeline } from "../../../api/modules/pipeline";
import { PageHeader } from "@/components/PageHeader";
import styles from "./PipelineManagement.module.less";

export default function PipelineManagementPage() {
  const { t } = useTranslation();
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(false);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingPipeline, setEditingPipeline] = useState<Pipeline | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadPipelines();
  }, []);

  const loadPipelines = async () => {
    setLoading(true);
    try {
      const data = await pipelineApi.list();
      setPipelines(data);
    } catch (error) {
      message.error(t("pipeline.loadError", "Failed to load pipelines"));
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (pipeline: Pipeline) => {
    setEditingPipeline(pipeline);
    form.setFieldsValue({
      name: pipeline.name,
      type: pipeline.type,
      description: pipeline.description,
    });
    setEditModalVisible(true);
  };

  const handleDelete = async (id: string) => {
    try {
      await pipelineApi.delete(id);
      message.success(t("pipeline.deleteSuccess", "Pipeline deleted successfully"));
      loadPipelines();
    } catch (error) {
      message.error(t("pipeline.deleteError", "Failed to delete pipeline"));
    }
  };

  const handleUpdate = async () => {
    if (!editingPipeline) return;

    try {
      const values = await form.validateFields();
      await pipelineApi.update(editingPipeline.id, values);
      message.success(t("pipeline.updateSuccess", "Pipeline updated successfully"));
      setEditModalVisible(false);
      loadPipelines();
    } catch (error) {
      message.error(t("pipeline.updateError", "Failed to update pipeline"));
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending: "default",
      running: "processing",
      completed: "success",
      failed: "error",
    };
    return colors[status] || "default";
  };

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      sequential: t("pipeline.type.sequential", "Sequential"),
      fanout: t("pipeline.type.fanout", "Fanout"),
      conditional: t("pipeline.type.conditional", "Conditional"),
      loop: t("pipeline.type.loop", "Loop"),
    };
    return labels[type] || type;
  };

  const columns = [
    {
      title: t("pipeline.name", "Name"),
      dataIndex: "name",
      key: "name",
    },
    {
      title: t("pipeline.type", "Type"),
      dataIndex: "type",
      key: "type",
      render: (type: string) => <Tag>{getTypeLabel(type)}</Tag>,
    },
    {
      title: t("pipeline.agents", "Agents"),
      dataIndex: "agents",
      key: "agents",
      render: (agents: string[]) => (
        <Space size={[0, 4]} wrap>
          {agents.map((agent) => (
            <Tag key={agent} color="blue">
              {agent}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: t("pipeline.leaderAgent", "Leader Agent"),
      dataIndex: "config",
      key: "leader",
      render: (config: any) =>
        config?.leader_agent ? (
          <Tag color="gold">{config.leader_agent}</Tag>
        ) : (
          "-"
        ),
    },
    {
      title: t("pipeline.status", "Status"),
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {t(`pipeline.status.${status}`, status)}
        </Tag>
      ),
    },
    {
      title: t("pipeline.updatedAt", "Updated At"),
      dataIndex: "updated_at",
      key: "updated_at",
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: t("common.actions", "Actions"),
      key: "actions",
      render: (_: any, record: Pipeline) => (
        <Space>
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            {t("common.edit", "Edit")}
          </Button>
          <Popconfirm
            title={t("pipeline.deleteConfirm", "Delete this pipeline?")}
            onConfirm={() => handleDelete(record.id)}
            okText={t("common.yes", "Yes")}
            cancelText={t("common.no", "No")}
          >
            <Button type="text" danger icon={<DeleteOutlined />}>
              {t("common.delete", "Delete")}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div className={styles.pipelineManagementPage}>
      <PageHeader
        parent={t("agent.parent", "Settings")}
        current={t("pipeline.management", "Pipeline Management")}
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={loadPipelines}
            loading={loading}
          >
            {t("common.refresh", "Refresh")}
          </Button>
        }
      />

      <Card>
        <Table
          columns={columns}
          dataSource={pipelines}
          rowKey="id"
          loading={loading}
        />
      </Card>

      <Modal
        title={t("pipeline.edit", "Edit Pipeline")}
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        onOk={handleUpdate}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label={t("pipeline.name", "Name")}
            rules={[{ required: true }]}
          >
            <Input />
          </Form.Item>

          <Form.Item name="type" label={t("pipeline.type", "Type")}>
            <Select disabled>
              <Select.Option value="sequential">
                {t("pipeline.type.sequential", "Sequential")}
              </Select.Option>
              <Select.Option value="fanout">
                {t("pipeline.type.fanout", "Fanout")}
              </Select.Option>
              <Select.Option value="conditional">
                {t("pipeline.type.conditional", "Conditional")}
              </Select.Option>
              <Select.Option value="loop">
                {t("pipeline.type.loop", "Loop")}
              </Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="description" label={t("pipeline.description", "Description")}>
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

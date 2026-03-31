import { useState, useEffect } from "react";
import {
  Card,
  Button,
  Table,
  Modal,
  Form,
  Input,
  Select,
  Space,
  Tag,
  message,
  Tooltip,
  Popconfirm,
} from "antd";
import {
  PlusOutlined,
  PlayCircleOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { PageHeader } from "@/components/PageHeader";
import { pipelineApi, type Pipeline as PipelineType } from "@/api/modules/pipeline";
import styles from "./index.module.less";

export default function PipelinePage() {
  const { t } = useTranslation();
  const [pipelines, setPipelines] = useState<PipelineType[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [executeModalOpen, setExecuteModalOpen] = useState(false);
  const [historyModalOpen, setHistoryModalOpen] = useState(false);
  const [selectedPipeline, setSelectedPipeline] = useState<PipelineType | null>(
    null,
  );
  const [executions, setExecutions] = useState<any[]>([]);
  const [form] = Form.useForm();
  const [executeForm] = Form.useForm();

  // Load pipelines
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

  const handleCreate = async (values: any) => {
    try {
      await pipelineApi.create(values);
      message.success(
        t("pipeline.createSuccess", "Pipeline created successfully"),
      );
      setCreateModalOpen(false);
      form.resetFields();
      loadPipelines();
    } catch (error) {
      message.error(t("pipeline.createError", "Failed to create pipeline"));
    }
  };

  const handleExecute = async (values: any) => {
    if (!selectedPipeline) return;
    try {
      await pipelineApi.execute(selectedPipeline.id, values);
      message.success(
        t("pipeline.executeSuccess", "Pipeline execution started"),
      );
      setExecuteModalOpen(false);
      executeForm.resetFields();
      loadPipelines();
    } catch (error) {
      message.error(t("pipeline.executeError", "Failed to execute pipeline"));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await pipelineApi.delete(id);
      message.success(
        t("pipeline.deleteSuccess", "Pipeline deleted successfully"),
      );
      loadPipelines();
    } catch (error) {
      message.error(t("pipeline.deleteError", "Failed to delete pipeline"));
    }
  };

  const handleViewHistory = async (pipeline: PipelineType) => {
    setSelectedPipeline(pipeline);
    setHistoryModalOpen(true);
    try {
      const data = await pipelineApi.getHistory(pipeline.id);
      setExecutions(data);
    } catch (error) {
      message.error(t("pipeline.historyError", "Failed to load history"));
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
      render: (_: any, record: PipelineType) => (
        <Space>
          <Tooltip title={t("pipeline.execute", "Execute")}>
            <Button
              type="text"
              icon={<PlayCircleOutlined />}
              onClick={() => {
                setSelectedPipeline(record);
                setExecuteModalOpen(true);
              }}
            />
          </Tooltip>
          <Tooltip title={t("pipeline.history", "History")}>
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => handleViewHistory(record)}
            />
          </Tooltip>
          <Popconfirm
            title={t("pipeline.deleteConfirm", "Delete this pipeline?")}
            onConfirm={() => handleDelete(record.id)}
            okText={t("common.yes", "Yes")}
            cancelText={t("common.no", "No")}
          >
            <Tooltip title={t("common.delete", "Delete")}>
              <Button type="text" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const executionColumns = [
    {
      title: t("pipeline.executionId", "Execution ID"),
      dataIndex: "execution_id",
      key: "execution_id",
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
      title: t("pipeline.startedAt", "Started At"),
      dataIndex: "started_at",
      key: "started_at",
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: t("pipeline.completedAt", "Completed At"),
      dataIndex: "completed_at",
      key: "completed_at",
      render: (date?: string) =>
        date ? new Date(date).toLocaleString() : "-",
    },
  ];

  return (
    <div className={styles.pipelinePage}>
      <PageHeader
        title={t("pipeline.title", "Pipeline Management")}
        description={t(
          "pipeline.description",
          "Create and manage multi-agent pipelines",
        )}
      />

      <Card
        title={t("pipeline.list", "Pipelines")}
        extra={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadPipelines}
              loading={loading}
            >
              {t("common.refresh", "Refresh")}
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setCreateModalOpen(true)}
            >
              {t("pipeline.create", "Create Pipeline")}
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={pipelines}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* Create Pipeline Modal */}
      <Modal
        title={t("pipeline.create", "Create Pipeline")}
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="name"
            label={t("pipeline.name", "Name")}
            rules={[{ required: true }]}
          >
            <Input placeholder={t("pipeline.namePlaceholder", "Enter name")} />
          </Form.Item>

          <Form.Item
            name="type"
            label={t("pipeline.type", "Type")}
            rules={[{ required: true }]}
          >
            <Select placeholder={t("pipeline.typePlaceholder", "Select type")}>
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

          <Form.Item
            name="agents"
            label={t("pipeline.agents", "Agents")}
            rules={[{ required: true }]}
          >
            <Select
              mode="tags"
              placeholder={t("pipeline.agentsPlaceholder", "Select agents")}
            >
              <Select.Option value="analyst">Analyst</Select.Option>
              <Select.Option value="writer">Writer</Select.Option>
              <Select.Option value="reviewer">Reviewer</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="description"
            label={t("pipeline.description", "Description")}
          >
            <Input.TextArea
              rows={3}
              placeholder={t(
                "pipeline.descriptionPlaceholder",
                "Enter description",
              )}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Execute Pipeline Modal */}
      <Modal
        title={t("pipeline.execute", "Execute Pipeline")}
        open={executeModalOpen}
        onCancel={() => {
          setExecuteModalOpen(false);
          executeForm.resetFields();
        }}
        onOk={() => executeForm.submit()}
      >
        <Form form={executeForm} layout="vertical" onFinish={handleExecute}>
          <Form.Item label={t("pipeline.name", "Pipeline")}>
            <Input value={selectedPipeline?.name} disabled />
          </Form.Item>

          <Form.Item
            name="input"
            label={t("pipeline.input", "Input Message")}
            rules={[{ required: true }]}
          >
            <Input.TextArea
              rows={4}
              placeholder={t(
                "pipeline.inputPlaceholder",
                "Enter input message",
              )}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* History Modal */}
      <Modal
        title={t("pipeline.history", "Execution History")}
        open={historyModalOpen}
        onCancel={() => setHistoryModalOpen(false)}
        footer={null}
        width={800}
      >
        <Table
          columns={executionColumns}
          dataSource={executions}
          rowKey="execution_id"
        />
      </Modal>
    </div>
  );
}

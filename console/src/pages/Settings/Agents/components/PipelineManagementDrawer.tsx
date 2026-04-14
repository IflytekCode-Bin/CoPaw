import { Table, Button, Space, Popconfirm, Tag, message, Drawer } from "antd";
import type { ColumnsType } from "antd/es/table";
import { EditOutlined, DeleteOutlined, EyeOutlined, PlusOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { pipelineApi, type Pipeline, type CreatePipelineRequest } from "../../../../api/modules/pipeline";
import type { AgentSummary } from "../../../../api/types/agents";
import PipelineTreeSelect from "./PipelineTreeSelect";
import { PipelineCanvasEditor } from "./PipelineCanvasEditor";
import styles from "./PipelineManagementDrawer.module.less";

interface Props {
  open: boolean;
  ownerAgent: AgentSummary | null;
  allAgents: AgentSummary[];
  leaderAgent: string | null;
  onClose: () => void;
  onPipelineSuccess: () => void;
}

interface PipelineFormValues {
  name: string;
  type: string;
  agents: string[];
  description?: string;
  sub_pipelines?: string[];
  parent_pipeline_id?: string;
}

export function PipelineManagementDrawer({
  open,
  ownerAgent,
  allAgents,
  leaderAgent,
  onClose,
  onPipelineSuccess,
}: Props) {
  const { t } = useTranslation();
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [loading, setLoading] = useState(false);
  const [viewDrawerVisible, setViewDrawerVisible] = useState(false);
  const [canvasEditorPipeline, setCanvasEditorPipeline] = useState<Pipeline | null>(null);
  const [viewingPipeline, setViewingPipeline] = useState<Pipeline | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadPipelines = useCallback(async () => {
    if (!ownerAgent) return;
    setLoading(true);
    try {
      const data = await pipelineApi.list({ owner_agent_id: ownerAgent.id });
      setPipelines(data);
    } catch (error) {
      message.error(t("pipeline.loadError", "加载编排失败"));
    } finally {
      setLoading(false);
    }
  }, [ownerAgent, t]);

  useEffect(() => {
    if (open && ownerAgent) {
      loadPipelines();
    }
  }, [open, ownerAgent, loadPipelines]);

  const handleDelete = async (pipeline: Pipeline) => {
    try {
      await pipelineApi.delete(pipeline.id);
      message.success(t("pipeline.deleteSuccess", "编排已删除"));
      await loadPipelines();
    } catch (error) {
      message.error(t("pipeline.deleteError", "删除编排失败"));
    }
  };

  const getAgentName = (agentId: string) => {
    const agent = allAgents.find((a) => a.id === agentId);
    return agent?.name || agentId;
  };

  const getTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      sequential: t("pipeline.type.sequential", "顺序"),
      fanout: t("pipeline.type.fanout", "并行"),
      conditional: t("pipeline.type.conditional", "条件"),
      loop: t("pipeline.type.loop", "循环"),
    };
    return labels[type] || type;
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending: "default",
      running: "processing",
      completed: "success",
      failed: "error",
    };
    return colors[status || "pending"] || "default";
  };

  const handleCreatePipeline = async () => {
    // Open canvas editor with null pipeline (creates new)
    setCanvasEditorPipeline(null);
  };

  const handleEditPipeline = async (pipeline: Pipeline) => {
    // Open canvas editor with existing pipeline
    setCanvasEditorPipeline(pipeline);
  };

  const columns: ColumnsType<Pipeline> = [
    {
      title: t("pipeline.name", "名称"),
      dataIndex: "name",
      key: "name",
      width: 160,
    },
    {
      title: t("pipeline.type", "类型"),
      dataIndex: "type",
      key: "type",
      width: 90,
      render: (type: string) => <Tag>{getTypeLabel(type)}</Tag>,
    },
    {
      title: t("pipeline.agents", "包含智能体"),
      key: "agents",
      ellipsis: true,
      render: (_: any, record: Pipeline) => (
        <Space size={4} wrap>
          {record.agents?.slice(0, 3).map((agentId: string) => (
            <Tag key={agentId} color="blue">
              {getAgentName(agentId)}
            </Tag>
          ))}
          {record.agents?.length > 3 && (
            <Tag color="default">+{record.agents.length - 3}</Tag>
          )}
        </Space>
      ),
    },
    {
      title: t("pipeline.status", "状态"),
      dataIndex: "status",
      key: "status",
      width: 80,
      render: (status: string) => (
        <Tag color={getStatusColor(status || "pending")}>
          {status || "pending"}
        </Tag>
      ),
    },
    {
      title: t("pipeline.nested", "子编排"),
      key: "nested",
      width: 70,
      align: "center",
      render: (_: any, record: Pipeline) => {
        const nestedCount = record.sub_pipelines?.length || 0;
        return nestedCount > 0 ? (
          <Tag color="purple">{nestedCount}</Tag>
        ) : (
          <span className={styles.emptyText}>-</span>
        );
      },
    },
    {
      title: t("common.actions", "操作"),
      key: "actions",
      width: 180,
      fixed: "right" as const,
      render: (_: any, record: Pipeline) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              setViewingPipeline(record);
              setViewDrawerVisible(true);
            }}
            title={t("pipeline.view", "查看")}
          />
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditPipeline(record)}
            title={t("pipeline.edit", "编辑")}
          />
          <Popconfirm
            title={t("pipeline.deleteConfirm", "确认删除编排？")}
            description={t("pipeline.deleteConfirmDesc", "删除后不可恢复，请确认")}
            onConfirm={() => handleDelete(record)}
            okText={t("common.confirm", "确认")}
            cancelText={t("common.cancel", "取消")}
          >
            <Button
              type="text"
              size="small"
              danger
              icon={<DeleteOutlined />}
              title={t("common.delete", "删除")}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const availableAgents = allAgents.filter((a) => a.id !== ownerAgent?.id);

  return (
    <>
      {/* ─── Main Pipeline List Drawer ─── */}
      <Drawer
        title={
          <span>
            {t("pipeline.management", "编排管理")} — {ownerAgent?.name || ""}
          </span>
        }
        placement="right"
        width={860}
        open={open}
        onClose={onClose}
        className={styles.pipelineDrawer}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => handleCreatePipeline()}
          >
            {t("pipeline.create", "新增编排")}
          </Button>
        }
      >
        {!ownerAgent?.is_leader && leaderAgent !== ownerAgent?.id && (
          <div className={styles.warningBanner}>
            {t("pipeline.notLeaderWarning", "当前智能体未设为 Leader，无法创建编排。请先将当前智能体设为 Leader。")}
          </div>
        )}

        <Table<Pipeline>
          dataSource={pipelines}
          columns={columns}
          loading={loading}
          rowKey="id"
          pagination={false}
          scroll={{ y: "calc(100vh - 200px)" }}
          locale={{
            emptyText: ownerAgent?.is_leader || leaderAgent === ownerAgent?.id
              ? t("pipeline.emptyWithLeader", "暂无编排，点击「新增编排」创建")
              : t("pipeline.emptyWithoutLeader", "请先将当前智能体设为 Leader"),
          }}
        />
      </Drawer>

      {/* ─── Canvas Editor Drawer (replaces old Create/Edit form drawers) ─── */}
      <PipelineCanvasEditor
        open={!!canvasEditorPipeline}
        pipeline={canvasEditorPipeline}
        allAgents={allAgents}
        allPipelines={pipelines.filter((p) => p.id !== canvasEditorPipeline?.id)}
        onClose={() => setCanvasEditorPipeline(null)}
        onSaveSuccess={() => {
          setCanvasEditorPipeline(null);
          loadPipelines();
        }}
      />

      {/* ─── View Drawer ─── */}
      <Drawer
        title={t("pipeline.viewDetail", "编排详情")}
        open={viewDrawerVisible}
        onClose={() => setViewDrawerVisible(false)}
        width={520}
      >
        {viewingPipeline && (
          <div className={styles.viewContent}>
            <div className={styles.viewField}>
              <label>{t("pipeline.name", "名称")}:</label>
              <span>{viewingPipeline.name}</span>
            </div>
            <div className={styles.viewField}>
              <label>{t("pipeline.type", "类型")}:</label>
              <Tag>{getTypeLabel(viewingPipeline.type)}</Tag>
            </div>
            <div className={styles.viewField}>
              <label>{t("pipeline.description", "描述")}:</label>
              <span>{viewingPipeline.description || "-"}</span>
            </div>
            <div className={styles.viewField}>
              <label>{t("pipeline.agents", "包含智能体")}:</label>
              <Space wrap>
                {viewingPipeline.agents?.map((agentId: string) => (
                  <Tag key={agentId} color="blue">
                    {getAgentName(agentId)}
                  </Tag>
                ))}
              </Space>
            </div>
            <div className={styles.viewField}>
              <label>{t("pipeline.status", "状态")}:</label>
              <Tag color={getStatusColor(viewingPipeline.status || "pending")}>
                {viewingPipeline.status || "pending"}
              </Tag>
            </div>
            <div className={styles.viewField}>
              <label>{t("pipeline.nested", "子编排")}:</label>
              <span>
                {viewingPipeline.sub_pipelines?.length
                  ? viewingPipeline.sub_pipelines.map((id: string) => (
                      <Tag key={id} color="purple">Pipeline {id}</Tag>
                    ))
                  : "-"}
              </span>
            </div>
            {viewingPipeline.owner_agent_id && (
              <div className={styles.viewField}>
                <label>{t("pipeline.owner", "所属智能体")}:</label>
                <span>{getAgentName(viewingPipeline.owner_agent_id)}</span>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </>
  );
}

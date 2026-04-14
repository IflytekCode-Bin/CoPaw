import { Table, Button, Space, Popconfirm, Tag, Tooltip } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useTranslation } from "react-i18next";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { EditOutlined, DeleteOutlined, RobotOutlined, CrownOutlined, ApartmentOutlined, CloseCircleOutlined } from "@ant-design/icons";
import { EyeOff, Eye } from "lucide-react";
import type { AgentSummary } from "../../../../api/types/agents";
import { useTheme } from "../../../../contexts/ThemeContext";
import { getAgentDisplayName } from "../../../../utils/agentDisplayName";
import { SortableAgentRow, DragHandle } from "./SortableAgentRow";
import styles from "../index.module.less";

interface AgentTableProps {
  agents: AgentSummary[];
  loading: boolean;
  reordering: boolean;
  onEdit: (agent: AgentSummary) => void;
  onDelete: (agentId: string) => void;
  onToggle: (agentId: string, currentEnabled: boolean) => void;
  onReorder: (activeId: string, overId: string) => void;
  onSetLeader: (agentId: string) => void;
  onRemoveLeader: (agentId: string) => void;
  onOrchestration: (agent: AgentSummary) => void;
}

export function AgentTable({
  agents,
  loading,
  reordering,
  onEdit,
  onDelete,
  onToggle,
  onReorder,
  onSetLeader,
  onRemoveLeader,
  onOrchestration,
}: AgentTableProps) {
  const { t } = useTranslation();
  const { isDark } = useTheme();
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 6,
      },
    }),
  );

  const disabledStyle: React.CSSProperties = isDark
    ? { color: "rgba(255,255,255,0.35)", opacity: 1 }
    : {};

  const iconStyle: React.CSSProperties = isDark
    ? { color: "rgba(255,255,255,0.85)" }
    : {};

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) {
      return;
    }

    onReorder(String(active.id), String(over.id));
  };

  const columns: ColumnsType<AgentSummary> = [
    {
      title: "",
      key: "sort",
      width: 56,
      align: "center",
      render: () => (
        <Tooltip title={t("agent.dragHandleTooltip")}>
          <span>
            <DragHandle disabled={reordering || loading} />
          </span>
        </Tooltip>
      ),
    },
    {
      title: t("agent.name"),
      dataIndex: "name",
      key: "name",
      width: 300,
      render: (_text: string, record: AgentSummary) => (
        <Space>
          <RobotOutlined
            style={{
              fontSize: 16,
              opacity: record.enabled ? 1 : 0.5,
            }}
          />
          <span style={{ opacity: record.enabled ? 1 : 0.5 }}>
            {getAgentDisplayName(record, t)}
          </span>
          {!record.enabled && <Tag color="error">{t("agent.disabled")}</Tag>}
          {record.is_leader && (
            <Tag icon={<CrownOutlined />} color="gold">
              {t("agent.leader", "Leader")}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: t("agent.id"),
      dataIndex: "id",
      key: "id",
    },
    {
      title: t("agent.description"),
      dataIndex: "description",
      key: "description",
      ellipsis: true,
    },
    {
      title: t("agent.workspace"),
      dataIndex: "workspace_dir",
      key: "workspace_dir",
      ellipsis: true,
    },
    {
      title: t("common.actions"),
      key: "actions",
      width: 340,
      render: (_: any, record: AgentSummary) => {
        const isDefault = record.id === "default";
        const isLeader = record.is_leader === true;

        return (
          <div className={styles.agentActions}>
            <div className={styles.agentActionsRow}>
              <Space size="small">
                <Button
                  type="text"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => onEdit(record)}
                  disabled={isDefault}
                  style={isDefault ? disabledStyle : iconStyle}
                  title={
                    isDefault
                      ? t("agent.defaultNotEditable")
                      : undefined
                  }
                />
                <Popconfirm
                  title={
                    record.enabled
                      ? t("agent.disableConfirm")
                      : t("agent.enableConfirm")
                  }
                  description={
                    record.enabled
                      ? t("agent.disableConfirmDesc")
                      : t("agent.enableConfirmDesc")
                  }
                  onConfirm={() => onToggle(record.id, record.enabled)}
                  disabled={isDefault}
                  okText={t("common.confirm")}
                  cancelText={t("common.cancel")}
                >
                  <Button
                    type="text"
                    size="small"
                    icon={record.enabled ? <EyeOff size={14} /> : <Eye size={14} />}
                    disabled={isDefault}
                    style={isDefault ? disabledStyle : iconStyle}
                    title={
                      isDefault
                        ? t("agent.defaultNotDisablable")
                        : undefined
                    }
                  />
                </Popconfirm>
                {!isLeader && (
                  <Button
                    type="text"
                    size="small"
                    icon={<CrownOutlined />}
                    onClick={() => onSetLeader(record.id)}
                  >
                    {t("agent.setLeader", "设为 Leader")}
                  </Button>
                )}
              </Space>
            </div>
            <div className={styles.agentActionsRow}>
              <Space size="small">
                {isLeader && (
                  <Popconfirm
                    title={t("agent.removeLeaderConfirm", "确认移除 Leader？")}
                    description={t(
                      "agent.removeLeaderDesc",
                      "这将清除当前的 Leader。请确保没有 Pipeline 正在使用它。"
                    )}
                    onConfirm={() => onRemoveLeader(record.id)}
                    okText={t("common.confirm", "确认")}
                    cancelText={t("common.cancel", "取消")}
                  >
                    <Button
                      type="text"
                      size="small"
                      icon={<CloseCircleOutlined />}
                      danger
                    >
                      {t("agent.removeLeader", "移除 Leader")}
                    </Button>
                  </Popconfirm>
                )}
                <Button
                  type="text"
                  size="small"
                  icon={<ApartmentOutlined />}
                  onClick={() => onOrchestration(record)}
                >
                  {t("agent.orchestration", "智能体编排管理")}
                </Button>
                <Popconfirm
                  title={t("agent.deleteConfirm")}
                  description={t("agent.deleteConfirmDesc")}
                  onConfirm={() => onDelete(record.id)}
                  disabled={isDefault}
                  okText={t("common.confirm")}
                  cancelText={t("common.cancel")}
                >
                  <Button
                    type="link"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    disabled={isDefault}
                    style={isDefault ? disabledStyle : undefined}
                    title={
                      isDefault
                        ? t("agent.defaultNotDeletable")
                        : undefined
                    }
                  />
                </Popconfirm>
              </Space>
            </div>
          </div>
        );
      },
    },
  ];

  return (
    <div className={styles.tableCard}>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={agents.map((agent) => agent.id)}
          strategy={verticalListSortingStrategy}
        >
          <Table
            dataSource={agents}
            columns={columns}
            loading={loading}
            rowKey="id"
            components={{
              body: {
                row: SortableAgentRow,
              },
            }}
            pagination={false}
          />
        </SortableContext>
      </DndContext>
    </div>
  );
}

import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  message,
  Switch,
  Space,
  Spin,
  Tag,
  Descriptions,
  Alert,
  Divider,
  Modal,
  Typography,
  Collapse,
} from "antd";
import { ClockCircleOutlined, CloudOutlined, SyncOutlined, CheckCircleOutlined, ExclamationCircleOutlined, FileOutlined, FolderOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import api from "../../../api";
import { useAgentStore } from "../../../stores/agentStore";
import type { BackupConfig, BackupStatus, BackupResult } from "../../../api/types/backup";
import { PageHeader } from "@/components/PageHeader";
import styles from "./index.module.less";

const { Text } = Typography;

function BackupPage() {
  const { t } = useTranslation();
  const { selectedAgent } = useAgentStore();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingConnection, setTestConnection] = useState(false);
  const [backingUp, setBackingUp] = useState(false);
  const [form] = Form.useForm<BackupConfig>();
  const [status, setStatus] = useState<BackupStatus | null>(null);
  const [connectionTest, setConnectionTest] = useState<{ success: boolean; message: string } | null>(null);
  const [backupResult, setBackupResult] = useState<BackupResult | null>(null);
  const [resultModalOpen, setResultModalOpen] = useState(false);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const data = await api.getBackupConfig();
      form.setFieldsValue(data);
    } catch (e) {
      console.error("Failed to load backup config:", e);
      message.error(t("backup.loadFailed"));
    } finally {
      setLoading(false);
    }
  };

  const fetchStatus = async () => {
    try {
      const data = await api.getBackupStatus();
      setStatus(data);
    } catch (e) {
      console.error("Failed to load backup status:", e);
    }
  };

  useEffect(() => {
    fetchConfig();
    fetchStatus();
  }, [selectedAgent]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const values = await form.validateFields();
      await api.updateBackupConfig(values);
      message.success(t("backup.saveSuccess"));
    } catch (e) {
      console.error("Failed to save backup config:", e);
      message.error(t("backup.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTestConnection(true);
    setConnectionTest(null);
    try {
      const result = await api.testConnection();
      setConnectionTest(result);
      if (result.success) {
        message.success(result.message);
      } else {
        message.error(result.message);
      }
    } catch (e) {
      console.error("Connection test failed:", e);
      setConnectionTest({ success: false, message: "Connection failed" });
      message.error(t("backup.connectionFailed"));
    } finally {
      setTestConnection(false);
    }
  };

  const handleTriggerBackup = async (full: boolean) => {
    setBackingUp(true);
    try {
      const result: BackupResult = await api.triggerBackup(full);
      setBackupResult(result);
      setResultModalOpen(true);
      if (result.success) {
        fetchStatus();
      }
    } catch (e) {
      console.error("Backup failed:", e);
      message.error(t("backup.backupFailed"));
    } finally {
      setBackingUp(false);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  const formatDateTime = (isoString: string | null) => {
    if (!isoString) return "-";
    return new Date(isoString).toLocaleString();
  };

  const renderBackupResultModal = () => (
    <Modal
      title={
        <Space>
          {backupResult?.success ? (
            <CheckCircleOutlined style={{ color: "#52c41a" }} />
          ) : (
            <ExclamationCircleOutlined style={{ color: "#ff4d4f" }} />
          )}
          {backupResult?.message}
        </Space>
      }
      open={resultModalOpen}
      onCancel={() => setResultModalOpen(false)}
      footer={[
        <Button key="close" onClick={() => setResultModalOpen(false)}>
          关闭
        </Button>,
      ]}
      width={700}
    >
      {backupResult && (
        <div>
          <Descriptions column={3} size="small" style={{ marginBottom: 16 }}>
            <Descriptions.Item label="备份文件数">
              <Text strong>{backupResult.files_backed_up}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="耗时">
              <Text>{backupResult.duration_ms} ms</Text>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={backupResult.success ? "success" : "error"}>
                {backupResult.success ? "成功" : "失败"}
              </Tag>
            </Descriptions.Item>
          </Descriptions>

          {/* Shared Files */}
          {backupResult.shared_files.length > 0 && (
            <Card size="small" title={<Space><FolderOutlined /> 共享文件</Space>} style={{ marginBottom: 12 }}>
              <div style={{ maxHeight: 100, overflow: "auto" }}>
                {backupResult.shared_files.map((file, idx) => (
                  <Tag key={idx} icon={<FileOutlined />} style={{ margin: "2px" }}>
                    {file}
                  </Tag>
                ))}
              </div>
            </Card>
          )}

          {/* Agent Files */}
          {backupResult.agents.length > 0 && (
            <Collapse
              size="small"
              defaultActiveKey={backupResult.agents.map(a => a.agent_id)}
              items={backupResult.agents.map((agent) => ({
                key: agent.agent_id,
                label: (
                  <Space>
                    <FolderOutlined />
                    <Text strong>{agent.agent_id}</Text>
                    <Tag color="blue">{agent.bucket}</Tag>
                    <Text type="secondary">({agent.success}/{agent.total} 文件)</Text>
                  </Space>
                ),
                children: (
                  <div>
                    {agent.files_synced.length > 0 && (
                      <div style={{ marginBottom: 8 }}>
                        <Text type="success" strong>已同步 ({agent.files_synced.length})</Text>
                        <div style={{ maxHeight: 150, overflow: "auto", marginTop: 4 }}>
                          {agent.files_synced.map((file, idx) => (
                            <Tag key={idx} color="success" icon={<FileOutlined />} style={{ margin: "2px" }}>
                              {file}
                            </Tag>
                          ))}
                        </div>
                      </div>
                    )}
                    {agent.files_failed.length > 0 && (
                      <div>
                        <Text type="danger" strong>失败 ({agent.files_failed.length})</Text>
                        <div style={{ maxHeight: 100, overflow: "auto", marginTop: 4 }}>
                          {agent.files_failed.map((file, idx) => (
                            <Tag key={idx} color="error" icon={<FileOutlined />} style={{ margin: "2px" }}>
                              {file}
                            </Tag>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ),
              }))}
            />
          )}
        </div>
      )}
    </Modal>
  );

  return (
    <div className={styles.container}>
      <PageHeader
        items={[{ title: t("nav.control") }, { title: t("backup.title") }]}
      />

      {renderBackupResultModal()}

      <Spin spinning={loading}>
        {/* Status Card */}
        {status && (
          <Card
            title={
              <Space>
                <CloudOutlined />
                {t("backup.statusTitle")}
              </Space>
            }
            className={styles.card}
            style={{ marginBottom: 16 }}
          >
            <Descriptions column={2} size="small">
              <Descriptions.Item label={t("backup.lastFullBackup")}>
                {formatDateTime(status.last_full_backup)}
              </Descriptions.Item>
              <Descriptions.Item label={t("backup.lastIncrementalBackup")}>
                {formatDateTime(status.last_incremental_backup)}
              </Descriptions.Item>
              <Descriptions.Item label={t("backup.totalFiles")}>
                {status.total_files}
              </Descriptions.Item>
              <Descriptions.Item label={t("backup.totalSize")}>
                {formatBytes(status.total_size)}
              </Descriptions.Item>
              <Descriptions.Item label={t("backup.buckets")}>
                <Space>
                  {status.buckets.map((b) => (
                    <Tag key={b} color="blue">{b}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
            </Descriptions>
          </Card>
        )}

        {/* Connection Test */}
        {connectionTest && (
          <Alert
            type={connectionTest.success ? "success" : "error"}
            message={connectionTest.message}
            icon={connectionTest.success ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        {/* Configuration Form */}
        <Card
          title={
            <Space>
              <ClockCircleOutlined />
              {t("backup.configTitle")}
            </Space>
          }
          className={styles.card}
        >
          <Form
            form={form}
            layout="vertical"
            initialValues={{
              enabled: false,
              endpoint: "localhost:9000",
              secure: false,
              full_backup_schedule: "0 2 * * *",
              incremental_interval: 3600,
              retention_days: 30,
              dedup_enabled: true,
              compress_dialog: true,
              compress_chats: true,
            }}
          >
            {/* Enable Backup */}
            <Form.Item name="enabled" label={t("backup.enabled")} valuePropName="checked">
              <Switch />
            </Form.Item>

            <Divider>{t("backup.storageSettings")}</Divider>

            {/* MinIO Settings */}
            <Form.Item name="endpoint" label={t("backup.endpoint")}>
              <Input placeholder="localhost:9000" />
            </Form.Item>

            <Form.Item name="access_key" label={t("backup.accessKey")}>
              <Input.Password placeholder={t("backup.accessKeyPlaceholder")} />
            </Form.Item>

            <Form.Item name="secret_key" label={t("backup.secretKey")}>
              <Input.Password placeholder={t("backup.secretKeyPlaceholder")} />
            </Form.Item>

            <Form.Item name="secure" label={t("backup.secure")} valuePropName="checked">
              <Switch />
            </Form.Item>

            {/* Test Connection Button */}
            <Form.Item>
              <Button
                onClick={handleTestConnection}
                loading={testingConnection}
                icon={<SyncOutlined />}
              >
                {t("backup.testConnection")}
              </Button>
            </Form.Item>

            <Divider>{t("backup.scheduleSettings")}</Divider>

            {/* Backup Schedule */}
            <Form.Item
              name="full_backup_schedule"
              label={t("backup.fullBackupSchedule")}
              extra={t("backup.cronHelp")}
            >
              <Input placeholder="0 2 * * *" />
            </Form.Item>

            <Form.Item
              name="incremental_interval"
              label={t("backup.incrementalInterval")}
              extra={t("backup.intervalHelp")}
            >
              <InputNumber min={60} max={86400} step={60} addonAfter="秒" style={{ width: "100%" }} />
            </Form.Item>

            <Form.Item
              name="retention_days"
              label={t("backup.retentionDays")}
            >
              <InputNumber min={1} max={365} addonAfter="天" style={{ width: "100%" }} />
            </Form.Item>

            <Divider>{t("backup.advancedSettings")}</Divider>

            {/* Deduplication */}
            <Form.Item name="dedup_enabled" label={t("backup.dedupEnabled")} valuePropName="checked">
              <Switch />
            </Form.Item>

            {/* Compression */}
            <Form.Item name="compress_dialog" label={t("backup.compressDialog")} valuePropName="checked">
              <Switch />
            </Form.Item>

            <Form.Item name="compress_chats" label={t("backup.compressChats")} valuePropName="checked">
              <Switch />
            </Form.Item>

            {/* Actions */}
            <Form.Item>
              <Space>
                <Button type="primary" onClick={handleSave} loading={saving}>
                  {t("backup.save")}
                </Button>
                <Button
                  onClick={() => handleTriggerBackup(true)}
                  loading={backingUp}
                  type="default"
                  icon={<CloudOutlined />}
                >
                  {t("backup.fullBackupNow")}
                </Button>
                <Button
                  onClick={() => handleTriggerBackup(false)}
                  loading={backingUp}
                  icon={<SyncOutlined />}
                >
                  {t("backup.incrementalBackupNow")}
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </Spin>
    </div>
  );
}

export default BackupPage;
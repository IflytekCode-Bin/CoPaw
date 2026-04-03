export interface BackupConfig {
  enabled: boolean;
  endpoint: string;
  access_key: string;
  secret_key: string;
  secure: boolean;
  full_backup_schedule: string; // cron format
  incremental_interval: number; // seconds
  retention_days: number;
  dedup_enabled: boolean;
  dedup_resources: string[];
  compress_dialog: boolean;
  compress_chats: boolean;
}

export interface BackupStatus {
  last_full_backup: string | null; // ISO datetime
  last_incremental_backup: string | null;
  total_files: number;
  total_size: number; // bytes
  buckets: string[];
}

export interface AgentBackupResult {
  agent_id: string;
  bucket: string;
  files_synced: string[];
  files_failed: string[];
  total: number;
  success: number;
}

export interface BackupResult {
  success: boolean;
  message: string;
  files_backed_up: number;
  duration_ms: number;
  agents: AgentBackupResult[];
  shared_files: string[];
}
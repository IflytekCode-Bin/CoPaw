import { request } from "../request";
import type { BackupConfig, BackupStatus, BackupResult } from "../types/backup";

export const backupApi = {
  /** Get backup configuration */
  getBackupConfig: () => request<BackupConfig>("/config/backup"),

  /** Update backup configuration */
  updateBackupConfig: (body: Partial<BackupConfig>) =>
    request<void>("/config/backup", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  /** Get backup status */
  getBackupStatus: () => request<BackupStatus>("/backup/status"),

  /** Trigger manual backup */
  triggerBackup: (full: boolean = true) =>
    request<BackupResult>("/backup/trigger", {
      method: "POST",
      body: JSON.stringify({ full }),
    }),

  /** Test MinIO connection */
  testConnection: () =>
    request<{ success: boolean; message: string }>("/backup/test-connection", {
      method: "POST",
    }),
};
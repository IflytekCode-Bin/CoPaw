import { request } from "../config";
import type { BackupConfig, BackupStatus, BackupResult } from "../types/backup";

export const backupApi = {
  /** Get backup configuration */
  getConfig: async (): Promise<BackupConfig> => {
    return request.get("/api/backup/config");
  },

  /** Update backup configuration */
  updateConfig: async (config: Partial<BackupConfig>): Promise<void> => {
    return request.put("/api/backup/config", config);
  },

  /** Get backup status */
  getStatus: async (): Promise<BackupStatus> => {
    return request.get("/api/backup/status");
  },

  /** Trigger manual backup */
  triggerBackup: async (full: boolean = true): Promise<BackupResult> => {
    return request.post("/api/backup/trigger", { full });
  },

  /** Test MinIO connection */
  testConnection: async (): Promise<{ success: boolean; message: string }> => {
    return request.post("/api/backup/test-connection");
  },
};
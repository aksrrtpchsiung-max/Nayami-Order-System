/**
 * 文件名称：audit.ts
 * 文件用途：封装操作日志筛选和单条日志详情
 * 主要职责：封装操作日志筛选和单条日志详情
 * 所属业务模块：审计接口
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { http, unwrapResponse } from "./http";
import type { OperationLog } from "../types/domain";

export interface OperationLogFilters {
  operation_module?: string;
  operation_type?: string;
  operation_result?: string;
  operator_id?: number;
  start_at?: string;
  end_at?: string;
  limit?: number;
  store_id?: number;
  operator_role_code?: string;
}

export function listOperationLogsApi(filters: OperationLogFilters = {}) {
  return unwrapResponse<OperationLog[]>(http.get("/audit/logs", { params: filters }));
}

export function getOperationLogApi(id: number) {
  return unwrapResponse<OperationLog>(http.get(`/audit/logs/${id}`));
}

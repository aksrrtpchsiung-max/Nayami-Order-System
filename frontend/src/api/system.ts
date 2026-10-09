/**
 * 文件名称：system.ts
 * 文件用途：封装实际配置读取及可编辑项维护
 * 主要职责：封装实际配置读取及可编辑项维护
 * 所属业务模块：系统接口
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { http, unwrapResponse } from "./http";
import type { SystemConfig } from "../types/domain";

export function getSystemConfigApi() {
  return unwrapResponse<SystemConfig>(http.get("/system/config"));
}

export function updateSystemConfigApi(payload: Pick<SystemConfig, "demo_mode" | "default_language" | "payment_description">) {
  return unwrapResponse<SystemConfig>(http.patch("/system/config", payload));
}

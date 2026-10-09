/**
 * 文件名称：inventory.ts
 * 文件用途：封装库存维护及门店库存变更记录查询
 * 主要职责：封装库存维护及门店库存变更记录查询
 * 所属业务模块：库存接口
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { http, unwrapResponse } from "./http";
import type { StoreInventoryItem, UpdateStoreInventoryPayload } from "../types/domain";

export function listStoreInventoryApi(storeId: number) {
  return unwrapResponse<StoreInventoryItem[]>(http.get("/store/inventory", { params: { store_id: storeId } }));
}

export function updateStoreInventoryApi(storeProductId: number, payload: UpdateStoreInventoryPayload) {
  return unwrapResponse<StoreInventoryItem>(http.patch(`/store/inventory/${storeProductId}`, payload));
}

export function listInventoryLogsApi(storeId: number, storeProductId?: number, days = 7, changeType?: string) {
  return unwrapResponse<import("../types/domain").InventoryLog[]>(http.get("/store/inventory/logs", {params:{store_id:storeId,store_product_id:storeProductId,days,change_type:changeType}}));
}

/**
 * 文件名称：orders.ts
 * 文件用途：封装顾客订单、门店查询和顺序履约请求
 * 主要职责：封装顾客订单、门店查询和顺序履约请求
 * 所属业务模块：订单接口
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { http, unwrapResponse } from "./http";
import type { OrderDetail } from "../types/domain";

export interface CreateOrderPayload {
  store_id: number;
  order_type: "dine_in" | "pickup";
  tableware_count: number;
  remark?: string;
  user_coupon_id?: number;
  items: Array<{
    store_product_id: number;
    quantity: number;
  }>;
}

export function createOrderApi(payload: CreateOrderPayload) {
  return unwrapResponse<OrderDetail>(http.post("/orders", payload));
}

export function getOrderApi(orderId: number) {
  return unwrapResponse<OrderDetail>(http.get(`/orders/${orderId}`));
}

export function listCustomerOrdersApi(status?: string) {
  return unwrapResponse<OrderDetail[]>(http.get("/orders", { params: status ? { status } : {} }));
}

export function cancelOrderApi(orderId: number) {
  return unwrapResponse<OrderDetail>(http.post(`/orders/${orderId}/cancel`));
}

export function listStoreOrdersApi(storeId: number, status?: string, filters: {view?: string; days?: number; search?: string} = {}) {
  const params = { store_id: storeId, status, ...filters };
  return unwrapResponse<OrderDetail[]>(http.get("/store/orders", { params }));
}

export function updateStoreOrderStatusApi(orderId: number, targetStatus: string, pickupCode?: string) {
  return unwrapResponse<OrderDetail>(
    http.post(`/store/orders/${orderId}/status`, {
      target_status: targetStatus,
      pickup_code: pickupCode
    })
  );
}

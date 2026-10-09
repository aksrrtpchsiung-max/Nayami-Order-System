/**
 * 文件名称：coupons.ts
 * 文件用途：封装领取、资格校验和异步任务详情重试
 * 主要职责：封装领取、资格校验和异步任务详情重试
 * 所属业务模块：优惠券接口
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { http, unwrapResponse } from "./http";
import type {
  CouponClaimResult,
  CouponClaimTask,
  PublicCouponActivity,
  UserCoupon
} from "../types/domain";

export function listCouponActivitiesApi() {
  return unwrapResponse<PublicCouponActivity[]>(http.get("/coupons/activities"));
}

export function claimCouponApi(activityId: number) {
  return unwrapResponse<CouponClaimResult>(
    http.post(`/coupons/activities/${activityId}/claim`, {
      request_id: `web-${activityId}-${Date.now()}`
    })
  );
}

export function listMyCouponsApi(status?: string) {
  return unwrapResponse<UserCoupon[]>(http.get("/coupons/me", { params: status ? { status } : {} }));
}

export function listEligibleCouponsApi(storeId: number, itemsAmount: number, productIds: number[]) {
  return unwrapResponse<UserCoupon[]>(
    http.get("/coupons/eligible", {
      params: {
        store_id: storeId,
        items_amount: itemsAmount.toFixed(2),
        product_ids: productIds.join(",")
      }
    })
  );
}

export function warmupCouponActivityApi(activityId: number, force = false) {
  return unwrapResponse<{ activity_id: number; remaining_stock: number }>(
    http.post(`/coupons/activities/${activityId}/warmup`, { force })
  );
}

export function listCouponClaimTasksApi(activityId: number, status?: string) {
  return unwrapResponse<CouponClaimTask[]>(
    http.get(`/coupons/activities/${activityId}/tasks`, { params: status ? { status } : {} })
  );
}

export function retryCouponClaimTaskApi(taskId: number) {
  return unwrapResponse<CouponClaimTask>(http.post(`/coupons/tasks/${taskId}/retry`));
}

export function reconcileCouponActivityApi(activityId: number) {
  return unwrapResponse<Record<string, number>>(http.post(`/coupons/activities/${activityId}/reconcile`));
}

export function getCouponClaimTaskApi(taskId: number) {
  return unwrapResponse<CouponClaimTask>(http.get(`/coupons/tasks/${taskId}`));
}

import { http, unwrapResponse } from "./http";
import type {
  BrandOverview,
  BrandProduct,
  BrandProductPayload,
  BrandReport,
  BrandStoreProduct,
  CouponActivity,
  CouponActivityPayload,
  CouponMetrics,
  ProductCategory,
  ProductCategoryPayload,
  StoreProductPayload,
  StoreSummary,
  UpdateStoreStatusPayload
} from "../types/domain";

export function getBrandOverviewApi() {
  return unwrapResponse<BrandOverview>(http.get("/brand/overview"));
}

export function getBrandReportApi() {
  return unwrapResponse<BrandReport>(http.get("/brand/report"));
}

export function listBrandStoresApi() {
  return unwrapResponse<StoreSummary[]>(http.get("/brand/stores"));
}

export function createBrandStoreApi(payload: Partial<StoreSummary> & UpdateStoreStatusPayload) {
  return unwrapResponse<StoreSummary>(http.post("/brand/stores", payload));
}

export function updateBrandStoreApi(storeId: number, payload: Partial<StoreSummary> & Partial<UpdateStoreStatusPayload>) {
  return unwrapResponse<StoreSummary>(http.patch(`/brand/stores/${storeId}`, payload));
}

export function listCategoriesApi() {
  return unwrapResponse<ProductCategory[]>(http.get("/brand/categories"));
}

export function createCategoryApi(payload: ProductCategoryPayload) {
  return unwrapResponse<ProductCategory>(http.post("/brand/categories", payload));
}

export function updateCategoryApi(categoryId: number, payload: Partial<ProductCategoryPayload>) {
  return unwrapResponse<ProductCategory>(http.patch(`/brand/categories/${categoryId}`, payload));
}

export function listProductsApi() {
  return unwrapResponse<BrandProduct[]>(http.get("/brand/products"));
}

export function createProductApi(payload: BrandProductPayload) {
  return unwrapResponse<BrandProduct>(http.post("/brand/products", payload));
}

export function updateProductApi(productId: number, payload: Partial<BrandProductPayload>) {
  return unwrapResponse<BrandProduct>(http.patch(`/brand/products/${productId}`, payload));
}

export function listBrandStoreProductsApi(storeId?: number) {
  return unwrapResponse<BrandStoreProduct[]>(http.get("/brand/store-products", { params: { store_id: storeId } }));
}

export function upsertStoreProductApi(payload: StoreProductPayload) {
  return unwrapResponse<BrandStoreProduct>(http.post("/brand/store-products", payload));
}

export function updateBrandStoreProductApi(storeProductId: number, payload: StoreProductPayload) {
  return unwrapResponse<BrandStoreProduct>(http.patch(`/brand/store-products/${storeProductId}`, payload));
}

export function listCouponsApi() {
  return unwrapResponse<CouponActivity[]>(http.get("/brand/coupons"));
}

export function createCouponApi(payload: CouponActivityPayload) {
  return unwrapResponse<CouponActivity>(http.post("/brand/coupons", payload));
}

export function updateCouponApi(activityId: number, payload: Partial<CouponActivityPayload>) {
  return unwrapResponse<CouponActivity>(http.patch(`/brand/coupons/${activityId}`, payload));
}

export function getCouponMetricsApi(activityId: number) {
  return unwrapResponse<CouponMetrics>(http.get(`/brand/coupons/${activityId}/metrics`));
}

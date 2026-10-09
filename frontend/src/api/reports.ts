import { http, unwrapResponse } from "./http";
import type { StoreOverview, StoreReport } from "../types/domain";

export function getStoreOverviewApi(storeId: number) {
  return unwrapResponse<StoreOverview>(http.get("/store/overview", { params: { store_id: storeId } }));
}

export function getStoreReportApi(storeId: number) {
  return unwrapResponse<StoreReport>(http.get("/store/report", { params: { store_id: storeId } }));
}

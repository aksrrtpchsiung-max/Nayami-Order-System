import { http, unwrapResponse } from "./http";
import type { StoreSummary, UpdateStoreStatusPayload } from "../types/domain";

export function listStoresApi() {
  return unwrapResponse<StoreSummary[]>(http.get("/stores"));
}

export function updateStoreStatusApi(storeId: number, payload: UpdateStoreStatusPayload) {
  return unwrapResponse<StoreSummary>(http.patch(`/store/status/${storeId}`, payload));
}

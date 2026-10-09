import { http, unwrapResponse } from "./http";
import type { StoreMenu } from "../types/domain";

export function getStoreMenuApi(storeId: number) {
  return unwrapResponse<StoreMenu>(http.get(`/catalog/stores/${storeId}/menu`));
}

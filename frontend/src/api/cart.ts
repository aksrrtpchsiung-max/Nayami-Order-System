import { http, unwrapResponse } from "./http";

export interface SessionCartItem {
  store_product_id: number;
  quantity: number;
}

export function listCartItemsApi() {
  return unwrapResponse<SessionCartItem[]>(http.get("/cart/items"));
}

export function addCartItemApi(storeProductId: number, quantity = 1) {
  return unwrapResponse<SessionCartItem[]>(
    http.post("/cart/items", { store_product_id: storeProductId, quantity })
  );
}

export function updateCartItemApi(storeProductId: number, quantity: number) {
  return unwrapResponse<SessionCartItem[]>(
    http.patch(`/cart/items/${storeProductId}`, { quantity })
  );
}

export function removeCartItemApi(storeProductId: number) {
  return unwrapResponse<SessionCartItem[]>(http.delete(`/cart/items/${storeProductId}`));
}

export function clearCartItemsApi() {
  return unwrapResponse<SessionCartItem[]>(http.delete("/cart/items"));
}

/**
 * 文件名称：cartStore.ts
 * 文件用途：持久化门店商品与数量、处理清空和减零移除
 * 主要职责：持久化门店商品与数量、处理清空和减零移除
 * 所属业务模块：购物车
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CartItem, MenuProduct } from "../types/domain";

interface CartState {
  storeId: number | null;
  items: CartItem[];
  addItem: (storeId: number, product: MenuProduct) => void;
  updateQuantity: (storeProductId: number, quantity: number) => void;
  removeItem: (storeProductId: number) => void;
  clearCart: () => void;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      storeId: null,
      items: [],
      addItem: (storeId, product) => {
        if (!product.can_add_to_cart) return;
        const currentState = get();
        const currentItems = currentState.storeId && currentState.storeId !== storeId ? [] : currentState.items;
        const existingItem = currentItems.find((item) => item.storeProductId === product.store_product_id);
        if (existingItem) {
          set({
            storeId,
            items: currentItems.map((item) =>
              item.storeProductId === product.store_product_id
                ? { ...item, quantity: Math.min(item.quantity + 1, product.available_stock ?? 99) }
                : item
            )
          });
          return;
        }
        set({
          storeId,
          items: [
            ...currentItems,
            {
              storeProductId: product.store_product_id,
              productId: product.product_id,
              storeId,
              nameZh: product.name_zh,
              nameEn: product.name_en,
              price: product.base_price,
              quantity: 1,
              availableStock: product.available_stock ?? 99,
              imageUrl: product.image_url
            }
          ]
        });
      },
      updateQuantity: (storeProductId, quantity) => {
        if (!Number.isInteger(quantity) || quantity < 0) return;
        if (quantity === 0) { get().removeItem(storeProductId); return; }
        set({
          items: get().items.map((item) =>
            item.storeProductId === storeProductId
              ? { ...item, quantity: Math.max(1, Math.min(quantity, item.availableStock)) }
              : item
          )
        });
      },
      removeItem: (storeProductId) => {
        const nextItems = get().items.filter((item) => item.storeProductId !== storeProductId);
        set({ items: nextItems, storeId: nextItems.length ? get().storeId : null });
      },
      clearCart: () => set({ items: [], storeId: null })
    }),
    { name: "nayami_cart" }
  )
);

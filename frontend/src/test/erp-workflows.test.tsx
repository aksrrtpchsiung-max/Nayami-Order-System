/**
 * 文件名称：erp-workflows.test.tsx
 * 文件用途：验证传统 ERP 顾客操作与安全边界
 * 主要职责：覆盖登录回跳、关店浏览、购物车重校验、减零删除与取消单支付保护
 * 所属业务模块：前端自动化测试
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getStoreMenuApi } from "../api/catalog";
import { listEligibleCouponsApi } from "../api/coupons";
import { createOrderApi } from "../api/orders";
import { getPaymentApi, simulatePaymentApi } from "../api/payments";
import { safeReturnPath, returnPathForUser } from "../components/LoginRedirect";
import {
  CheckoutPage,
  checkoutItemsValid,
} from "../pages/customer/CheckoutPage";
import { MenuPage } from "../pages/customer/MenuPage";
import { PaymentPage } from "../pages/customer/PaymentPage";
import { useAuthStore } from "../stores/authStore";
import { useCartStore } from "../stores/cartStore";
import i18next from "../i18n";
import type {
  CartItem,
  OrderDetail,
  PaymentDetail,
  StoreMenu,
  UserProfile,
} from "../types/domain";

vi.mock("../api/catalog", () => ({ getStoreMenuApi: vi.fn() }));
vi.mock("../api/coupons", () => ({ listEligibleCouponsApi: vi.fn() }));
vi.mock("../api/orders", () => ({ createOrderApi: vi.fn() }));
vi.mock("../api/payments", () => ({
  getPaymentApi: vi.fn(),
  simulatePaymentApi: vi.fn(),
  retryPaymentApi: vi.fn(),
}));

const customer: UserProfile = {
  id: 81,
  username: "customer",
  user_type: "customer",
  default_language: "en-US",
  roles: [],
  store_bindings: [],
};
const item: CartItem = {
  storeProductId: 15,
  productId: 5,
  storeId: 3,
  nameZh: "测试餐品",
  nameEn: "Test meal",
  price: "20.00",
  quantity: 2,
  availableStock: 99,
};
const menu: StoreMenu = {
  store: {
    id: 3,
    store_code: "S3",
    name_zh: "测试门店",
    name_en: "Test store",
    address: "Test address",
    phone: "12345678",
    business_start_time: "00:00",
    business_end_time: "23:59",
    store_status: "open",
    is_active: true,
    can_order: true,
  },
  categories: [
    {
      id: 1,
      name_zh: "餐品",
      name_en: "Meals",
      products: [
        {
          store_product_id: 15,
          product_id: 5,
          name_zh: "测试餐品",
          name_en: "Test meal",
          base_price: "20.00",
          is_sold_out: false,
          can_add_to_cart: true,
        },
      ],
    },
  ],
};
const order: OrderDetail = {
  id: 4,
  order_no: "ORDER4",
  user_id: 81,
  store_id: 3,
  store_name_en: "Test store",
  order_type: "pickup",
  order_status: "pending_payment",
  items_amount: "40.00",
  discount_amount: "0.00",
  payable_amount: "40.00",
  tableware_count: 1,
  payment_deadline: "2099-01-01 12:00:00",
  created_at: "2026-09-08 10:00:00",
  items: [],
  payment: {
    id: 12,
    payment_no: "PAY12",
    payment_method: "wechat",
    payment_amount: "40.00",
    payment_status: "pending",
  },
};

function LocationResult() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.pathname}
      {location.search}
    </output>
  );
}
function renderPage(
  page: JSX.Element,
  route = "/en/checkout",
  pattern = "/en/checkout",
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path={pattern} element={page} />
          <Route path="*" element={<LocationResult />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, client };
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18next.changeLanguage("en-US");
  useAuthStore.setState({ user: customer, accessToken: "test" });
  useCartStore.setState({ storeId: 3, items: [{ ...item }] });
  vi.mocked(getStoreMenuApi).mockResolvedValue(structuredClone(menu));
  vi.mocked(listEligibleCouponsApi).mockResolvedValue([]);
  vi.mocked(createOrderApi).mockResolvedValue(order);
});
afterEach(() => {
  cleanup();
  useCartStore.getState().clearCart();
});

describe("safe authentication return", () => {
  it("keeps an exact localized payment or checkout goal", () => {
    expect(safeReturnPath("/en/pay/12?from=orders#result", "/en/stores")).toBe(
      "/en/pay/12?from=orders#result",
    );
    expect(safeReturnPath("/zh/checkout", "/zh/stores")).toBe("/zh/checkout");
  });
  it.each([
    "https://evil.test",
    "//evil.test",
    "/\\evil.test",
    "javascript:alert(1)",
    "/en/../login",
    "/en/%2f%2fevil.test",
    "/en/checkout%252f%252fevil.test",
  ])("rejects unsafe return target %s", (value) => {
    expect(safeReturnPath(value, "/en/stores")).toBe("/en/stores");
  });
  it("keeps staff and customer return targets within their respective workflows", () => {
    const staff: UserProfile = {
      ...customer,
      user_type: "staff",
      roles: [{ role_code: "store_staff", role_name: "Staff" }],
    };
    expect(
      returnPathForUser("/en/orders/1", staff, "/en/store/workspace"),
    ).toBe("/en/store/workspace");
    expect(
      returnPathForUser("/en/system/workspace", customer, "/en/stores"),
    ).toBe("/en/stores");
    expect(returnPathForUser("/en/checkout", customer, "/en/stores")).toBe(
      "/en/checkout",
    );
  });
  it("remembers checkout through the login redirect without fetching private data", async () => {
    useAuthStore.setState({ user: null });
    renderPage(<CheckoutPage />);
    await waitFor(() =>
      expect(screen.getByTestId("location").textContent).toBe(
        "/en/login?returnTo=%2Fen%2Fcheckout",
      ),
    );
    expect(listEligibleCouponsApi).not.toHaveBeenCalled();
  });
});

describe("menu and checkout", () => {
  it("allows a closed store to be browsed while blocking add-to-cart and hiding numeric stock", async () => {
    const closed = structuredClone(menu);
    closed.store.can_order = false;
    closed.categories[0].products[0] = {
      ...closed.categories[0].products[0],
      available_stock: 777,
      current_stock: 888,
    };
    vi.mocked(getStoreMenuApi).mockResolvedValue(closed);
    renderPage(<MenuPage />, "/en/stores/3/menu", "/en/stores/:storeId/menu");
    expect(await screen.findByText("Test meal")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add to cart/ })).toBeDisabled();
    expect(screen.queryByText(/777|888/)).not.toBeInTheDocument();
  });
  it("removes the last cart line when quantity reaches zero", async () => {
    renderPage(<CheckoutPage />);
    await screen.findByText("Test store");
    fireEvent.change(
      screen.getByRole("spinbutton", { name: "Quantity for Test meal" }),
      { target: { value: "0" } },
    );
    await waitFor(() => expect(useCartStore.getState().items).toEqual([]));
    expect(useCartStore.getState().storeId).toBeNull();
  });
  it("blocks submission when the latest menu marks the product unavailable", async () => {
    const unavailable = structuredClone(menu);
    unavailable.categories[0].products[0].can_add_to_cart = false;
    vi.mocked(getStoreMenuApi).mockResolvedValue(unavailable);
    renderPage(<CheckoutPage />);
    await screen.findByText("Test store");
    expect(
      screen.getByRole("button", {
        name: new RegExp(i18next.t("pages.checkout.submit")),
      }),
    ).toBeDisabled();
    expect(createOrderApi).not.toHaveBeenCalled();
  });
  it("rechecks the store at submit time and preserves the cart if it closes", async () => {
    const closed = structuredClone(menu);
    closed.store.can_order = false;
    vi.mocked(getStoreMenuApi)
      .mockResolvedValueOnce(menu)
      .mockResolvedValue(closed);
    renderPage(<CheckoutPage />);
    const button = await screen.findByRole("button", {
      name: new RegExp(i18next.t("pages.checkout.submit")),
    });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    await waitFor(() => expect(getStoreMenuApi).toHaveBeenCalledTimes(2));
    expect(createOrderApi).not.toHaveBeenCalled();
    expect(useCartStore.getState().items).toHaveLength(1);
  });
  it("does not treat mixed-store or fractional cart quantities as valid", () => {
    expect(checkoutItemsValid([{ ...item, storeId: 9 }], menu)).toBe(false);
    expect(checkoutItemsValid([{ ...item, quantity: 1.5 }], menu)).toBe(false);
    expect(checkoutItemsValid([{ ...item, quantity: 2 }], menu)).toBe(true);
  });
});

describe("payment terminal states", () => {
  it("prevents callbacks on a canceled order even if its original deadline is in the future", async () => {
    const payment: PaymentDetail = {
      ...order.payment!,
      payment_status: "canceled",
      order: { ...order, order_status: "canceled" },
    };
    vi.mocked(getPaymentApi).mockResolvedValue(payment);
    renderPage(<PaymentPage />, "/en/pay/12", "/en/pay/:paymentId");
    const success = await screen.findByRole("button", {
      name: i18next.t("pages.payment.simulateSuccess"),
    });
    expect(success).toBeDisabled();
    expect(
      screen.getByRole("button", {
        name: i18next.t("pages.payment.simulateFailure"),
      }),
    ).toBeDisabled();
    fireEvent.click(success);
    expect(simulatePaymentApi).not.toHaveBeenCalled();
  });
});

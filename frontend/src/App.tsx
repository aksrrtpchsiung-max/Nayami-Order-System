/**
 * 文件名称：App.tsx
 * 文件用途：提供奈亚米前端应用入口与全局路由
 * 主要职责：装配全局 Provider、语言化路由、角色访问守卫、页面懒加载及私有缓存隔离
 * 所属业务模块：前端应用与路由
 * 创建时间：2026-05-21 19:22
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */

import { LoginRedirect } from "./components/LoginRedirect";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Button, Card, Space, Typography } from "antd";
import { lazy, Suspense, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, RouterProvider, createBrowserRouter, useLocation, useParams } from "react-router-dom";
import i18next from "./i18n";
import { buildLocalizedLegacyPath } from "./i18n/routing";
import { AppShell } from "./components/AppShell";
import { useAuthStore } from "./stores/authStore";
import { defaultRouteForUser, isBrandAdmin, isStoreWorkspaceUser, isSystemAdmin } from "./utils/access";

const CheckoutPage = lazy(() => import("./pages/customer/CheckoutPage").then((module) => ({ default: module.CheckoutPage })));
const CustomerCenterPage = lazy(() => import("./pages/customer/CustomerCenterPage").then((module) => ({ default: module.CustomerCenterPage })));
const LoginPage = lazy(() => import("./pages/customer/LoginPage").then((module) => ({ default: module.LoginPage })));
const MenuPage = lazy(() => import("./pages/customer/MenuPage").then((module) => ({ default: module.MenuPage })));
const OrderDetailPage = lazy(() => import("./pages/customer/OrderDetailPage").then((module) => ({ default: module.OrderDetailPage })));
const PaymentPage = lazy(() => import("./pages/customer/PaymentPage").then((module) => ({ default: module.PaymentPage })));
const StoreSelectPage = lazy(() => import("./pages/customer/StoreSelectPage").then((module) => ({ default: module.StoreSelectPage })));
const BrandWorkspacePage = lazy(() => import("./pages/brand/BrandWorkspacePage").then((module) => ({ default: module.BrandWorkspacePage })));
const StoreOrdersPage = lazy(() => import("./pages/store/StoreOrdersPage").then((module) => ({ default: module.StoreOrdersPage })));
const SystemWorkspacePage = lazy(() => import("./pages/system/SystemWorkspacePage").then((module) => ({ default: module.SystemWorkspacePage })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1
    }
  }
});

// 身份变化时同步清除私有查询缓存，避免共享浏览器显示上一账号的数据。
useAuthStore.subscribe((state, previous) => {
  if (state.user?.id !== previous.user?.id) queryClient.clear();
});

const router = createBrowserRouter([
  {
    path: "/:language",
    element: (
      <LanguageBoundary>
        <AppShell />
      </LanguageBoundary>
    ),
    children: [
      { index: true, element: <HomeRedirect /> },
      { path: "login", element: <LoginPage /> },
      { path: "stores", element: <StoreSelectPage /> },
      { path: "stores/:storeId/menu", element: <MenuPage /> },
      { path: "checkout", element: <CheckoutPage /> },
      { path: "pay/:paymentId", element: <PaymentPage /> },
      { path: "orders/:orderId", element: <OrderDetailPage /> },
      { path: "me", element: <CustomerCenterPage /> },
      { path: "my/orders", element: <CustomerCenterPage /> },
      { path: "my/coupons", element: <CustomerCenterPage /> },
      { path: "coupons", element: <CustomerCenterPage /> },
      { path: "store", element: <Navigate to="/store/workspace" replace /> },
      {
        path: "store/workspace",
        element: (
          <StoreRouteGuard>
            <StoreOrdersPage />
          </StoreRouteGuard>
        )
      },
      {
        path: "store/orders",
        element: (
          <StoreRouteGuard>
            <StoreOrdersPage />
          </StoreRouteGuard>
        )
      },
      {
        path: "store/unbound",
        element: (
          <StoreRouteGuard requireBinding={false}>
            <StoreUnboundPage />
          </StoreRouteGuard>
        )
      },
      { path: "brand", element: <Navigate to="/brand/workspace" replace /> },
      {
        path: "brand/workspace",
        element: (
          <BrandRouteGuard>
            <BrandWorkspacePage />
          </BrandRouteGuard>
        )
      },
      { path: "system", element: <Navigate to="/system/workspace" replace /> },
      {
        path: "system/workspace",
        element: (
          <SystemRouteGuard>
            <SystemWorkspacePage />
          </SystemRouteGuard>
        )
      }
    ]
  },
  { path: "*", element: <LegacyLanguageRedirect /> }
]);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<div className="center-page">Loading…</div>}>
        <RouterProvider router={router} />
      </Suspense>
    </QueryClientProvider>
  );
}

function HomeRedirect() {
  const user = useAuthStore((state) => state.user);
  const { language } = useParams();
  const destination = user ? defaultRouteForUser(user) : "/stores";
  return <Navigate to={`/${language}${destination}`} replace />;
}

function LanguageBoundary({ children }: { children: JSX.Element }) {
  const { language } = useParams();
  const location = useLocation();
  const normalizedLanguage = language === "en" ? "en-US" : language === "zh" ? "zh-CN" : null;

  useEffect(() => {
    if (normalizedLanguage && i18next.language !== normalizedLanguage) {
      void i18next.changeLanguage(normalizedLanguage);
    }
  }, [normalizedLanguage]);

  if (!normalizedLanguage) {
    return (
      <Navigate
        to={buildLocalizedLegacyPath(location.pathname, i18next.language, location.search, location.hash)}
        replace
      />
    );
  }
  return children;
}

function LegacyLanguageRedirect() {
  const location = useLocation();
  return (
    <Navigate
      to={buildLocalizedLegacyPath(location.pathname, i18next.language, location.search, location.hash)}
      replace
    />
  );
}

function StoreRouteGuard({ children, requireBinding = true }: { children: JSX.Element; requireBinding?: boolean }) {
  const user = useAuthStore((state) => state.user);
  if (!user) {
    return <LoginRedirect />;
  }
  if (!isStoreWorkspaceUser(user)) {
    return <Navigate to="/stores" replace />;
  }
  if (requireBinding && !user.store_bindings?.[0]) {
    return <Navigate to="/store/unbound" replace />;
  }
  if (!requireBinding && user.store_bindings?.[0]) {
    return <Navigate to="/store/workspace" replace />;
  }
  return children;
}

function BrandRouteGuard({ children }: { children: JSX.Element }) {
  const user = useAuthStore((state) => state.user);
  if (!user) {
    return <LoginRedirect />;
  }
  if (!isBrandAdmin(user) && !isSystemAdmin(user)) {
    return <Navigate to={defaultRouteForUser(user)} replace />;
  }
  return children;
}

function SystemRouteGuard({ children }: { children: JSX.Element }) {
  const user = useAuthStore((state) => state.user);
  if (!user) {
    return <LoginRedirect />;
  }
  if (!isSystemAdmin(user)) {
    return <Navigate to={defaultRouteForUser(user)} replace />;
  }
  return children;
}

function StoreUnboundPage() {
  const { t } = useTranslation();

  return (
    <div className="center-page">
      <Card className="login-panel">
        <Space direction="vertical" size={14} className="full-width">
          <Typography.Text className="page-kicker">{t("pages.unbound.kicker")}</Typography.Text>
          <Typography.Title level={2}>{t("pages.unbound.title")}</Typography.Title>
          <Typography.Paragraph type="secondary">
            {t("pages.unbound.description")}
          </Typography.Paragraph>
          <Button type="primary" href="/login">
            {t("pages.unbound.loginAgain")}
          </Button>
        </Space>
      </Card>
    </div>
  );
}

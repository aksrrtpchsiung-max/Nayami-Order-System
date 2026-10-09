/**
 * 文件名称：AppShell.tsx
 * 文件用途：显示角色导航、语言切换与退出登录入口
 * 主要职责：显示角色导航、语言切换与退出登录入口
 * 所属业务模块：前端布局
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { flushSync } from "react-dom";
import {
  GlobalOutlined,
  ControlOutlined,
  LogoutOutlined,
  SafetyCertificateOutlined,
  ShopOutlined,
  ShoppingCartOutlined,
  GiftOutlined,
  UserOutlined
} from "@ant-design/icons";
import { Badge, Button, Layout, Space, Typography } from "antd";
import { useTranslation } from "react-i18next";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import nayamiLogoUrl from "../assets/nayami-logo.png";
import { logoutApi } from "../api/auth";
import { useAuthStore } from "../stores/authStore";
import { useCartStore } from "../stores/cartStore";
import { defaultRouteForUser, isBrandAdmin, isStoreWorkspaceUser, isSystemAdmin } from "../utils/access";

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuthStore();
  const cartCount = useCartStore((state) => state.items.reduce((sum, item) => sum + item.quantity, 0));
  const isStoreUser = isStoreWorkspaceUser(user);
  const isBrandUser = isBrandAdmin(user);
  const isSystemUser = isSystemAdmin(user);
  const localizedPathname = location.pathname.replace(/^\/(?:zh|en)(?=\/|$)/, "") || "/";
  const isStoreWorkspace = localizedPathname.startsWith("/store");
  const isBrandWorkspace = localizedPathname.startsWith("/brand");
  const isSystemWorkspace = localizedPathname.startsWith("/system");
  const isStoreBrowsing = localizedPathname === "/stores" || localizedPathname.startsWith("/stores/");
  const isAuthPage = localizedPathname === "/login";
  const language = t("language.short");
  const homePath = user ? defaultRouteForUser(user) : "/stores";

  return (
    <Layout className="app-shell">
      <Layout.Header className="top-bar">
        <Link to={homePath} className="brand-mark">
          <img className="brand-logo" src={nayamiLogoUrl} alt="Nayami Bistro" />
          <span>
            <span className="brand-name">Nayami Bistro</span>
            <span className="brand-subtitle">奈亚米</span>
          </span>
        </Link>
        <Space className="top-actions" size={10} wrap>
          {isSystemUser ? (
            <Link to="/system/workspace">
              <Button className="nav-button" type={isSystemWorkspace ? "primary" : "default"} icon={<SafetyCertificateOutlined />}>
                {t("nav.system")}
              </Button>
            </Link>
          ) : isBrandUser ? (
            <Link to="/brand/workspace">
              <Button className="nav-button" type={isBrandWorkspace ? "primary" : "default"} icon={<ControlOutlined />}>
                {t("nav.brand")}
              </Button>
            </Link>
          ) : isStoreUser ? (
            <Link to={homePath}>
              <Button className="nav-button" type={isStoreWorkspace ? "primary" : "default"} icon={<ShopOutlined />}>
                {t("nav.storeWorkspace")}
              </Button>
            </Link>
          ) : (
            <>
              <Link to="/stores">
                <Button className="nav-button" type={isStoreBrowsing ? "primary" : "default"} icon={<ShopOutlined />}>
                  {t("nav.stores")}
                </Button>
              </Link>
              <Link to="/checkout">
                <Badge count={cartCount} size="small" offset={[-4, 4]}>
                  <Button className="nav-button" icon={<ShoppingCartOutlined />}>
                    {t("nav.cart")}
                  </Button>
                </Badge>
              </Link>
              {user ? (
                <>
                  <Link to="/coupons">
                    <Button className="nav-button" icon={<GiftOutlined />}>
                      {t("nav.couponCenter")}
                    </Button>
                  </Link>
                  <Link to="/me">
                    <Button className="nav-button" icon={<UserOutlined />}>
                      {t("nav.myOrders")}
                    </Button>
                  </Link>
                </>
              ) : null}
            </>
          )}
          <Button
            className="icon-button"
            icon={<GlobalOutlined />}
            aria-label={t("language.switch")}
            onClick={() => {
              const nextLanguage = i18n.language === "en-US" ? "zh-CN" : "en-US";
              const nextPrefix = nextLanguage === "en-US" ? "en" : "zh";
              const nextPath = `/${nextPrefix}${localizedPathname}${location.search}${location.hash}`;
              void i18n.changeLanguage(nextLanguage);
              navigate(nextPath, { replace: true });
            }}
          >
            {language}
          </Button>
          {user ? (
            <>
              <Typography.Text className="top-user">
                <UserOutlined /> {user.username}
              </Typography.Text>
              <Button
                className="icon-button"
                icon={<LogoutOutlined />}
                onClick={() => {
                  void logoutApi().catch(() => undefined);
                  flushSync(() => navigate(`/${i18n.language === "en-US" ? "en" : "zh"}/login`, { replace: true }));
                  logout();
                }}
              />
            </>
          ) : isAuthPage ? null : (
            <Link to="/login">
              <Button className="nav-button" type="primary">
                {t("nav.auth")}
              </Button>
            </Link>
          )}
        </Space>
      </Layout.Header>
      <Layout.Content className="page-content">
        <Outlet />
      </Layout.Content>
    </Layout>
  );
}

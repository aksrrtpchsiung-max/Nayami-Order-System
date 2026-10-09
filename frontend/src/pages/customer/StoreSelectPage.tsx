/**
 * 文件名称：StoreSelectPage.tsx
 * 文件用途：展示营业信息、选择门店并允许关店菜单浏览
 * 主要职责：展示营业信息、选择门店并允许关店菜单浏览
 * 所属业务模块：门店选择
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
/*
 * 文件名称：StoreSelectPage.tsx
 * 文件用途：展示顾客端门店选择页
 * 主要职责：加载可用门店、突出推荐门店、展示营业信息并处理跨门店购物车切换
 * 所属业务模块：顾客端门店选择
 * 创建时间：2026-05-22 16:12
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */

import { ClockCircleOutlined, EnvironmentOutlined, PhoneOutlined, RightOutlined, ShopOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Col, Empty, Modal, Row, Skeleton, Space, Typography } from "antd";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { listStoresApi } from "../../api/stores";
import { localizedText } from "../../i18n/localizedText";
import { useCartStore } from "../../stores/cartStore";

export function StoreSelectPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { storeId: cartStoreId, items: cartItems, clearCart } = useCartStore();
  const { data, isLoading } = useQuery({ queryKey: ["stores"], queryFn: listStoresApi });
  const stores = data ?? [];
  const availableStores = stores.filter((store) => store.can_order);
  const recommendedStore = availableStores[0] ?? stores[0];

  if (isLoading) {
    return <Skeleton active />;
  }

  function openStoreMenu(storeId: number) {
    if (cartItems.length && cartStoreId && cartStoreId !== storeId) {
      Modal.confirm({
        title: t("messages.storeSwitchTitle"),
        content: t("messages.storeSwitchWarning"),
        okText: t("common.clear"),
        cancelText: t("common.cancel"),
        onOk: () => {
          clearCart();
          navigate(`/stores/${storeId}/menu`);
        }
      });
      return;
    }
    navigate(`/stores/${storeId}/menu`);
  }

  return (
    <Space direction="vertical" size={24} className="full-width">
      <section className="store-entry">
        <div className="store-entry-main">
          <div className="entry-eyebrow">
            <span>{t("pages.stores.eyebrowBrand")}</span>
            <span>{t("common.storeCountOrderable", { count: availableStores.length })}</span>
          </div>
          <div className="store-entry-copy">
            <Typography.Title level={1}>{t("pages.stores.title")}</Typography.Title>
            <Typography.Paragraph>{t("pages.stores.description")}</Typography.Paragraph>
          </div>
          <div className="store-entry-actions">
            <Button
              type="primary"
              size="large"
              icon={<ShopOutlined />}
              disabled={!recommendedStore}
              onClick={() => recommendedStore && openStoreMenu(recommendedStore.id)}
            >
              {t("pages.stores.enterRecommended")}
            </Button>
          </div>
        </div>
        <div className="store-entry-board">
          <div className="recommended-store">
            <div>
              <span className="recommended-store-label">{t("pages.stores.recommendedStore")}</span>
              <strong>{recommendedStore ? localizedText(recommendedStore.name_zh, recommendedStore.name_en, i18n.language) : t("pages.stores.noRecommendedStore")}</strong>
              <span>{recommendedStore?.address ?? t("pages.stores.seedStoresHint")}</span>
            </div>
            {recommendedStore ? (
              <Button
                type="link"
                icon={<RightOutlined />}
                iconPosition="end"
                disabled={!recommendedStore.is_active}
                onClick={() => openStoreMenu(recommendedStore.id)}
              >
                {t("pages.stores.viewMenu")}
              </Button>
            ) : null}
          </div>
        </div>
      </section>

      <div className="section-header">
        <div>
          <Typography.Title level={2}>{t("pages.stores.networkTitle")}</Typography.Title>
          <Typography.Text type="secondary">{t("pages.stores.networkDescription")}</Typography.Text>
        </div>
      </div>
      {!data?.length ? <Empty description={t("pages.stores.empty")} /> : null}
      <Row gutter={[18, 18]}>
        {data?.map((store) => (
          <Col xs={24} md={12} lg={8} key={store.id}>
            <Card className="store-card">
              <div className="store-card-cover">
                <span>{store.store_code}</span>
                <strong>{store.can_order ? t("pages.stores.open") : t("pages.stores.paused")}</strong>
              </div>
              <Space direction="vertical" size={12} className="full-width">
                <div>
                  <Typography.Title level={3}>{localizedText(store.name_zh, store.name_en, i18n.language)}</Typography.Title>
                  <Typography.Text type="secondary">{store.store_code}</Typography.Text>
                </div>
                <Space direction="vertical" size={6}>
                  <Typography.Text>
                    <EnvironmentOutlined /> {store.address}
                  </Typography.Text>
                  <Typography.Text type="secondary">
                    <ClockCircleOutlined /> {store.business_start_time}-{store.business_end_time} · {t(`status.store.${store.store_status}`, { defaultValue: store.store_status })}
                  </Typography.Text>
                  {store.phone ? (
                    <Typography.Text type="secondary">
                      <PhoneOutlined /> {store.phone}
                    </Typography.Text>
                  ) : null}
                </Space>
                <Button
                  block
                  type="primary"
                  icon={<ShopOutlined />}
                  disabled={!store.is_active}
                  onClick={() => openStoreMenu(store.id)}
                >
                  {t("pages.stores.enterMenu")}
                </Button>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </Space>
  );
}

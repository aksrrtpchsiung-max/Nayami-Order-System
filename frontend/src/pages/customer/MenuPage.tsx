/**
 * 文件名称：MenuPage.tsx
 * 文件用途：展示双语商品详情、禁止关店加购与切店购物车确认
 * 主要职责：展示双语商品详情、禁止关店加购与切店购物车确认
 * 所属业务模块：顾客菜单
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { useState } from "react";
import type { MenuProduct } from "../../types/domain";
import { FireOutlined, ShoppingCartOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, Col, Alert, Empty, Modal, Row, Skeleton, Space, Typography, message } from "antd";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router-dom";
import { getStoreMenuApi } from "../../api/catalog";
import { MoneyText } from "../../components/MoneyText";
import { localizedText } from "../../i18n/localizedText";
import { useCartStore } from "../../stores/cartStore";

export function MenuPage() {
  const { t, i18n } = useTranslation();
  const params = useParams();
  const storeId = Number(params.storeId);
  const [selectedProduct,setSelectedProduct]=useState<MenuProduct>();
  const addItem = useCartStore((state) => state.addItem);
  const cartItems = useCartStore((state) => state.items);
  const { data, isLoading } = useQuery({
    queryKey: ["store-menu", storeId],
    queryFn: () => getStoreMenuApi(storeId),
    enabled: Boolean(storeId)
  });

  if (isLoading) {
    return <Skeleton active />;
  }

  return (
    <Space direction="vertical" size={24} className="full-width">
      <section className="menu-heading">
        <div>
          <Typography.Text className="page-kicker">{t("pages.menu.kicker")}</Typography.Text>
          <Typography.Title level={1}>{data?.store ? localizedText(data.store.name_zh, data.store.name_en, i18n.language) : ""}</Typography.Title>
          <Typography.Paragraph>
            {data?.store.address} · {data?.store.business_start_time}-{data?.store.business_end_time}
          </Typography.Paragraph>
        </div>
        <Link to="/checkout">
          <Button className="checkout-float-button" type="primary" size="large" icon={<ShoppingCartOutlined />} disabled={!cartItems.length}>
            {t("pages.menu.checkout", { count: cartItems.length })}
          </Button>
        </Link>
      </section>
      {data && !data.store.can_order ? <Alert type="warning" showIcon message={t("erp.closedBrowse")} description={data.store.temporary_close_reason} /> : null}
      {!data?.categories.length ? <Empty description={t("pages.menu.empty")} /> : null}
      {data?.categories.map((category) => (
        <section className="menu-section" key={category.id}>
          <div className="category-heading">
            <Typography.Title level={2}>{localizedText(category.name_zh, category.name_en, i18n.language)}</Typography.Title>
            <Typography.Text type="secondary">#{category.id}</Typography.Text>
          </div>
          <Row gutter={[18, 18]}>
            {category.products.map((product) => (
              <Col xs={24} md={12} xl={8} key={product.store_product_id}>
                <Card
                  className="menu-card"
                  cover={product.image_url ? <img alt={localizedText(product.name_zh, product.name_en, i18n.language)} src={product.image_url} /> : undefined}
                >
                  <Space direction="vertical" size={12} className="full-width">
                    <div className="row-between">
                      <Typography.Text className={product.can_add_to_cart ? "product-state" : "product-state danger"}>
                        <FireOutlined /> {product.can_add_to_cart ? t("pages.menu.available") : t("pages.menu.unavailable")}
                      </Typography.Text>
                      <Typography.Text type="secondary">#{product.product_id}</Typography.Text>
                    </div>
                    <div>
                      <Typography.Title level={3}>{localizedText(product.name_zh, product.name_en, i18n.language)}</Typography.Title>
                      <Typography.Text type="secondary">#{product.product_id}</Typography.Text>
                    </div>
                    <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }}>
                      {localizedText(product.description_zh, product.description_en, i18n.language, "")}
                    </Typography.Paragraph>
                    <MoneyText value={product.base_price} />
                    <Button onClick={()=>setSelectedProduct(product)}>{t("erp.details")}</Button>
                    <Button
                      block
                      type="primary"
                      size="large"
                      icon={<ShoppingCartOutlined />}
                      disabled={!data.store.can_order || !product.can_add_to_cart}
                      onClick={() => {
                        const add = () => { addItem(storeId, product); message.success(t("messages.addedToCart")); };
                        if (cartItems.length && cartItems[0].storeId !== storeId) {
                          Modal.confirm({title:t("erp.switchCart"),onOk:add});
                        } else add();
                      }}
                    >
                      {t("pages.menu.addToCart")}
                    </Button>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </section>
      ))}
      <Modal open={Boolean(selectedProduct)} footer={<Button onClick={()=>setSelectedProduct(undefined)}>{t("common.close")}</Button>} onCancel={()=>setSelectedProduct(undefined)} title={localizedText(selectedProduct?.name_zh,selectedProduct?.name_en,i18n.language)}><Space direction="vertical" className="full-width">{selectedProduct?.image_url?<img style={{width:"100%",maxHeight:360,objectFit:"cover"}} src={selectedProduct.image_url} alt={localizedText(selectedProduct.name_zh,selectedProduct.name_en,i18n.language)}/>:null}<Typography.Paragraph>{localizedText(selectedProduct?.description_zh,selectedProduct?.description_en,i18n.language)}</Typography.Paragraph><MoneyText value={selectedProduct?.base_price||"0"}/></Space></Modal>
    </Space>
  );
}

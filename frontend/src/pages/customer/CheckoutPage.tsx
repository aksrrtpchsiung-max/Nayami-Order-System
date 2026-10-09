/**
 * 文件名称：CheckoutPage.tsx
 * 文件用途：购物车校验及订单确认
 * 主要职责：重取菜单与优惠券、展示门店和金额、提交服务端创建订单
 * 所属业务模块：顾客结算
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { DeleteOutlined, SendOutlined } from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  InputNumber,
  List,
  Popconfirm,
  Radio,
  Row,
  Select,
  Space,
  Typography,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { getStoreMenuApi } from "../../api/catalog";
import { createOrderApi } from "../../api/orders";
import { listEligibleCouponsApi } from "../../api/coupons";
import { LoginRedirect } from "../../components/LoginRedirect";
import { MoneyText } from "../../components/MoneyText";
import { localizedText } from "../../i18n/localizedText";
import { useAuthStore } from "../../stores/authStore";
import { useCartStore } from "../../stores/cartStore";
import type { CartItem, StoreMenu } from "../../types/domain";

interface CheckoutForm {
  orderType: "pickup" | "dine_in";
  tablewareCount: number;
  remark?: string;
  userCouponId?: number;
}

export function checkoutItemsValid(
  items: CartItem[],
  menu?: StoreMenu,
): boolean {
  return Boolean(
    menu?.store.can_order &&
      items.length &&
      items.every(
        (item) =>
          item.storeId === menu.store.id &&
          Number.isInteger(item.quantity) &&
          item.quantity > 0 &&
          menu.categories.some((category) =>
            category.products.some(
              (product) =>
                product.store_product_id === item.storeProductId &&
                product.can_add_to_cart,
            ),
          ),
      ),
  );
}

export function CheckoutPage() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const { storeId, items, updateQuantity, removeItem, clearCart } =
    useCartStore();
  const [form] = Form.useForm<CheckoutForm>();
  const selectedCouponId = Form.useWatch("userCouponId", form);
  const [submitting, setSubmitting] = useState(false);
  const menuQuery = useQuery({
    queryKey: ["checkout-menu", storeId],
    queryFn: () => getStoreMenuApi(storeId as number),
    enabled: Boolean(user && storeId),
    staleTime: 0,
    refetchOnMount: "always",
  });
  const products =
    menuQuery.data?.categories.flatMap((category) => category.products) || [];
  const latestPrice = (id: number, fallback: string) =>
    products.find((product) => product.store_product_id === id)?.base_price ||
    fallback;
  const totalAmount =
    items.reduce(
      (sum, item) =>
        sum +
        Math.round(Number(latestPrice(item.storeProductId, item.price)) * 100) *
          item.quantity,
      0,
    ) / 100;
  const couponsQuery = useQuery({
    queryKey: [
      "eligible-coupons",
      user?.id,
      storeId,
      totalAmount,
      items.map((item) => item.productId).join(","),
    ],
    queryFn: () =>
      listEligibleCouponsApi(
        storeId as number,
        totalAmount,
        items.map((item) => item.productId),
      ),
    enabled: Boolean(user && storeId && items.length && menuQuery.data),
  });
  const eligibleCoupons = couponsQuery.data || [];
  const selectedCoupon = eligibleCoupons.find(
    (coupon) => coupon.id === selectedCouponId,
  );
  const discount = Math.min(
    totalAmount,
    Number(selectedCoupon?.discount_amount || 0),
  );
  const valid = checkoutItemsValid(items, menuQuery.data);
  useEffect(() => {
    if (
      selectedCouponId &&
      !eligibleCoupons.some((coupon) => coupon.id === selectedCouponId) &&
      !couponsQuery.isFetching
    )
      form.setFieldValue("userCouponId", undefined);
  }, [eligibleCoupons, selectedCouponId, couponsQuery.isFetching, form]);
  if (!user) return <LoginRedirect />;

  /**
   * 函数名称：submitOrder；用途：提交前再次验证最新菜单、价格与券资格。
   * 参数：结算表单；返回值：异步完成后跳转支付。核心逻辑：刷新菜单、拒绝失效商品/变价、重查券，再创建订单。
   * 失败情况：关店、商品失效、变价、券不可用或服务端库存冲突时保留购物车并展示提示。
   * 最近修改时间：2026-10-09 14:06；修改人：Project Maintainers
   */
  async function submitOrder(values: CheckoutForm) {
    if (submitting || !storeId) return;
    setSubmitting(true);
    try {
      const fresh = await menuQuery.refetch();
      if (fresh.error) throw fresh.error;
      if (!checkoutItemsValid(items, fresh.data))
        throw new Error(t("erp.cartUnavailable"));
      const freshProducts = fresh.data!.categories.flatMap(
        (category) => category.products,
      );
      const freshAmount =
        items.reduce(
          (sum, item) =>
            sum +
            Math.round(
              Number(
                freshProducts.find(
                  (product) => product.store_product_id === item.storeProductId,
                )!.base_price,
              ) * 100,
            ) *
              item.quantity,
          0,
        ) / 100;
      if (freshAmount !== totalAmount) throw new Error(t("erp.priceChanged"));
      if (values.userCouponId) {
        const latestCoupons = await listEligibleCouponsApi(
          storeId,
          freshAmount,
          items.map((item) => item.productId),
        );
        if (
          !latestCoupons.some((coupon) => coupon.id === values.userCouponId)
        ) {
          form.setFieldValue("userCouponId", undefined);
          throw new Error(t("erp.couponChanged"));
        }
      }
      const order = await createOrderApi({
        store_id: storeId,
        order_type: values.orderType,
        tableware_count: values.tablewareCount,
        remark: values.remark,
        user_coupon_id: values.userCouponId,
        items: items.map((item) => ({
          store_product_id: item.storeProductId,
          quantity: item.quantity,
        })),
      });
      clearCart();
      message.success(t("messages.orderCreated"));
      navigate(
        order.payment ? `/pay/${order.payment.id}` : `/orders/${order.id}`,
      );
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <Space direction="vertical" size={24} className="full-width">
      <section className="page-title-block">
        <Typography.Title level={1}>
          {t("pages.checkout.title")}
        </Typography.Title>
      </section>
      {menuQuery.error ? (
        <Alert
          type="error"
          showIcon
          message={(menuQuery.error as Error).message}
          action={
            <Button onClick={() => menuQuery.refetch()}>
              {t("common.refresh")}
            </Button>
          }
        />
      ) : null}
      {items.length && !menuQuery.isLoading && !valid ? (
        <Alert type="warning" showIcon message={t("erp.cartUnavailable")} />
      ) : null}
      {menuQuery.data ? (
        <Card
          title={localizedText(
            menuQuery.data.store.name_zh,
            menuQuery.data.store.name_en,
            i18n.language,
          )}
        >
          <Typography.Paragraph>
            {menuQuery.data.store.address} · {menuQuery.data.store.phone}
          </Typography.Paragraph>
          <Typography.Text>
            {menuQuery.data.store.business_start_time}–
            {menuQuery.data.store.business_end_time}
          </Typography.Text>
        </Card>
      ) : null}
      <Row gutter={[20, 20]} align="top">
        <Col xs={24} lg={15}>
          <Card
            title={t("pages.checkout.cartTitle")}
            extra={
              <Popconfirm
                title={t("erp.clearCartConfirm")}
                onConfirm={clearCart}
              >
                <Button danger disabled={!items.length || submitting}>
                  {t("erp.clearCart")}
                </Button>
              </Popconfirm>
            }
          >
            <List
              dataSource={items}
              locale={{ emptyText: t("messages.emptyCart") }}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <InputNumber
                      key="quantity"
                      aria-label={t("erp.quantityFor", {
                        name: localizedText(
                          item.nameZh,
                          item.nameEn,
                          i18n.language,
                        ),
                      })}
                      min={0}
                      max={99}
                      precision={0}
                      disabled={submitting}
                      value={item.quantity}
                      onChange={(value) =>
                        value !== null &&
                        updateQuantity(item.storeProductId, value)
                      }
                    />,
                    <Button
                      key="delete"
                      aria-label={t("common.delete")}
                      disabled={submitting}
                      icon={<DeleteOutlined />}
                      onClick={() => removeItem(item.storeProductId)}
                    />,
                  ]}
                >
                  <List.Item.Meta
                    title={localizedText(
                      item.nameZh,
                      item.nameEn,
                      i18n.language,
                    )}
                    description={
                      <MoneyText
                        value={latestPrice(item.storeProductId, item.price)}
                      />
                    }
                  />
                  <MoneyText
                    value={
                      Number(latestPrice(item.storeProductId, item.price)) *
                      item.quantity
                    }
                  />
                </List.Item>
              )}
            />
            <div className="checkout-total">
              <Typography.Text>{t("erp.itemsAmount")}</Typography.Text>
              <MoneyText value={totalAmount} />
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={9}>
          <Card title={t("pages.checkout.fulfillmentTitle")}>
            <Form<CheckoutForm>
              form={form}
              layout="vertical"
              initialValues={{ orderType: "pickup", tablewareCount: 1 }}
              onFinish={submitOrder}
            >
              <Form.Item
                name="orderType"
                label={t("forms.orderType")}
                rules={[{ required: true }]}
              >
                <Radio.Group
                  options={[
                    { label: t("orderTypes.pickup"), value: "pickup" },
                    { label: t("orderTypes.dine_in"), value: "dine_in" },
                  ]}
                />
              </Form.Item>
              <Form.Item
                name="tablewareCount"
                label={t("forms.tablewareCount")}
                rules={[{ required: true, type: "integer", min: 0, max: 10 }]}
              >
                <InputNumber min={0} max={10} precision={0} />
              </Form.Item>
              <Form.Item name="userCouponId" label={t("forms.coupon")}>
                <Select
                  allowClear
                  loading={couponsQuery.isFetching}
                  options={eligibleCoupons
                    .filter((coupon) => coupon.id !== null)
                    .map((coupon) => ({
                      value: coupon.id!,
                      label: `${localizedText(coupon.activity_name_zh, coupon.activity_name_en, i18n.language)} · ${t("forms.couponDiscount", { amount: coupon.discount_amount })}`,
                    }))}
                />
              </Form.Item>
              <Form.Item name="remark" label={t("forms.orderRemark")}>
                <Input.TextArea maxLength={100} showCount rows={3} />
              </Form.Item>
              <div className="checkout-total">
                <Typography.Text>{t("forms.discountAmount")}</Typography.Text>
                <MoneyText value={discount} />
              </div>
              <div className="checkout-total">
                <Typography.Text strong>
                  {t("pages.order.payableAmount")}
                </Typography.Text>
                <MoneyText value={Math.max(0, totalAmount - discount)} />
              </div>
              <Button
                block
                size="large"
                type="primary"
                htmlType="submit"
                icon={<SendOutlined />}
                loading={submitting}
                disabled={
                  !valid || menuQuery.isFetching || couponsQuery.isFetching
                }
              >
                {t("pages.checkout.submit")}
              </Button>
            </Form>
          </Card>
        </Col>
      </Row>
    </Space>
  );
}

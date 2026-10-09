/**
 * 文件名称：CustomerCenterPage.tsx
 * 文件用途：展示历史订单、优惠券范围状态与异步到账轮询
 * 主要职责：展示历史订单、优惠券范围状态与异步到账轮询
 * 所属业务模块：顾客中心
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { useState } from "react";
import { LoginRedirect } from "../../components/LoginRedirect";
import { GiftOutlined, HistoryOutlined, ThunderboltOutlined, UserOutlined } from "@ant-design/icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Select, Col, Empty, List, Row, Skeleton, Space, Statistic, Tabs, Tag, Typography, message } from "antd";
import { useTranslation } from "react-i18next";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { claimCouponApi, listCouponActivitiesApi, listMyCouponsApi } from "../../api/coupons";
import { listCustomerOrdersApi } from "../../api/orders";
import { MoneyText } from "../../components/MoneyText";
import { StatusTag } from "../../components/StatusTag";
import { localizedText } from "../../i18n/localizedText";
import { useAuthStore } from "../../stores/authStore";

export function CustomerCenterPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [couponFilter,setCouponFilter]=useState("all");
  const user = useAuthStore((state) => state.user);
  const { data: orders = [], isLoading: ordersLoading } = useQuery({
    queryKey: ["my-orders", user?.id],
    refetchInterval: 10000,
    queryFn: () => listCustomerOrdersApi(),
    enabled: Boolean(user)
  });
  const { data: coupons = [], isLoading: couponsLoading, error: couponsError } = useQuery({
    queryKey: ["my-coupons", user?.id],
    refetchInterval: query => query.state.data?.some(coupon => ["syncing","abnormal"].includes(coupon.coupon_status)) ? 3000 : false,
    queryFn: () => listMyCouponsApi(),
    enabled: Boolean(user)
  });
  const { data: activities = [], isLoading: activitiesLoading } = useQuery({
    queryKey: ["coupon-activities"],
    queryFn: listCouponActivitiesApi
  });
  const claimMutation = useMutation({
    mutationFn: claimCouponApi,
    onSuccess: async () => {
      message.success(t("messages.couponClaimed"));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["my-coupons"] }),
        queryClient.invalidateQueries({ queryKey: ["coupon-activities"] })
      ]);
    },
    onError: (error) => message.error((error as Error).message)
  });

  if (!user) {
    return <LoginRedirect />;
  }

  const localizedPathname = location.pathname.replace(/^\/(?:zh|en)(?=\/|$)/, "");
  const activeTab = localizedPathname === "/coupons"
    ? "activities"
    : localizedPathname === "/my/coupons"
      ? "coupons"
      : localizedPathname === "/me"
        ? "profile"
        : "orders";

  return (
    <Space direction="vertical" size={24} className="full-width">
      <section className="page-title-block">
        <Typography.Text className="page-kicker">{t("pages.customerCenter.kicker")}</Typography.Text>
        <Typography.Title level={1}>{t("pages.customerCenter.title")}</Typography.Title>
        <Typography.Paragraph>{t("pages.customerCenter.description")}</Typography.Paragraph>
      </section>
      <Button onClick={() => {void queryClient.invalidateQueries({queryKey:["my-orders"]});void queryClient.invalidateQueries({queryKey:["my-coupons"]});}}>{t("common.refresh")}</Button>
      {couponsError ? <Alert type="error" showIcon message={(couponsError as Error).message}/> : null}
      <Tabs
        activeKey={activeTab}
        onChange={(tabKey) => {
          const paths: Record<string, string> = {
            orders: "/my/orders",
            coupons: "/my/coupons",
            activities: "/coupons",
            profile: "/me"
          };
          navigate(paths[tabKey]);
        }}
        items={[
          {
            key: "orders",
            label: <span><HistoryOutlined /> {t("nav.myOrders")}</span>,
            children: ordersLoading ? (
              <Skeleton active />
            ) : (
              <List
                dataSource={orders}
                locale={{ emptyText: <Empty description={t("pages.customerCenter.noOrders")} /> }}
                renderItem={(order) => (
                  <List.Item
                    className="workspace-list-item"
                    actions={[
                      ...(order.order_status === "pending_payment" && order.payment ? [<Button key="pay" type="primary" onClick={()=>navigate(`/pay/${order.payment!.id}`)}>{t("erp.continuePayment")}</Button>] : []),
                      <Button key="detail" onClick={() => navigate(`/orders/${order.id}`)}>
                        {t("pages.customerCenter.viewOrder")}
                      </Button>
                    ]}
                  >
                    <List.Item.Meta
                      title={<Space><strong>{order.order_no}</strong><StatusTag status={order.order_status} namespace="order" /></Space>}
                      description={<span>{localizedText(order.store_name_zh, order.store_name_en, i18n.language)} · {order.created_at}<br/>{order.items.map(item=>`${localizedText(item.product_name_zh,item.product_name_en,i18n.language)} × ${item.quantity}`).join(" · ")} · {t(`orderTypes.${order.order_type}`)}</span>}
                    />
                    <MoneyText value={order.payable_amount} />
                  </List.Item>
                )}
              />
            )
          },
          {
            key: "coupons",
            label: <span><GiftOutlined /> {t("nav.myCoupons")}</span>,
            children: couponsLoading ? (
              <Skeleton active />
            ) : (
              <Row gutter={[16, 16]}>
                <Col span={24}><Select aria-label={t("erp.couponFilter")} style={{minWidth:180}} value={couponFilter} onChange={setCouponFilter} options={["all","available","locked","used","expired","syncing","abnormal"].map(value=>({value,label:value==="all"?t("erp.all"):t(`status.coupon.${value}`)}))}/></Col>
                {coupons.filter(coupon=>couponFilter==="all"||coupon.coupon_status===couponFilter).map((coupon) => (
                  <Col xs={24} md={12} xl={8} key={coupon.id ? `coupon-${coupon.id}` : `task-${coupon.task_id}`}>
                    <Card className="compact-card">
                      <Space direction="vertical" className="full-width">
                        <Space>
                          <Typography.Title level={4}>
                            {localizedText(coupon.activity_name_zh, coupon.activity_name_en, i18n.language)}
                          </Typography.Title>
                          <StatusTag status={coupon.coupon_status} namespace="coupon" />
                        </Space>
                        <Statistic title={t("forms.discountAmount")} value={coupon.discount_amount} prefix="¥" />
                        <Typography.Text type="secondary">
                          {t("pages.customerCenter.minimumOrder", { amount: coupon.minimum_order_amount })}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          {t("pages.customerCenter.expiresAt", { time: coupon.expired_at || "-" })}
                        </Typography.Text>
                        <Typography.Text>{t("erp.scopeStores")}: {coupon.scope_stores?.length ? coupon.scope_stores.map(store=>localizedText(store.name_zh,store.name_en,i18n.language)).join(" · ") : coupon.store_ids.length ? coupon.store_ids.join(", ") : t("erp.allStores")}</Typography.Text>
                        <Typography.Text>{t("erp.scopeProducts")}: {coupon.scope_products?.length ? coupon.scope_products.map(product=>localizedText(product.name_zh,product.name_en,i18n.language)).join(" · ") : coupon.product_ids.length ? coupon.product_ids.join(", ") : t("erp.allProducts")}</Typography.Text>
                        {coupon.coupon_status === "available" ? <Button type="primary" onClick={()=>navigate(coupon.store_ids.length===1 ? `/stores/${coupon.store_ids[0]}/menu` : "/stores")}>{t("erp.useCoupon")}</Button> : ["syncing","abnormal"].includes(coupon.coupon_status) ? <Alert type="info" message={t("erp.couponSyncHint")}/> : null}
                      </Space>
                    </Card>
                  </Col>
                ))}
                {!coupons.length ? <Col span={24}><Empty description={t("pages.customerCenter.noCoupons")} /></Col> : null}
              </Row>
            )
          },
          {
            key: "activities",
            label: <span><ThunderboltOutlined /> {t("nav.couponCenter")}</span>,
            children: activitiesLoading ? (
              <Skeleton active />
            ) : (
              <Row gutter={[16, 16]}>
                {activities.map((activity) => (
                  <Col xs={24} md={12} xl={8} key={activity.id}>
                    <Card className="compact-card">
                      <Space direction="vertical" className="full-width">
                        <Tag color={activity.effective_status === "active" ? "green" : "default"}>
                          {t(`status.coupon.${activity.effective_status}`)}
                        </Tag>
                        <Typography.Title level={4}>
                          {localizedText(activity.activity_name_zh, activity.activity_name_en, i18n.language)}
                        </Typography.Title>
                        <Typography.Paragraph type="secondary">
                          {localizedText(activity.description_zh, activity.description_en, i18n.language)}
                        </Typography.Paragraph>
                        <Statistic title={t("forms.discountAmount")} value={activity.discount_amount} prefix="¥" />
                        <Typography.Text>{t("pages.customerCenter.remaining", { count: activity.remaining_stock ?? 0 })}</Typography.Text>
                        <Button
                          block
                          type="primary"
                          disabled={activity.effective_status !== "active" || activity.remaining_stock === 0}
                          loading={claimMutation.isPending && claimMutation.variables === activity.id}
                          onClick={() => claimMutation.mutate(activity.id)}
                        >
                          {t("pages.customerCenter.claim")}
                        </Button>
                      </Space>
                    </Card>
                  </Col>
                ))}
              </Row>
            )
          },
          {
            key: "profile",
            label: <span><UserOutlined /> {t("pages.customerCenter.profile")}</span>,
            children: (
              <Card className="compact-card">
                <Typography.Title level={3}>{user.username}</Typography.Title>
                <Typography.Paragraph>{user.phone}</Typography.Paragraph>
                <Typography.Text type="secondary">{user.default_language}</Typography.Text>
              </Card>
            )
          }
        ]}
      />
    </Space>
  );
}

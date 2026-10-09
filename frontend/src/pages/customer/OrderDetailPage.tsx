/**
 * 文件名称：OrderDetailPage.tsx
 * 文件用途：显示订单状态与日志、继续支付和取消退款
 * 主要职责：显示订单状态与日志、继续支付和取消退款
 * 所属业务模块：顾客订单
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { OrderFacts } from "../../components/OrderFacts";
import { LoginRedirect } from "../../components/LoginRedirect";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Descriptions, List, Popconfirm, Row, Skeleton, Space, Steps, Typography, message } from "antd";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { cancelOrderApi, getOrderApi } from "../../api/orders";
import { requestRefundApi, simulateRefundSuccessApi } from "../../api/payments";
import { MoneyText } from "../../components/MoneyText";
import { StatusTag } from "../../components/StatusTag";
import { localizedText } from "../../i18n/localizedText";
import { useAuthStore } from "../../stores/authStore";

const orderSteps = ["pending_payment", "paid", "accepted", "preparing", "ready", "completed"];

export function OrderDetailPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const orderId = Number(useParams().orderId);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["order", orderId, user?.id],
    queryFn: () => getOrderApi(orderId),
    enabled: Boolean(user && orderId),
    refetchInterval: (query) => ["completed","canceled","refunded"].includes(query.state.data?.order_status || "") ? false : 5000
  });
  const cancelMutation = useMutation({
    mutationFn: () => cancelOrderApi(orderId),
    onSuccess: async () => {
      message.success(t("messages.orderCanceled"));
      await queryClient.invalidateQueries({ queryKey: ["order", orderId, user?.id] });
    },
    onError: (error) => {
      message.error((error as Error).message);
    }
  });
  const refundMutation = useMutation({
    mutationFn: () => requestRefundApi(orderId, t("pages.order.customerRefundReason")),
    onSuccess: async () => {
      message.success(t("messages.refundRequested"));
      await queryClient.invalidateQueries({ queryKey: ["order", orderId, user?.id] });
    },
    onError: (error) => message.error((error as Error).message)
  });
  const refundSuccessMutation = useMutation({
    mutationFn: () => simulateRefundSuccessApi(data?.refund?.id as number),
    onSuccess: async () => {
      message.success(t("messages.refundCompleted"));
      await queryClient.invalidateQueries({ queryKey: ["order", orderId, user?.id] });
    },
    onError: (error) => message.error((error as Error).message)
  });

  if (!user) {
    return <LoginRedirect />;
  }
  if (isLoading) {
    return <Skeleton active />;
  }

  if (error || !data) return <Alert type="error" showIcon message={(error as Error)?.message || t("errors.order_not_found")} action={<Button onClick={() => refetch()}>{t("common.refresh")}</Button>}/>;
  const currentStep = orderSteps.indexOf(data.order_status);

  return (
    <Space direction="vertical" size={24} className="full-width">
      <section className="order-hero">
        <div>
          <Typography.Text className="page-kicker">{t("pages.order.kicker")}</Typography.Text>
          <Typography.Title level={1}>{t("pages.order.title")}</Typography.Title>
          <Button onClick={() => refetch()}>{t("common.refresh")}</Button>
          {data.order_status === "pending_payment" && data.payment ? <Button type="primary" onClick={() => navigate(`/pay/${data.payment!.id}`)}>{t("erp.continuePayment")}</Button> : null}
          <Typography.Paragraph>{t("pages.order.description")}</Typography.Paragraph>
        </div>
        <div className="pickup-code-card">
          <Typography.Text type="secondary">{t("common.pickupCode")}</Typography.Text>
          <strong>{data?.pickup_code || t("common.generatedAfterPayment")}</strong>
          {data ? <StatusTag status={data.order_status} namespace="order" /> : null}
          {data?.order_status === "pending_payment" ? (
            <Popconfirm
              title={t("pages.order.cancelConfirm")}
              okText={t("common.submit")}
              cancelText={t("common.cancel")}
              onConfirm={() => cancelMutation.mutate()}
            >
              <Button danger loading={cancelMutation.isPending}>
                {t("pages.order.cancelOrder")}
              </Button>
            </Popconfirm>
          ) : data?.order_status === "paid" || data?.order_status === "accepted" ? (
            <Popconfirm
              title={t("pages.order.refundConfirm")}
              okText={t("common.submit")}
              cancelText={t("common.cancel")}
              onConfirm={() => refundMutation.mutate()}
            >
              <Button danger loading={refundMutation.isPending}>
                {t("pages.order.requestRefund")}
              </Button>
            </Popconfirm>
          ) : data?.order_status === "refund_pending" && data.refund ? (
            <Button type="primary" loading={refundSuccessMutation.isPending} onClick={() => refundSuccessMutation.mutate()}>
              {t("pages.order.simulateRefund")}
            </Button>
          ) : null}
        </div>
      </section>
      <Card className="compact-card order-progress-card">
        {currentStep < 0 ? <Alert showIcon type={data.order_status === "refunded" ? "success" : "warning"} message={t(`status.order.${data.order_status}`)} description={data.cancel_reason || data.refund?.refund_reason}/> : <Steps
          current={currentStep}
          responsive
          items={orderSteps.map((status) => ({ title: t(`status.order.${status}`) }))}
        />}
      </Card>
      <OrderFacts order={data}/>

    </Space>
  );
}

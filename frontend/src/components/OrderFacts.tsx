/**
 * 文件名称：OrderFacts.tsx
 * 文件用途：共享订单及支付明细
 * 主要职责：展示商品快照、金额、取餐信息与状态时间线
 * 所属业务模块：订单
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { Card, Descriptions, List, Space, Timeline, Typography } from "antd";
import { useTranslation } from "react-i18next";
import type { OrderDetail } from "../types/domain";
import { localizedText } from "../i18n/localizedText";
import { MoneyText } from "./MoneyText";
import { StatusTag } from "./StatusTag";

export function OrderFacts({
  order,
  showLogs = true,
}: {
  order: OrderDetail;
  showLogs?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const systemReasons: Record<string, string> = {
    顾客提交订单: "orderSubmitted",
    顾客主动取消订单: "customerCanceled",
    门店履约状态更新: "fulfillmentUpdated",
    支付超时自动取消订单: "paymentTimedOut",
    仿真支付成功回调: "paymentSucceeded",
    仿真退款成功: "refundSucceeded",
  };
  return (
    <Space direction="vertical" size={16} className="full-width">
      <Descriptions bordered column={{ xs: 1, md: 2 }} size="small">
        <Descriptions.Item label={t("pages.order.orderNo")}>
          {order.order_no}
        </Descriptions.Item>
        <Descriptions.Item label={t("pages.order.store")}>
          {localizedText(
            order.store_name_zh || order.store_name,
            order.store_name_en,
            i18n.language,
          )}
        </Descriptions.Item>
        <Descriptions.Item label={t("forms.address")}>
          {order.store_address || "—"}
        </Descriptions.Item>
        <Descriptions.Item label={t("forms.phone")}>
          {order.store_phone || "—"}
        </Descriptions.Item>
        <Descriptions.Item label={t("forms.orderType")}>
          {t(`orderTypes.${order.order_type}`)}
        </Descriptions.Item>
        <Descriptions.Item label={t("common.pickupCode")}>
          {order.pickup_code || t("common.generatedAfterPayment")}
        </Descriptions.Item>
        <Descriptions.Item label={t("forms.tablewareCount")}>
          {order.tableware_count}
        </Descriptions.Item>
        <Descriptions.Item label={t("forms.orderRemark")}>
          {order.remark || t("common.none")}
        </Descriptions.Item>
        <Descriptions.Item label={t("pages.order.createdAt")}>
          {order.created_at}
        </Descriptions.Item>
        <Descriptions.Item label={t("erp.paidAt")}>
          {order.paid_at || "—"}
        </Descriptions.Item>
        {order.customer_name ? (
          <Descriptions.Item label={t("erp.customer")}>
            {order.customer_name} · {order.customer_phone_masked}
          </Descriptions.Item>
        ) : null}
        {order.cancel_reason ? (
          <Descriptions.Item label={t("erp.reason")}>
            {order.cancel_reason}
          </Descriptions.Item>
        ) : null}
        <Descriptions.Item label={t("erp.itemsAmount")}>
          <MoneyText value={order.items_amount} />
        </Descriptions.Item>
        <Descriptions.Item label={t("forms.discountAmount")}>
          <MoneyText value={order.discount_amount} />
        </Descriptions.Item>
        <Descriptions.Item label={t("pages.order.payableAmount")}>
          <MoneyText value={order.payable_amount} />
        </Descriptions.Item>
        {order.refund ? (
          <Descriptions.Item label={t("erp.refund")}>
            <StatusTag status={order.refund.refund_status} namespace="refund" />{" "}
            <MoneyText value={order.refund.refund_amount} />
            <br />
            {order.refund.refund_reason} {order.refund.refunded_at}
          </Descriptions.Item>
        ) : null}
      </Descriptions>
      <List
        bordered
        dataSource={order.items}
        renderItem={(item) => (
          <List.Item>
            <List.Item.Meta
              title={localizedText(
                item.product_name_zh,
                item.product_name_en,
                i18n.language,
              )}
              description={
                <span>
                  <MoneyText value={item.unit_price} /> × {item.quantity}
                </span>
              }
            />
            <MoneyText value={item.subtotal_amount} />
          </List.Item>
        )}
      />
      <Card size="small" title={t("erp.paymentRecords")}>
        <List
          locale={{ emptyText: t("common.none") }}
          dataSource={order.payments || (order.payment ? [order.payment] : [])}
          renderItem={(payment) => (
            <List.Item>
              <Space direction="vertical" size={0}>
                <Typography.Text>
                  {payment.payment_no} ·{" "}
                  {t(`paymentMethods.${payment.payment_method}`)}
                </Typography.Text>
                <StatusTag
                  namespace="payment"
                  status={payment.payment_status}
                />
                <Typography.Text type="secondary">
                  {payment.paid_at || "—"} {payment.transaction_no || ""}{" "}
                  {payment.masked_card_no || ""}
                </Typography.Text>
              </Space>
              <MoneyText value={payment.payment_amount} />
            </List.Item>
          )}
        />
      </Card>
      {showLogs ? (
        <Card size="small" title={t("erp.statusHistory")}>
          <Timeline
            items={(order.status_logs || []).map((log) => ({
              children: (
                <>
                  <Typography.Text>
                    {log.created_at} ·{" "}
                    {log.from_status
                      ? `${t(`status.order.${log.from_status}`)} → `
                      : ""}
                    {t(`status.order.${log.to_status}`)}
                  </Typography.Text>
                  {log.reason ? (
                    <div>
                      {systemReasons[log.reason]
                        ? t(`erp.${systemReasons[log.reason]}`)
                        : log.reason}
                    </div>
                  ) : null}
                </>
              ),
            }))}
          />
          <Timeline
            items={(order.payment_logs || []).map((log) => ({
              color: "gray",
              children: (
                <Typography.Text type="secondary">
                  {log.created_at} · {t("erp.payment")} #{log.payment_id} ·{" "}
                  {t(`status.payment.${log.to_status}`)}
                </Typography.Text>
              ),
            }))}
          />
        </Card>
      ) : null}
    </Space>
  );
}

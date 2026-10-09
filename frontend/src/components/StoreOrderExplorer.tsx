/**
 * 文件名称：StoreOrderExplorer.tsx
 * 文件用途：查询门店历史与异常订单
 * 主要职责：日期/订单号搜索、订单详情、按角色取消退款
 * 所属业务模块：门店工作台与品牌订单视角
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Drawer,
  Input,
  Modal,
  Select,
  Space,
  Table,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getOrderApi,
  listStoreOrdersApi,
  updateStoreOrderStatusApi,
} from "../api/orders";
import { requestRefundApi, simulateRefundSuccessApi } from "../api/payments";
import { useAuthStore } from "../stores/authStore";
import { isStoreManager } from "../utils/access";
import { OrderFacts } from "./OrderFacts";
import { StatusTag } from "./StatusTag";
import { MoneyText } from "./MoneyText";

export function StoreOrderExplorer({
  storeId,
  readOnly = false,
  initialOrderId,
  onCloseDetail,
}: {
  storeId: number;
  readOnly?: boolean;
  initialOrderId?: number;
  onCloseDetail?: () => void;
}) {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const [view, setView] = useState("history");
  const [days, setDays] = useState(7);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number>();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [pickupCode, setPickupCode] = useState("");
  useEffect(() => {
    setSelectedId(undefined);
    setCancelOpen(false);
    setReason("");
    setPickupCode("");
  }, [storeId, user?.id]);
  const detailId = initialOrderId || selectedId;
  const orders = useQuery({
    queryKey: ["store-history", storeId, view, days, search],
    queryFn: () =>
      listStoreOrdersApi(storeId, undefined, { view, days, search }),
    enabled: !initialOrderId,
  });
  const detail = useQuery({
    queryKey: ["store-order-detail", storeId, detailId],
    queryFn: () => getOrderApi(detailId!),
    enabled: Boolean(detailId),
    refetchInterval: detailId ? 5000 : false,
  });
  const nextStatuses: Record<string, string> = {
    paid: "accepted",
    accepted: "preparing",
    preparing: "ready",
    ready: "completed",
  };
  const actionLabels: Record<string, string> = {
    accepted: "pages.storeWorkspace.acceptOrder",
    preparing: "pages.storeWorkspace.startPreparing",
    ready: "pages.storeWorkspace.finishPreparing",
    completed: "pages.storeWorkspace.completePickup",
  };
  const nextStatus = detail.data
    ? nextStatuses[detail.data.order_status]
    : undefined;
  async function advance() {
    if (!detailId || !nextStatus || busy) return;
    setBusy(true);
    try {
      await updateStoreOrderStatusApi(detailId, nextStatus, pickupCode);
      setPickupCode("");
      await Promise.all([detail.refetch(), orders.refetch()]);
      message.success(t("messages.orderStatusUpdated"));
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const canCancel =
    !readOnly &&
    detail.data &&
    (["paid", "accepted"].includes(detail.data.order_status) ||
      (isStoreManager(user) && detail.data.order_status === "preparing"));
  async function cancel() {
    if (!detailId || !reason.trim()) return;
    setBusy(true);
    try {
      await requestRefundApi(detailId, reason.trim());
      setCancelOpen(false);
      setReason("");
      await Promise.all([orders.refetch(), detail.refetch()]);
      message.success(t("messages.refundRequested"));
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Space direction="vertical" className="full-width" size={16}>
      {!initialOrderId ? (
        <>
          <Space wrap>
            <Select
              value={view}
              onChange={setView}
              options={["history", "active", "all"].map((value) => ({
                value,
                label: t(`erp.orders_${value}`),
              }))}
            />
            <Select
              value={days}
              onChange={setDays}
              options={[1, 7, 30].map((value) => ({
                value,
                label: t(
                  value === 1
                    ? "erp.today"
                    : value === 7
                      ? "erp.last7"
                      : "erp.last30",
                ),
              }))}
            />
            <Input.Search
              allowClear
              placeholder={t("erp.orderSearch")}
              onSearch={setSearch}
            />
            <Button onClick={() => orders.refetch()}>
              {t("common.refresh")}
            </Button>
          </Space>
          {orders.error ? (
            <Alert type="error" message={(orders.error as Error).message} />
          ) : null}
          <Table
            rowKey="id"
            dataSource={orders.data || []}
            loading={orders.isFetching}
            scroll={{ x: 700 }}
            columns={[
              { title: t("pages.order.orderNo"), dataIndex: "order_no" },
              { title: t("common.pickupCode"), dataIndex: "pickup_code" },
              {
                title: t("pages.tables.status"),
                dataIndex: "order_status",
                render: (value) => (
                  <StatusTag namespace="order" status={value} />
                ),
              },
              { title: t("erp.paidAt"), dataIndex: "paid_at" },
              {
                title: t("pages.order.payableAmount"),
                dataIndex: "payable_amount",
                render: (value) => <MoneyText value={value} />,
              },
              {
                title: t("pages.tables.actions"),
                render: (_, row) => (
                  <Button onClick={() => setSelectedId(row.id)}>
                    {t("erp.details")}
                  </Button>
                ),
              },
            ]}
          />
        </>
      ) : null}
      <Drawer
        open={Boolean(detailId)}
        onClose={() => {
          setSelectedId(undefined);
          onCloseDetail?.();
        }}
        width={850}
        title={t("pages.order.title")}
      >
        <Space direction="vertical" className="full-width" size={16}>
          <Space wrap>
            <Button onClick={() => detail.refetch()}>
              {t("common.refresh")}
            </Button>
            {detail.data ? (
              <StatusTag status={detail.data.order_status} namespace="order" />
            ) : null}
            {!readOnly && nextStatus ? (
              <>
                {nextStatus === "completed" ? (
                  <Input
                    aria-label={t("common.pickupCode")}
                    placeholder={t("forms.pickupCodePlaceholder")}
                    value={pickupCode}
                    onChange={(event) => setPickupCode(event.target.value)}
                  />
                ) : null}
                <Button
                  type="primary"
                  loading={busy}
                  disabled={nextStatus === "completed" && !pickupCode.trim()}
                  onClick={advance}
                >
                  {t(actionLabels[nextStatus])}
                </Button>
              </>
            ) : null}
            {canCancel ? (
              <Button danger onClick={() => setCancelOpen(true)}>
                {t("erp.cancelWithReason")}
              </Button>
            ) : null}
            {!readOnly &&
            detail.data?.order_status === "refund_pending" &&
            detail.data.refund ? (
              <Button
                loading={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await simulateRefundSuccessApi(detail.data!.refund!.id);
                    await detail.refetch();
                    await orders.refetch();
                  } catch (error) {
                    message.error((error as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {t("pages.order.simulateRefund")}
              </Button>
            ) : null}
          </Space>
          {detail.error ? (
            <Alert type="error" message={(detail.error as Error).message} />
          ) : null}
          {detail.data ? <OrderFacts order={detail.data} /> : null}
        </Space>
      </Drawer>
      <Modal
        title={t("erp.cancelWithReason")}
        open={cancelOpen}
        onCancel={() => setCancelOpen(false)}
        onOk={cancel}
        confirmLoading={busy}
        okButtonProps={{ disabled: !reason.trim() }}
      >
        <Input.TextArea
          aria-label={t("erp.reason")}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={255}
          rows={4}
          showCount
          placeholder={t("erp.reason")}
        />
      </Modal>
    </Space>
  );
}

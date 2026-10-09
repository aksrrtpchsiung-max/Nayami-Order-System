/**
 * 文件名称：StoreOrdersPage.tsx
 * 文件用途：提供订单看板、历史详情、库存维护与报表权限展示
 * 主要职责：提供订单看板、历史详情、库存维护与报表权限展示
 * 所属业务模块：门店运营
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { InventoryHistory } from "../../components/InventoryHistory";
import { ReportPeriods } from "../../components/ReportPeriods";
import { StoreOrderExplorer } from "../../components/StoreOrderExplorer";
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  LineChartOutlined,
  ReloadOutlined,
  ShopOutlined,
  ToolOutlined
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Card, Col, Empty, Input, InputNumber, Row, Select, Space, Statistic, Switch, Table, Tabs, Tag, Typography, message } from "antd";
import type { TableColumnsType } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate } from "react-router-dom";
import { listStoreInventoryApi, updateStoreInventoryApi } from "../../api/inventory";
import { listStoreOrdersApi, updateStoreOrderStatusApi } from "../../api/orders";
import { getStoreOverviewApi, getStoreReportApi } from "../../api/reports";
import { listStoresApi, updateStoreStatusApi } from "../../api/stores";
import { MoneyText } from "../../components/MoneyText";
import { StatusTag } from "../../components/StatusTag";
import { localizedList, localizedText } from "../../i18n/localizedText";
import { useAuthStore } from "../../stores/authStore";
import type { StoreInventoryItem } from "../../types/domain";
import { isStoreManager, isStoreWorkspaceUser } from "../../utils/access";

const nextStatusMap: Record<string, { target: string; labelKey: string }> = {
  paid: { target: "accepted", labelKey: "pages.storeWorkspace.acceptOrder" },
  accepted: { target: "preparing", labelKey: "pages.storeWorkspace.startPreparing" },
  preparing: { target: "ready", labelKey: "pages.storeWorkspace.finishPreparing" },
  ready: { target: "completed", labelKey: "pages.storeWorkspace.completePickup" }
};

const kanbanColumns = [
  { status: "paid", titleKey: "pages.storeWorkspace.columnPaid" },
  { status: "accepted", titleKey: "pages.storeWorkspace.columnAccepted" },
  { status: "preparing", titleKey: "pages.storeWorkspace.columnPreparing" },
  { status: "ready", titleKey: "pages.storeWorkspace.columnReady" }
];

export function StoreOrdersPage() {
  const { t, i18n } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const [orderSearch,setOrderSearch]=useState("");
  const [selectedOrderId,setSelectedOrderId]=useState<number>();
  const [stockReasons,setStockReasons]=useState<Record<number,string>>({});
  const [pickupCodes, setPickupCodes] = useState<Record<number, string>>({});
  const [stockDrafts, setStockDrafts] = useState<Record<number, number>>({});
  const [storeStatus, setStoreStatus] = useState<"open" | "closed" | "temporarily_closed">("open");
  const [temporaryCloseReason, setTemporaryCloseReason] = useState("");
  const canManageStore = isStoreManager(user);
  const binding = user?.store_bindings?.[0];
  const storeId = binding?.store_id;

  const ordersQuery = useQuery({
    queryKey: ["store-orders", storeId, orderSearch],
    queryFn: () => listStoreOrdersApi(Number(storeId),undefined,{view:"active",days:1,search:orderSearch}),
    refetchInterval: 5000,
    enabled: Boolean(storeId && binding?.is_active !== false)
  });
  const overviewQuery = useQuery({
    queryKey: ["store-overview", storeId],
    refetchInterval: 5000,
    queryFn: () => getStoreOverviewApi(Number(storeId)),
    enabled: Boolean(storeId && binding?.is_active !== false)
  });
  const inventoryQuery = useQuery({
    queryKey: ["store-inventory", storeId],
    queryFn: () => listStoreInventoryApi(Number(storeId)),
    enabled: Boolean(storeId && binding?.is_active !== false)
  });
  const reportQuery = useQuery({
    queryKey: ["store-report", storeId],
    queryFn: () => getStoreReportApi(Number(storeId)),
    enabled: Boolean(storeId && canManageStore)
  });
  const storesQuery = useQuery({ queryKey: ["stores"], queryFn: listStoresApi, enabled: Boolean(storeId && binding?.is_active !== false) });

  const store = useMemo(() => storesQuery.data?.find((item) => item.id === storeId), [storeId, storesQuery.data]);
  const storeStatusOptions = [
    { label: t("status.store.open"), value: "open" },
    { label: t("status.store.temporarily_closed"), value: "temporarily_closed" },
    { label: t("status.store.closed"), value: "closed" }
  ];

  useEffect(() => {
    if (store?.store_status === "open" || store?.store_status === "closed" || store?.store_status === "temporarily_closed") {
      setStoreStatus(store.store_status);
      setTemporaryCloseReason(store.temporary_close_reason || "");
    }
  }, [store]);

  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!isStoreWorkspaceUser(user)) {
    return <Navigate to="/stores" replace />;
  }
  if (binding?.is_active === false) return <Alert type="warning" showIcon message={t("erp.storeUnavailable")}/>;
  if (!storeId) {
    return <Empty description={t("pages.storeWorkspace.unbound")} />;
  }

  async function refetchWorkspace() {
    await Promise.all([
      ordersQuery.refetch(),
      overviewQuery.refetch(),
      inventoryQuery.refetch(),
      ...(canManageStore ? [reportQuery.refetch()] : []),
      storesQuery.refetch()
    ]);
  }

  async function updateStatus(orderId: number, currentStatus: string) {
    const next = nextStatusMap[currentStatus];
    if (!next) {
      return;
    }
    try {
      await updateStoreOrderStatusApi(orderId, next.target, pickupCodes[orderId]);
      message.success(t("messages.orderStatusUpdated"));
      refetchWorkspace();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function updateInventory(row: StoreInventoryItem, payload: Partial<StoreInventoryItem>) {
    if (!canManageStore) {
      message.warning(t("messages.inventoryManagerOnly"));
      return;
    }
    try {
      await updateStoreInventoryApi(row.store_product_id, {
        current_stock: payload.current_stock,
        is_available: payload.is_available,
        is_sold_out: payload.is_sold_out,
        reason: stockReasons[row.store_product_id]
      });
      message.success(t("messages.inventoryUpdated"));
      refetchWorkspace();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function saveStock(row: StoreInventoryItem) {
    if (!stockReasons[row.store_product_id]?.trim()) {message.warning(t("erp.reasonRequired"));return;}
    const nextStock = stockDrafts[row.store_product_id] ?? row.current_stock;
    await updateInventory(row, { current_stock: nextStock });
  }

  async function saveStoreStatus() {
    if (!canManageStore) {
      message.warning(t("messages.storeStatusManagerOnly"));
      return;
    }
    try {
      await updateStoreStatusApi(Number(storeId), {
        store_status: storeStatus,
        temporary_close_reason: temporaryCloseReason
      });
      message.success(t("messages.storeStatusUpdated"));
      storesQuery.refetch();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  const orders = ordersQuery.data || [];
  const overview = overviewQuery.data;
  const report = reportQuery.data;
  const inventoryColumns: TableColumnsType<StoreInventoryItem> = [
    {
      title: t("pages.storeWorkspace.product"),
      dataIndex: "name_zh",
      render: (_value, row) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{localizedText(row.name_zh, row.name_en, i18n.language)}</Typography.Text>
          <Typography.Text type="secondary">
            {localizedText(row.category_name_zh, row.category_name_en, i18n.language)} · {t(`status.menu.${row.menu_status}`, { defaultValue: row.menu_status })}
          </Typography.Text>
        </Space>
      )
    },
    {
      title: t("forms.stock"),
      render: (_value, row) => (
        <Space>
          <InputNumber
            min={row.reserved_stock}
            value={stockDrafts[row.store_product_id] ?? row.current_stock}
            disabled={!canManageStore}
            onChange={(value) => setStockDrafts({ ...stockDrafts, [row.store_product_id]: Number(value || row.reserved_stock) })}
          />
          <Button disabled={!canManageStore} onClick={() => saveStock(row)}>
            {t("common.save")}
          </Button>
        </Space>
      )
    },
    {title:t("erp.reason"),render:(_value,row)=><Input disabled={!canManageStore} maxLength={500} placeholder={t("erp.reason")} value={stockReasons[row.store_product_id]} onChange={event=>setStockReasons({...stockReasons,[row.store_product_id]:event.target.value})}/>},
    { title: t("pages.storeWorkspace.reserved"), dataIndex: "reserved_stock" },
    { title: t("pages.storeWorkspace.available"), dataIndex: "available_stock" },
    {
      title: t("forms.available"),
      render: (_value, row) => (
        <Switch
          checked={row.is_available}
          disabled={!canManageStore}
          onChange={(checked) => updateInventory(row, { is_available: checked })}
        />
      )
    },
    {
      title: t("forms.soldOut"),
      render: (_value, row) => (
        <Button
          size="small"
          disabled={!canManageStore}
          type={row.is_sold_out ? "primary" : "default"}
          onClick={() => updateInventory(row, { is_sold_out: !row.is_sold_out })}
        >
          {row.is_sold_out ? t("pages.storeWorkspace.restoreAvailable") : t("pages.storeWorkspace.markSoldOut")}
        </Button>
      )
    }
  ];

  return (
    <Space direction="vertical" size={24} className="full-width">
      <section className="workspace-heading">
        <div>
          <Typography.Text className="page-kicker">{t("pages.storeWorkspace.kicker")}</Typography.Text>
          <Typography.Title level={1}>{t("pages.storeWorkspace.title")}</Typography.Title>
          <Typography.Paragraph>
            {t("pages.storeWorkspace.subtitle", {
              store: localizedText(binding.store_name_zh || binding.store_name, binding.store_name_en, i18n.language),
              role: canManageStore ? t("roles.storeManagerPermission") : t("roles.storeStaffPermission")
            })}
          </Typography.Paragraph>
        </div>
        <Button size="large" icon={<ReloadOutlined />} onClick={refetchWorkspace} loading={ordersQuery.isLoading || inventoryQuery.isLoading}>
          {t("common.refresh")}
        </Button>
      </section>

      {ordersQuery.error ? <Alert type="error" showIcon message={(ordersQuery.error as Error).message}/> : null}
      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <Card className="metric-card"><Statistic title={t("pages.storeWorkspace.metricsTodayOrders")} value={overview?.today_order_count || 0} /></Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="metric-card"><Statistic title={t("pages.storeWorkspace.metricsActiveOrders")} value={overview?.active_order_count || 0} /></Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="metric-card"><Statistic title={t("pages.storeWorkspace.metricsReadyOrders")} value={overview?.ready_order_count || 0} /></Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="metric-card"><Statistic title={t("pages.storeWorkspace.metricsLowStock")} value={overview?.low_stock_count || 0} /></Card>
        </Col>
      </Row>

      <Tabs
        className="workspace-tabs"
        items={[
          {
            key: "overview",
            label: <span><LineChartOutlined /> {t("pages.storeWorkspace.tabOverview")}</span>,
            children: canManageStore ? (
              <Row gutter={[16, 16]}>
                <Col span={24}><ReportPeriods report={report}/></Col>
                <Col xs={24} lg={12}>
                  <Card className="compact-card" title={t("pages.storeWorkspace.summaryTitle")}>
                    <Row gutter={[12, 12]}>
                      <Col span={12}><Statistic title={t("pages.storeWorkspace.todayRevenue")} value={overview?.today_revenue || "0.00"} prefix={i18n.language === "en-US" ? "CNY" : "¥"} /></Col>
                      <Col span={12}><Statistic title={t("pages.storeWorkspace.last7Revenue")} value={report?.last_7_days.revenue || "0.00"} prefix={i18n.language === "en-US" ? "CNY" : "¥"} /></Col>
                      <Col span={12}><Statistic title={t("pages.storeWorkspace.todayCompletedOrders")} value={report?.today.completed_order_count || 0} /></Col>
                      <Col span={12}><Statistic title={t("pages.storeWorkspace.last7Orders")} value={report?.last_7_days.order_count || 0} /></Col>
                    </Row>
                  </Card>
                </Col>
                <Col xs={24} lg={12}>
                  <Card className="compact-card" title={t("pages.storeWorkspace.popularProducts")}>
                    <Space direction="vertical" size={10} className="full-width">
                      {!report?.popular_products.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("pages.storeWorkspace.noSalesData")} /> : null}
                      {report?.popular_products.map((product) => (
                        <div className="popular-row" key={product.product_id}>
                          <div>
                            <Typography.Text strong>{localizedText(product.product_name_zh, product.product_name_en, i18n.language)}</Typography.Text>
                            <Typography.Text type="secondary">{t("common.soldCount", { count: product.sold_quantity })}</Typography.Text>
                          </div>
                          <MoneyText value={product.sales_amount} />
                        </div>
                      ))}
                    </Space>
                  </Card>
                </Col>
              </Row>
            ) : <Alert type="info" message={t("erp.managerReportOnly")}/>
          },
          {
            key: "orders",
            label: <span><ClockCircleOutlined /> {t("pages.storeWorkspace.tabOrders")}</span>,
            children: (
              <>
                <Input.Search className="erp-search" allowClear placeholder={t("erp.orderSearch")} onSearch={setOrderSearch}/>
                <Typography.Paragraph type="secondary">{t("erp.boardToday")}</Typography.Paragraph>
                {!ordersQuery.isLoading && !orders.length ? <Empty description={t("pages.storeWorkspace.noOrders")} /> : null}
                <Row gutter={[16, 16]} className="kanban-board">
                  {kanbanColumns.map((column) => {
                    const columnOrders = orders.filter((order) => order.order_status === column.status);
                    return (
                      <Col xs={24} md={12} xl={6} key={column.status}>
                        <section className="kanban-column">
                          <div className="kanban-title">
                            <Typography.Title level={4}>{t(column.titleKey)}</Typography.Title>
                            <span>{columnOrders.length}</span>
                          </div>
                          <Space direction="vertical" size={12} className="full-width">
                            {columnOrders.map((order) => {
                              const next = nextStatusMap[order.order_status];
                              return (
                                <Card className="order-ticket" key={order.id} loading={ordersQuery.isLoading}>
                                  <Space direction="vertical" size={12} className="full-width">
                                    <div className="row-between">
                                      <Typography.Text strong>{order.order_no}</Typography.Text>
                                      <StatusTag status={order.order_status} namespace="order" />
                                    </div>
                                    <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }}>
                                      {localizedList(
                                        order.items.map((item) => `${localizedText(item.product_name_zh, item.product_name_en, i18n.language)} x${item.quantity}`),
                                        i18n.language
                                      )}
                                    </Typography.Paragraph>
                                    <div className="row-between">
                                      <span className="pickup-mini">
                                        {t("common.pickupCodeValue", { code: order.pickup_code || t("common.notGenerated") })}
                                      </span>
                                      <MoneyText value={order.payable_amount} />
                                    </div>
                                    <Typography.Text>{t(`orderTypes.${order.order_type}`)} · {t("forms.tablewareCount")}: {order.tableware_count}</Typography.Text>
                                    <Typography.Text type="secondary">{t("erp.paidAt")}: {order.paid_at}</Typography.Text>
                                    {order.remark ? <Alert type="info" message={order.remark}/> : null}
                                    <Button onClick={()=>setSelectedOrderId(order.id)}>{t("erp.details")}</Button>
                                    {order.order_status === "ready" ? (
                                      <Input
                                        placeholder={t("forms.pickupCodePlaceholder")}
                                        value={pickupCodes[order.id]}
                                        onChange={(event) => setPickupCodes({ ...pickupCodes, [order.id]: event.target.value })}
                                      />
                                    ) : null}
                                    {next ? (
                                      <Button
                                        block
                                        type="primary"
                                        icon={<CheckCircleOutlined />}
                                        onClick={() => updateStatus(order.id, order.order_status)}
                                      >
                                        {t(next.labelKey)}
                                      </Button>
                                    ) : null}
                                  </Space>
                                </Card>
                              );
                            })}
                          </Space>
                        </section>
                      </Col>
                    );
                  })}
                </Row>
              </>
            )
          },
          {key:"history",label:t("erp.orderHistory"),children:<StoreOrderExplorer storeId={storeId}/>},
          ...(canManageStore ? [{key:"inventory-history",label:t("erp.inventoryHistory"),children:<InventoryHistory storeId={storeId} products={inventoryQuery.data||[]}/>}]:[]),
          {
            key: "inventory",
            label: <span><DatabaseOutlined /> {t("pages.storeWorkspace.tabInventory")}</span>,
            children: (
              <Card className="compact-card">
                {!canManageStore ? <Tag color="gold">{t("common.readonlyStoreManagerOnly")}</Tag> : null}
                <Table
                  className="workspace-table"
                  rowKey="store_product_id"
                  loading={inventoryQuery.isLoading}
                  dataSource={inventoryQuery.data || []}
                  pagination={false}
                  columns={inventoryColumns}
                />
              </Card>
            )
          },
          {
            key: "status",
            label: <span><ToolOutlined /> {t("pages.storeWorkspace.tabStatus")}</span>,
            children: (
              <Card className="compact-card status-console">
                <Space direction="vertical" size={16} className="full-width">
                  <div className="row-between">
                    <div>
                      <Typography.Title level={3}>{t("pages.storeWorkspace.currentStoreStatus")}</Typography.Title>
                      <Typography.Text type="secondary">
                        {localizedText(store?.name_zh || binding.store_name_zh || binding.store_name, store?.name_en || binding.store_name_en, i18n.language)} · {store?.business_start_time}-{store?.business_end_time}
                      </Typography.Text>
                    </div>
                    <Tag color={store?.can_order ? "green" : "orange"} icon={<ShopOutlined />}>
                      {store?.can_order ? t("pages.storeWorkspace.canOrder") : t("pages.storeWorkspace.pauseOrder")}
                    </Tag>
                  </div>
                  <Select
                    className="status-select"
                    options={storeStatusOptions}
                    value={storeStatus}
                    disabled={!canManageStore}
                    onChange={setStoreStatus}
                  />
                  <Input.TextArea
                    rows={4}
                    maxLength={255}
                    showCount
                    disabled={!canManageStore}
                    value={temporaryCloseReason}
                    placeholder={t("forms.temporaryCloseReasonPlaceholder")}
                    onChange={(event) => setTemporaryCloseReason(event.target.value)}
                  />
                  <Button type="primary" size="large" disabled={!canManageStore} onClick={saveStoreStatus}>
                    {t("pages.storeWorkspace.saveStatus")}
                  </Button>
                </Space>
              </Card>
            )
          }
        ]}
      />
      {selectedOrderId ? <StoreOrderExplorer storeId={storeId} initialOrderId={selectedOrderId} onCloseDetail={()=>{setSelectedOrderId(undefined);void refetchWorkspace();}}/> : null}
    </Space>
  );
}

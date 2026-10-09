/**
 * 文件名称：InventoryHistory.tsx
 * 文件用途：库存变更追溯
 * 主要职责：按门店商品与期间展示调整前后库存及原因
 * 所属业务模块：库存
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { useQuery } from "@tanstack/react-query";
import { Alert, Button, Select, Space, Table } from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { listInventoryLogsApi } from "../api/inventory";
import type { StoreInventoryItem } from "../types/domain";
import { localizedText } from "../i18n/localizedText";

export function InventoryHistory({
  storeId,
  products,
}: {
  storeId: number;
  products: StoreInventoryItem[];
}) {
  const { t, i18n } = useTranslation();
  const systemReasons: Record<string, string> = {
    订单创建预占库存: "stockReserved",
    支付成功确认扣减库存: "stockDeducted",
    仿真退款成功恢复已扣减库存: "stockRefundRestored",
    仿真支付失败释放预占库存: "stockPaymentFailed",
    顾客取消仿真支付释放预占库存: "stockPaymentCanceled",
    支付超时释放预占库存: "stockTimedOut",
    顾客取消订单释放预占库存: "stockOrderCanceled",
  };
  const [productId, setProductId] = useState<number>();
  const [days, setDays] = useState(7);
  const [changeType, setChangeType] = useState<string>();
  const query = useQuery({
    queryKey: ["inventory-history", storeId, productId, days, changeType],
    queryFn: () => listInventoryLogsApi(storeId, productId, days, changeType),
  });
  return (
    <Space direction="vertical" className="full-width" size={16}>
      <Space wrap>
        <Select
          allowClear
          placeholder={t("pages.tables.product")}
          style={{ minWidth: 220 }}
          value={productId}
          onChange={setProductId}
          options={products.map((product) => ({
            value: product.store_product_id,
            label: localizedText(
              product.name_zh,
              product.name_en,
              i18n.language,
            ),
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
        <Select
          allowClear
          placeholder={t("erp.changeType")}
          style={{ minWidth: 160 }}
          value={changeType}
          onChange={setChangeType}
          options={[
            "reserve",
            "release",
            "confirm_deduct",
            "refund_restore",
            "manual_adjust",
          ].map((value) => ({ value, label: t(`erp.stock_${value}`) }))}
        />
        <Button onClick={() => query.refetch()}>{t("common.refresh")}</Button>
      </Space>
      {query.error ? (
        <Alert type="error" message={(query.error as Error).message} />
      ) : null}
      <Table
        rowKey="id"
        dataSource={query.data || []}
        loading={query.isFetching}
        scroll={{ x: 900 }}
        columns={[
          { title: t("pages.tables.time"), dataIndex: "created_at" },
          {
            title: t("pages.tables.product"),
            render: (_, row) => {
              const product = products.find(
                (item) => item.store_product_id === row.store_product_id,
              );
              return localizedText(
                product?.name_zh,
                product?.name_en,
                i18n.language,
                String(row.store_product_id),
              );
            },
          },
          {
            title: t("erp.changeType"),
            dataIndex: "change_type",
            render: (value) => t(`erp.stock_${value}`, { defaultValue: value }),
          },
          {
            title: t("forms.stock"),
            render: (_, row) =>
              `${row.before_current_stock} → ${row.after_current_stock}`,
          },
          {
            title: t("pages.storeWorkspace.reserved"),
            render: (_, row) =>
              `${row.before_reserved_stock} → ${row.after_reserved_stock}`,
          },
          { title: t("pages.tables.operator"), dataIndex: "operator_id" },
          {
            title: t("erp.reason"),
            dataIndex: "remark",
            render: (value) =>
              systemReasons[value] ? t(`erp.${systemReasons[value]}`) : value,
          },
        ]}
      />
    </Space>
  );
}

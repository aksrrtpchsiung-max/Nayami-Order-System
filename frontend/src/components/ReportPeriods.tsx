/**
 * 文件名称：ReportPeriods.tsx
 * 文件用途：统一经营报表的期间及口径
 * 主要职责：展示今日、7日、30日订单/退款/核券指标和统计说明
 * 所属业务模块：报表
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { Alert, Space, Table } from "antd";
import { useTranslation } from "react-i18next";
import type { StoreReportSummary } from "../types/domain";
import { MoneyText } from "./MoneyText";

export function ReportPeriods({
  report,
}: {
  report?: {
    today: StoreReportSummary;
    last_7_days: StoreReportSummary;
    last_30_days?: StoreReportSummary;
  };
}) {
  const { t } = useTranslation();
  return (
    <Space direction="vertical" className="full-width">
      <Table
        pagination={false}
        rowKey="period"
        scroll={{ x: 600 }}
        dataSource={
          report
            ? [
                { period: "today", ...report.today },
                { period: "last7", ...report.last_7_days },
                ...(report.last_30_days
                  ? [{ period: "last30", ...report.last_30_days }]
                  : []),
              ]
            : []
        }
        columns={[
          {
            title: t("erp.period"),
            dataIndex: "period",
            render: (value) => t(`erp.${value}`),
          },
          { title: t("erp.orderCount"), dataIndex: "order_count" },
          {
            title: t("erp.completedCount"),
            dataIndex: "completed_order_count",
          },
          { title: t("erp.canceledCount"), dataIndex: "canceled_order_count" },
          { title: t("erp.couponUsedCount"), dataIndex: "coupon_used_count" },
          {
            title: t("erp.revenue"),
            dataIndex: "revenue",
            render: (value) => <MoneyText value={value} />,
          },
        ]}
      />
      <Alert
        type="info"
        showIcon
        message={t("erp.metricDefinitions")}
        description={t("erp.metricExplanation")}
      />
    </Space>
  );
}

/**
 * 文件名称：AuditLogPanel.tsx
 * 文件用途：查询审计与变更证据
 * 主要职责：筛选日志、读取授权详情并展示前后快照
 * 所属业务模块：审计
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Table,
  Tag,
} from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getOperationLogApi,
  listOperationLogsApi,
  type OperationLogFilters,
} from "../api/audit";

export function AuditLogPanel({ scope }: { scope: "brand" | "system" }) {
  const { t } = useTranslation();
  const [filters, setFilters] = useState<OperationLogFilters>({});
  const [selectedId, setSelectedId] = useState<number>();
  const logs = useQuery({
    queryKey: ["audit", scope, filters],
    queryFn: () => listOperationLogsApi({ ...filters, limit: 200 }),
  });
  const detail = useQuery({
    queryKey: ["audit-detail", scope, selectedId],
    queryFn: () => getOperationLogApi(selectedId!),
    enabled: Boolean(selectedId),
  });
  return (
    <Space direction="vertical" size={16} className="full-width">
      <Form layout="inline" onFinish={setFilters} className="erp-filter-form">
        <Form.Item name="operation_module" label={t("pages.tables.module")}>
          <Input allowClear />
        </Form.Item>
        <Form.Item name="operation_type" label={t("pages.tables.operation")}>
          <Input allowClear />
        </Form.Item>
        <Form.Item name="operator_id" label={t("pages.tables.operator")}>
          <InputNumber min={1} precision={0} />
        </Form.Item>
        <Form.Item name="operator_role_code" label={t("pages.tables.role")}>
          <Select
            allowClear
            style={{ minWidth: 160 }}
            options={[
              "customer",
              "store_staff",
              "store_manager",
              "brand_admin",
              "system_admin",
            ].map((value) => ({
              value,
              label: t(`roles.${value}`, { defaultValue: value }),
            }))}
          />
        </Form.Item>
        <Form.Item name="store_id" label={t("pages.tables.store")}>
          <InputNumber min={1} precision={0} />
        </Form.Item>
        <Form.Item name="start_at" label={t("erp.startDate")}>
          <Input type="date" />
        </Form.Item>
        <Form.Item name="end_at" label={t("erp.endDate")}>
          <Input type="date" />
        </Form.Item>
        <Form.Item name="operation_result" label={t("pages.tables.result")}>
          <Select
            allowClear
            style={{ minWidth: 120 }}
            options={["success", "failure", "denied"].map((value) => ({
              value,
              label: t(`status.operation.${value}`, { defaultValue: value }),
            }))}
          />
        </Form.Item>
        <Button htmlType="submit" type="primary">
          {t("erp.search")}
        </Button>
        <Button onClick={() => logs.refetch()}>{t("common.refresh")}</Button>
      </Form>
      {logs.error ? (
        <Alert type="error" message={(logs.error as Error).message} />
      ) : null}
      <Table
        rowKey="id"
        loading={logs.isFetching}
        dataSource={logs.data || []}
        scroll={{ x: 800 }}
        columns={[
          { title: t("pages.tables.time"), dataIndex: "created_at" },
          { title: t("pages.tables.module"), dataIndex: "operation_module" },
          { title: t("pages.tables.operation"), dataIndex: "operation_type" },
          { title: t("pages.tables.operator"), dataIndex: "operator_id" },
          {
            title: t("pages.tables.result"),
            dataIndex: "operation_result",
            render: (value) => (
              <Tag>
                {t(`status.operation.${value}`, { defaultValue: value })}
              </Tag>
            ),
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
      <Drawer
        open={Boolean(selectedId)}
        onClose={() => setSelectedId(undefined)}
        width={720}
        title={t("erp.auditDetails")}
      >
        {detail.error ? (
          <Alert type="error" message={(detail.error as Error).message} />
        ) : null}
        {detail.data ? (
          <Space direction="vertical" className="full-width">
            <Descriptions
              column={1}
              bordered
              items={[
                {
                  key: "operator",
                  label: t("pages.tables.operator"),
                  children: detail.data.operator_id,
                },
                {
                  key: "time",
                  label: t("pages.tables.time"),
                  children: detail.data.created_at,
                },
                {
                  key: "action",
                  label: t("pages.tables.operation"),
                  children: `${detail.data.operation_module} / ${detail.data.operation_type}`,
                },
                {
                  key: "target",
                  label: t("erp.target"),
                  children: detail.data.target_id,
                },
                {
                  key: "store",
                  label: t("pages.tables.store"),
                  children: detail.data.store_id,
                },
                {
                  key: "reason",
                  label: t("erp.reason"),
                  children: detail.data.failure_reason || "—",
                },
              ]}
            />
            <strong>{t("erp.before")}</strong>
            <pre className="erp-snapshot">
              {JSON.stringify(detail.data.before_snapshot, null, 2)}
            </pre>
            <strong>{t("erp.after")}</strong>
            <pre className="erp-snapshot">
              {JSON.stringify(detail.data.after_snapshot, null, 2)}
            </pre>
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
}

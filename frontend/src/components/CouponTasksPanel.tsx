/**
 * 文件名称：CouponTasksPanel.tsx
 * 文件用途：优惠券异步任务检查
 * 主要职责：按活动/状态筛选、查看失败原因、单任务重试
 * 所属业务模块：优惠券运营
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
  Select,
  Space,
  Table,
  message,
} from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getCouponClaimTaskApi,
  listCouponClaimTasksApi,
  retryCouponClaimTaskApi,
} from "../api/coupons";
import type { CouponActivity } from "../types/domain";
import { localizedText } from "../i18n/localizedText";

export function CouponTasksPanel({
  activities,
}: {
  activities: CouponActivity[];
}) {
  const { t, i18n } = useTranslation();
  const [activityId, setActivityId] = useState<number>();
  const [status, setStatus] = useState<string>();
  const [taskId, setTaskId] = useState<number>();
  const [busy, setBusy] = useState(false);
  const currentActivity = activityId || activities[0]?.id;
  const tasks = useQuery({
    queryKey: ["coupon-tasks", currentActivity, status],
    queryFn: () => listCouponClaimTasksApi(currentActivity!, status),
    enabled: Boolean(currentActivity),
    refetchInterval: 5000,
  });
  const task = useQuery({
    queryKey: ["coupon-task", taskId],
    queryFn: () => getCouponClaimTaskApi(taskId!),
    enabled: Boolean(taskId),
  });
  async function retry(id: number) {
    setBusy(true);
    try {
      await retryCouponClaimTaskApi(id);
      await tasks.refetch();
      if (taskId) await task.refetch();
      message.success(t("erp.retryQueued"));
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Space direction="vertical" className="full-width" size={16}>
      <Space wrap>
        <Select
          style={{ minWidth: 240 }}
          value={currentActivity}
          onChange={setActivityId}
          options={activities.map((activity) => ({
            value: activity.id,
            label: localizedText(
              activity.activity_name_zh,
              activity.activity_name_en,
              i18n.language,
            ),
          }))}
        />
        <Select
          allowClear
          placeholder={t("pages.tables.status")}
          style={{ minWidth: 150 }}
          value={status}
          onChange={setStatus}
          options={["pending", "processing", "succeeded", "failed", "dead"].map(
            (value) => ({ value, label: t(`erp.task_${value}`) }),
          )}
        />
        <Button onClick={() => tasks.refetch()}>{t("common.refresh")}</Button>
      </Space>
      {tasks.error ? (
        <Alert type="error" message={(tasks.error as Error).message} />
      ) : null}
      <Table
        rowKey="id"
        dataSource={tasks.data || []}
        loading={tasks.isFetching}
        scroll={{ x: 700 }}
        columns={[
          { title: t("erp.taskId"), dataIndex: "id" },
          { title: t("erp.customer"), dataIndex: "user_id" },
          {
            title: t("pages.tables.status"),
            dataIndex: "task_status",
            render: (value) => t(`erp.task_${value}`),
          },
          { title: t("erp.retryCount"), dataIndex: "retry_count" },
          { title: t("erp.nextRetry"), dataIndex: "next_retry_at" },
          {
            title: t("pages.tables.actions"),
            render: (_, row) => (
              <Space>
                <Button onClick={() => setTaskId(row.id)}>
                  {t("erp.details")}
                </Button>
                {["failed", "dead"].includes(row.task_status) ? (
                  <Button loading={busy} onClick={() => retry(row.id)}>
                    {t("erp.retry")}
                  </Button>
                ) : null}
              </Space>
            ),
          },
        ]}
      />
      <Drawer
        open={Boolean(taskId)}
        title={t("erp.taskDetails")}
        onClose={() => setTaskId(undefined)}
        width={640}
      >
        {task.error ? (
          <Alert type="error" message={(task.error as Error).message} />
        ) : null}
        {task.data ? (
          <Descriptions
            bordered
            column={1}
            items={[
              { key: "id", label: t("erp.taskId"), children: task.data.id },
              {
                key: "status",
                label: t("pages.tables.status"),
                children: t(`erp.task_${task.data.task_status}`),
              },
              {
                key: "user",
                label: t("erp.customer"),
                children: task.data.user_id,
              },
              {
                key: "count",
                label: t("erp.retryCount"),
                children: task.data.retry_count,
              },
              {
                key: "error",
                label: t("erp.reason"),
                children: task.data.last_error || "—",
              },
              {
                key: "time",
                label: t("erp.nextRetry"),
                children: task.data.next_retry_at || "—",
              },
            ]}
          />
        ) : null}
      </Drawer>
    </Space>
  );
}

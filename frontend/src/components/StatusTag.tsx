import { Tag } from "antd";
import { useTranslation } from "react-i18next";

const statusColor: Record<string, string> = {
  pending_payment: "gold",
  paid: "blue",
  accepted: "cyan",
  preparing: "purple",
  ready: "green",
  completed: "success",
  canceled: "default",
  refunded: "default",
  pending: "gold",
  succeeded: "success"
};

export function StatusTag({ status, namespace = "common" }: { status: string; namespace?: string }) {
  const { t } = useTranslation();
  const label = t(`status.${namespace}.${status}`, {
    defaultValue: t(`status.common.${status}`, { defaultValue: status })
  });

  return (
    <Tag className="status-tag" color={statusColor[status] || "default"}>
      {label}
    </Tag>
  );
}

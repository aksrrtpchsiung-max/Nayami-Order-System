import { Typography } from "antd";
import { useTranslation } from "react-i18next";
import { formatCny } from "../i18n/localizedText";

export function MoneyText({ value }: { value: string | number }) {
  const { i18n } = useTranslation();
  return <Typography.Text className="money-text">{formatCny(value, i18n.language)}</Typography.Text>;
}

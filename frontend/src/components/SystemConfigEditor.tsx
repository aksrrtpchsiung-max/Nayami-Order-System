/**
 * 文件名称：SystemConfigEditor.tsx
 * 文件用途：维护允许运行时修改的配置
 * 主要职责：实际配置读取、默认语言/演示模式/支付说明修改
 * 所属业务模块：系统管理
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Descriptions,
  Form,
  Input,
  Select,
  Space,
  Switch,
  message,
} from "antd";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getSystemConfigApi, updateSystemConfigApi } from "../api/system";
import type { SystemConfig } from "../types/domain";
export function SystemConfigEditor() {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [busy, setBusy] = useState(false);
  const config = useQuery({
    queryKey: ["system-config"],
    queryFn: getSystemConfigApi,
  });
  useEffect(() => {
    if (config.data) form.setFieldsValue(config.data);
  }, [config.data, form]);
  async function save(
    values: Pick<
      SystemConfig,
      "demo_mode" | "default_language" | "payment_description"
    >,
  ) {
    setBusy(true);
    try {
      await updateSystemConfigApi(values);
      await config.refetch();
      message.success(t("erp.configSaved"));
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Space direction="vertical" className="full-width" size={24}>
      {config.error ? (
        <Alert type="error" message={(config.error as Error).message} />
      ) : null}
      <Form form={form} layout="vertical" onFinish={save}>
        <Form.Item
          name="default_language"
          label={t("forms.defaultLanguage")}
          rules={[{ required: true }]}
        >
          <Select
            options={[
              { value: "zh-CN", label: t("language.zh") },
              { value: "en-US", label: t("language.en") },
            ]}
          />
        </Form.Item>
        <Form.Item
          name="demo_mode"
          label={t("pages.systemWorkspace.demoMode")}
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
        <Form.Item
          name="payment_description"
          label={t("erp.paymentDescription")}
          rules={[{ max: 500 }]}
        >
          <Input.TextArea maxLength={500} rows={4} showCount />
        </Form.Item>
        <Button
          htmlType="submit"
          type="primary"
          loading={busy}
          disabled={!config.data}
        >
          {t("common.saveChanges")}
        </Button>
      </Form>
      <Descriptions
        bordered
        column={{ xs: 1, md: 2 }}
        items={[
          {
            key: "currency",
            label: t("pages.systemWorkspace.currency"),
            children: config.data?.currency,
          },
          {
            key: "timeout",
            label: t("pages.systemWorkspace.paymentTimeout"),
            children: t("common.minuteWithCount", {
              count: config.data?.payment_timeout_minutes || 0,
            }),
          },
          {
            key: "languages",
            label: t("pages.systemWorkspace.supportedLanguages"),
            children: config.data?.supported_languages.join(" / "),
          },
          {
            key: "payments",
            label: t("pages.systemWorkspace.paymentMethods"),
            children: config.data?.payment_methods
              .map((method) => t(`paymentMethods.${method}`))
              .join(" / "),
          },
          {
            key: "source",
            label: t("pages.systemWorkspace.configSource"),
            children: config.data?.config_storage,
          },
          {
            key: "retry",
            label: t("erp.maxRetries"),
            children: config.data?.coupon_max_retries,
          },
        ]}
      />
    </Space>
  );
}

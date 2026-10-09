/**
 * 文件名称：SystemWorkspacePage.tsx
 * 文件用途：提供账号角色管理、可编辑系统配置与审计筛选
 * 主要职责：提供账号角色管理、可编辑系统配置与审计筛选
 * 所属业务模块：系统管理
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { AuditLogPanel } from "../../components/AuditLogPanel";
import { SystemConfigEditor } from "../../components/SystemConfigEditor";
import {
  AuditOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  TeamOutlined
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Card,
  Col,
  Descriptions,
  Form,
  Input,
  Row,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
  message
} from "antd";
import type { TableColumnsType } from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { listOperationLogsApi } from "../../api/audit";
import { listBrandStoresApi } from "../../api/brand";
import { listRolesApi } from "../../api/permissions";
import { getSystemConfigApi } from "../../api/system";
import {
  createBackendAccountApi,
  listBackendAccountsApi,
  resetBackendAccountPasswordApi,
  updateBackendAccountApi
} from "../../api/users";
import { localizedList, localizedText } from "../../i18n/localizedText";
import type { AccountPayload, BackendAccount, BackendRole, OperationLog } from "../../types/domain";

interface SystemAccountFormValues {
  username: string;
  phone?: string;
  password?: string;
  role_code: string;
  store_id?: number;
  default_language: "zh-CN" | "en-US";
  is_active: boolean;
}

export function SystemWorkspacePage() {
  const { t, i18n } = useTranslation();
  const [accountForm] = Form.useForm<SystemAccountFormValues>();
  const [editingAccountId, setEditingAccountId] = useState<number | null>(null);
  const selectedRoleCode = Form.useWatch("role_code", accountForm) || "store_staff";

  const accountsQuery = useQuery({ queryKey: ["system-accounts"], queryFn: () => listBackendAccountsApi("system") });
  const rolesQuery = useQuery({ queryKey: ["system-roles"], queryFn: listRolesApi });
  const storesQuery = useQuery({ queryKey: ["system-stores"], queryFn: listBrandStoresApi });
  const configQuery = useQuery({ queryKey: ["system-config"], queryFn: getSystemConfigApi });
  const logsQuery = useQuery({ queryKey: ["system-logs"], queryFn: () => listOperationLogsApi({ limit: 200 }) });

  const accounts = accountsQuery.data || [];
  const roles = rolesQuery.data || [];
  const stores = storesQuery.data || [];
  const roleOptions = roles.map((role) => ({ label: t(`roles.${role.role_code}`, { defaultValue: role.role_name }), value: role.role_code }));
  const roleUsesGlobalStoreScope = selectedRoleCode === "brand_admin" || selectedRoleCode === "system_admin";
  const storeOptions = [
    ...(roleUsesGlobalStoreScope ? [{ label: t("common.globalOrUnbound"), value: 0 }] : []),
    ...stores.map((store) => ({ label: `${localizedText(store.name_zh, store.name_en, i18n.language)} · ${store.store_code}`, value: store.id }))
  ];
  const languageOptions = [
    { label: t("language.zh"), value: "zh-CN" },
    { label: t("language.en"), value: "en-US" }
  ];

  async function refetchAll() {
    await Promise.all([
      accountsQuery.refetch(),
      rolesQuery.refetch(),
      storesQuery.refetch(),
      configQuery.refetch(),
      logsQuery.refetch()
    ]);
  }

  async function saveAccount(values: SystemAccountFormValues) {
    try {
      const payload: AccountPayload = { ...values, store_id: values.store_id || undefined };
      if (editingAccountId) {
        await updateBackendAccountApi(editingAccountId, payload, "system");
        message.success(t("messages.backendAccountUpdated"));
      } else {
        const result = await createBackendAccountApi(payload, "system");
        message.success(t("messages.backendAccountCreatedWithPassword", { password: result.temporary_password || t("common.set") }));
      }
      resetAccountForm();
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function resetPassword(accountId: number) {
    try {
      const result = await resetBackendAccountPasswordApi(accountId, "system");
      message.success(t("common.temporaryPassword", { password: result.temporary_password }));
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  function resetAccountForm() {
    setEditingAccountId(null);
    accountForm.resetFields();
    accountForm.setFieldsValue({ role_code: "store_staff", default_language: "zh-CN", is_active: true });
  }

  const accountColumns: TableColumnsType<BackendAccount> = [
    { title: t("pages.tables.account"), dataIndex: "username", render: (_value, row) => <TextStack title={row.username} subtitle={row.phone || "-"} /> },
    { title: t("pages.tables.type"), dataIndex: "user_type" },
    { title: t("pages.tables.role"), render: (_value, row) => row.roles.map((role) => <Tag key={role.role_code}>{t(`roles.${role.role_code}`, { defaultValue: role.role_name })}</Tag>) },
    {
      title: t("pages.tables.storeScope"),
      render: (_value, row) =>
        localizedList(
          row.store_bindings.map((binding) => localizedText(binding.store_name_zh || binding.store_name, binding.store_name_en, i18n.language)),
          i18n.language
        ) || t("common.globalOrUnbound")
    },
    { title: t("pages.tables.lastLogin"), dataIndex: "last_login_at", render: (value?: string) => value || "-" },
    { title: t("pages.tables.status"), dataIndex: "is_active", render: (value: boolean) => <Tag color={value ? "green" : "red"}>{value ? t("common.enabled") : t("common.disabled")}</Tag> },
    {
      title: t("pages.tables.actions"),
      render: (_value, row) => (
        <Space>
          <Button
            size="small"
            onClick={() => {
              const roleCode = row.roles[0]?.role_code || "store_staff";
              setEditingAccountId(row.id);
              accountForm.setFieldsValue({
                username: row.username,
                phone: row.phone,
                role_code: roleCode,
                store_id: roleCode === "brand_admin" || roleCode === "system_admin" ? 0 : row.store_bindings[0]?.store_id,
                default_language: row.default_language as "zh-CN" | "en-US",
                is_active: row.is_active
              });
            }}
          >
            {t("common.edit")}
          </Button>
          <Button
            size="small"
            onClick={() =>
              updateBackendAccountApi(
                row.id,
                { role_code: row.roles[0]?.role_code, store_id: row.store_bindings[0]?.store_id, is_active: !row.is_active },
                "system"
              ).then(refetchAll)
            }
          >
            {row.is_active ? t("common.disabled") : t("common.enabled")}
          </Button>
          <Button size="small" onClick={() => resetPassword(row.id)}>
            {t("pages.systemWorkspace.resetPassword")}
          </Button>
        </Space>
      )
    }
  ];

  const roleColumns: TableColumnsType<BackendRole> = [
    { title: t("pages.tables.roleCode"), dataIndex: "role_code" },
    { title: t("pages.tables.roleName"), render: (_value, row) => t(`roles.${row.role_code}`, { defaultValue: row.role_name }) },
    { title: t("pages.tables.description"), render: (_value, row) => t(`roleDescriptions.${row.role_code}`, { defaultValue: row.description || "-" }) },
    { title: t("pages.tables.permissionCodes"), render: (_value, row) => row.permission_codes.map((code) => <Tag key={code}>{code}</Tag>) }
  ];

  const logColumns: TableColumnsType<OperationLog> = [
    { title: t("pages.tables.time"), dataIndex: "created_at" },
    { title: t("pages.tables.module"), dataIndex: "operation_module" },
    { title: t("pages.tables.operation"), dataIndex: "operation_type" },
    { title: t("pages.tables.operator"), dataIndex: "operator_id" },
    { title: t("pages.tables.role"), dataIndex: "operator_role_code", render: (value?: string) => (value ? t(`roles.${value}`, { defaultValue: value }) : "-") },
    { title: t("pages.tables.result"), dataIndex: "operation_result", render: (value: string) => <Tag color={value === "success" ? "green" : "red"}>{t(`status.operation.${value}`, { defaultValue: value })}</Tag> }
  ];

  const config = configQuery.data;

  return (
    <Space direction="vertical" size={24} className="full-width">
      <section className="workspace-heading system-heading">
        <div>
          <Typography.Text className="page-kicker">{t("pages.systemWorkspace.kicker")}</Typography.Text>
          <Typography.Title level={1}>{t("pages.systemWorkspace.title")}</Typography.Title>
        </div>
        <Button size="large" icon={<ReloadOutlined />} onClick={refetchAll} loading={accountsQuery.isLoading || logsQuery.isLoading}>
          {t("common.refresh")}
        </Button>
      </section>

      <Row gutter={[16, 16]}>
        <Metric title={t("pages.systemWorkspace.backendAccounts")} value={accounts.length} />
        <Metric title={t("pages.systemWorkspace.activeAccounts")} value={accounts.filter((account) => account.is_active).length} />
        <Metric title={t("pages.systemWorkspace.fixedRoles")} value={roles.length} />
        <Metric title={t("pages.systemWorkspace.logRecords")} value={logsQuery.data?.length || 0} />
      </Row>

      <Tabs
        className="workspace-tabs"
        items={[
          {
            key: "accounts",
            label: <span><TeamOutlined /> {t("pages.systemWorkspace.tabAccounts")}</span>,
            children: (
              <Row gutter={[16, 16]}>
                <Col xs={24} xl={8}>
                  <Card className="compact-card" title={editingAccountId ? t("pages.systemWorkspace.editAccount") : t("pages.systemWorkspace.createAccount")}>
                    {editingAccountId ? (
                      <Button className="new-account-shortcut" type="primary" onClick={resetAccountForm} block>
                        {t("pages.systemWorkspace.createAccount")}
                      </Button>
                    ) : null}
                    <Form name="system-account" layout="vertical" form={accountForm} onFinish={saveAccount} initialValues={{ role_code: "store_staff", default_language: "zh-CN", is_active: true }}>
                      <Form.Item name="username" label={t("forms.username")} rules={[{ required: !editingAccountId, message: t("validation.usernameRequired") }]}>
                        <Input disabled={Boolean(editingAccountId)} />
                      </Form.Item>
                      <Form.Item name="phone" label={t("forms.phone")}><Input /></Form.Item>
                      {!editingAccountId ? <Form.Item name="password" label={t("forms.initialPassword")}><Input.Password placeholder={t("forms.defaultPasswordPlaceholder")} /></Form.Item> : null}
                      <Form.Item name="role_code" label={t("forms.role")} rules={[{ required: true, message: t("validation.required") }]}>
                        <Select
                          options={roleOptions}
                          onChange={(roleCode) => {
                            if (roleCode === "brand_admin" || roleCode === "system_admin") {
                              accountForm.setFieldValue("store_id", 0);
                              return;
                            }
                            accountForm.setFieldValue("store_id", undefined);
                          }}
                        />
                      </Form.Item>
                      <Form.Item name="store_id" label={t("forms.storeBinding")}>
                        <Select allowClear={!roleUsesGlobalStoreScope} options={storeOptions} />
                      </Form.Item>
                      <Form.Item name="default_language" label={t("forms.defaultLanguage")}>
                        <Select options={languageOptions} />
                      </Form.Item>
                      <Form.Item name="is_active" label={t("common.enabled")} valuePropName="checked"><Switch /></Form.Item>
                      <Space>
                        <Button type="primary" htmlType="submit">{editingAccountId ? t("common.saveChanges") : t("common.createAccount")}</Button>
                        <Button onClick={resetAccountForm}>{t("common.clear")}</Button>
                      </Space>
                    </Form>
                  </Card>
                </Col>
                <Col xs={24} xl={16}>
                  <Card className="compact-card" title={t("pages.systemWorkspace.accountList")}>
                    <Table rowKey="id" dataSource={accounts} columns={accountColumns} loading={accountsQuery.isLoading} />
                  </Card>
                </Col>
              </Row>
            )
          },
          {
            key: "roles",
            label: <span><SafetyCertificateOutlined /> {t("pages.systemWorkspace.tabRoles")}</span>,
            children: <Card className="compact-card"><Table rowKey="id" dataSource={roles} columns={roleColumns} loading={rolesQuery.isLoading} /></Card>
          },
          {
            key: "config",
            label: <span><SettingOutlined /> {t("pages.systemWorkspace.tabConfig")}</span>,
            children: <Card className="compact-card"><SystemConfigEditor/></Card>
          },
          {
            key: "logs",
            label: <span><AuditOutlined /> {t("pages.systemWorkspace.tabLogs")}</span>,
            children: <Card className="compact-card"><AuditLogPanel scope="system"/></Card>
          }
        ]}
      />
    </Space>
  );
}

function Metric({ title, value }: { title: string; value: string | number }) {
  return (
    <Col xs={12} lg={6}>
      <Card className="metric-card">
        <Statistic title={title} value={value} />
      </Card>
    </Col>
  );
}

function TextStack({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <Space direction="vertical" size={0}>
      <Typography.Text strong>{title}</Typography.Text>
      {subtitle ? <Typography.Text type="secondary">{subtitle}</Typography.Text> : null}
    </Space>
  );
}

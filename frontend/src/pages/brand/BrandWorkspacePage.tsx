/**
 * 文件名称：BrandWorkspacePage.tsx
 * 文件用途：提供门店菜单活动账号维护、版本发布和异常任务追溯
 * 主要职责：提供门店菜单活动账号维护、版本发布和异常任务追溯
 * 所属业务模块：品牌管理
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { AuditLogPanel } from "../../components/AuditLogPanel";
import { CouponTasksPanel } from "../../components/CouponTasksPanel";
import { ReportPeriods } from "../../components/ReportPeriods";
import { StoreOrderExplorer } from "../../components/StoreOrderExplorer";
import {
  ControlOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  GiftOutlined,
  LineChartOutlined,
  ReloadOutlined,
  ShopOutlined,
  TagsOutlined,
  TeamOutlined
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Drawer,
  Button,
  Card,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
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
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { listOperationLogsApi } from "../../api/audit";
import {
  createBrandStoreApi,
  createCategoryApi,
  createCouponApi,
  createProductApi,
  getBrandOverviewApi,
  getBrandReportApi,
  listBrandStoreProductsApi,
  listBrandStoresApi,
  listCategoriesApi,
  listCouponsApi,
  listProductsApi,
  updateBrandStoreApi,
  updateBrandStoreProductApi,
  updateCategoryApi,
  updateCouponApi,
  updateProductApi,
  upsertStoreProductApi
} from "../../api/brand";
import { listRolesApi } from "../../api/permissions";
import {
  listCouponClaimTasksApi,
  reconcileCouponActivityApi,
  retryCouponClaimTaskApi,
  warmupCouponActivityApi
} from "../../api/coupons";
import {
  createBackendAccountApi,
  listBackendAccountsApi,
  resetBackendAccountPasswordApi,
  updateBackendAccountApi
} from "../../api/users";
import { MoneyText } from "../../components/MoneyText";
import { StatusTag } from "../../components/StatusTag";
import { localizedList, localizedText } from "../../i18n/localizedText";
import type {
  BackendAccount,
  BrandProduct,
  BrandStoreProduct,
  CouponActivity,
  OperationLog,
  ProductCategory,
  StoreSummary
} from "../../types/domain";

interface StoreFormValues {
  store_code: string;
  name_zh: string;
  name_en?: string;
  address: string;
  phone?: string;
  business_start_time: string;
  business_end_time: string;
  store_status: "open" | "closed" | "temporarily_closed";
  temporary_close_reason?: string;
  is_active: boolean;
}

interface CategoryFormValues {
  name_zh: string;
  name_en?: string;
  sort_order?: number;
  is_active?: boolean;
}

interface ProductFormValues {
  category_id: number;
  name_zh: string;
  name_en?: string;
  description_zh?: string;
  description_en?: string;
  image_url?: string;
  base_price: number;
  menu_status: string;
  sort_order?: number;
}

interface StoreProductFormValues {
  store_id: number;
  product_id: number;
  current_stock: number;
  is_available: boolean;
  is_sold_out: boolean;
}

interface CouponFormValues {
  activity_name_zh: string;
  activity_name_en?: string;
  description_zh?: string;
  description_en?: string;
  start_at: string;
  end_at: string;
  total_stock: number;
  per_user_limit: number;
  discount_amount: number;
  minimum_order_amount?: number;
  activity_status: string;
  store_ids?: number[];
  product_ids?: number[];
}

interface AccountFormValues {
  username: string;
  phone?: string;
  password?: string;
  role_code: string;
  store_id: number;
  default_language: "zh-CN" | "en-US";
  is_active: boolean;
}

const storeStatusValues = ["open", "temporarily_closed", "closed"] as const;
const menuStatusValues = ["draft", "published", "draft_changes", "archived"] as const;
const couponStatusValues = ["draft", "scheduled", "active", "paused", "ended", "sold_out"] as const;

export function BrandWorkspacePage() {
  const { t, i18n } = useTranslation();
  const [storeForm] = Form.useForm<StoreFormValues>();
  const [categoryForm] = Form.useForm<CategoryFormValues>();
  const [productForm] = Form.useForm<ProductFormValues>();
  const [storeProductForm] = Form.useForm<StoreProductFormValues>();
  const [couponForm] = Form.useForm<CouponFormValues>();
  const [accountForm] = Form.useForm<AccountFormValues>();
  const [editingStoreId, setEditingStoreId] = useState<number | null>(null);
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [editingProductId, setEditingProductId] = useState<number | null>(null);
  const [editingCouponId, setEditingCouponId] = useState<number | null>(null);
  const [editingAccountId, setEditingAccountId] = useState<number | null>(null);
  const [orderStoreId,setOrderStoreId]=useState<number>();
  const [versionProduct,setVersionProduct]=useState<BrandProduct>();
  const [selectedStoreId, setSelectedStoreId] = useState<number | undefined>();

  const overviewQuery = useQuery({ queryKey: ["brand-overview"], queryFn: getBrandOverviewApi });
  const reportQuery = useQuery({ queryKey: ["brand-report"], queryFn: getBrandReportApi });
  const storesQuery = useQuery({ queryKey: ["brand-stores"], queryFn: listBrandStoresApi });
  const categoriesQuery = useQuery({ queryKey: ["brand-categories"], queryFn: listCategoriesApi });
  const productsQuery = useQuery({ queryKey: ["brand-products"], queryFn: listProductsApi });
  const storeProductsQuery = useQuery({
    queryKey: ["brand-store-products", selectedStoreId],
    queryFn: () => listBrandStoreProductsApi(selectedStoreId)
  });
  const couponsQuery = useQuery({ queryKey: ["brand-coupons"], queryFn: listCouponsApi });
  const accountsQuery = useQuery({ queryKey: ["brand-accounts"], queryFn: () => listBackendAccountsApi("brand") });
  const rolesQuery = useQuery({ queryKey: ["brand-roles"], queryFn: listRolesApi });
  const logsQuery = useQuery({ queryKey: ["brand-logs"], queryFn: () => listOperationLogsApi({ limit: 120 }) });

  const stores = storesQuery.data || [];
  const categories = categoriesQuery.data || [];
  const products = productsQuery.data || [];
  const roleOptions = (rolesQuery.data || [])
    .filter((role) => role.role_code === "store_staff" || role.role_code === "store_manager")
    .map((role) => ({ label: t(`roles.${role.role_code}`, { defaultValue: role.role_name }), value: role.role_code }));

  const storeOptions = stores.map((store) => ({ label: `${localizedText(store.name_zh, store.name_en, i18n.language)} · ${store.store_code}`, value: store.id }));
  const categoryOptions = categories.map((category) => ({ label: localizedText(category.name_zh, category.name_en, i18n.language), value: category.id }));
  const productOptions = products.filter(product=>["published","draft_changes"].includes(product.menu_status)).map((product) => ({
    label: `${localizedText(product.name_zh, product.name_en, i18n.language)} · ${t(`status.menu.${product.menu_status}`, { defaultValue: product.menu_status })}`,
    value: product.id
  }));
  const storeStatusOptions = storeStatusValues.map((value) => ({ label: t(`status.store.${value}`), value }));
  const menuStatusOptions = menuStatusValues.map((value) => ({ label: t(`status.menu.${value}`), value }));
  const couponStatusOptions = couponStatusValues.map((value) => ({ label: t(`status.coupon.${value}`), value }));
  const languageOptions = [
    { label: t("language.zh"), value: "zh-CN" },
    { label: t("language.en"), value: "en-US" }
  ];

  const isLoading =
    overviewQuery.isLoading ||
    reportQuery.isLoading ||
    storesQuery.isLoading ||
    categoriesQuery.isLoading ||
    productsQuery.isLoading;

  async function refetchAll() {
    await Promise.all([
      overviewQuery.refetch(),
      reportQuery.refetch(),
      storesQuery.refetch(),
      categoriesQuery.refetch(),
      productsQuery.refetch(),
      storeProductsQuery.refetch(),
      couponsQuery.refetch(),
      accountsQuery.refetch(),
      rolesQuery.refetch(),
      logsQuery.refetch()
    ]);
  }

  async function saveStore(values: StoreFormValues) {
    try {
      if (editingStoreId) {
        await updateBrandStoreApi(editingStoreId, values);
        message.success(t("messages.storeUpdated"));
      } else {
        await createBrandStoreApi(values);
        message.success(t("messages.storeCreated"));
      }
      resetStoreForm();
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function saveCategory(values: CategoryFormValues) {
    try {
      if (editingCategoryId) {
        await updateCategoryApi(editingCategoryId, values);
        message.success(t("messages.categoryUpdated"));
      } else {
        await createCategoryApi({ ...values, sort_order: values.sort_order || 0, is_active: values.is_active ?? true });
        message.success(t("messages.categoryCreated"));
      }
      resetCategoryForm();
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function saveProduct(values: ProductFormValues) {
    try {
      if (editingProductId) {
        await updateProductApi(editingProductId, values);
        message.success(t("messages.productUpdated"));
      } else {
        await createProductApi(values);
        message.success(t("messages.productCreated"));
      }
      resetProductForm();
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function saveStoreProduct(values: StoreProductFormValues) {
    try {
      await upsertStoreProductApi(values);
      message.success(t("messages.storeProductSaved"));
      storeProductForm.resetFields();
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function toggleStoreProduct(row: BrandStoreProduct, payload: Partial<BrandStoreProduct>) {
    try {
      await updateBrandStoreProductApi(row.store_product_id, {
        current_stock: payload.current_stock,
        is_available: payload.is_available,
        is_sold_out: payload.is_sold_out
      });
      message.success(t("messages.storeProductUpdated"));
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function saveCoupon(values: CouponFormValues) {
    try {
      if (editingCouponId) {
        await updateCouponApi(editingCouponId, values);
        message.success(t("messages.couponUpdated"));
      } else {
        await createCouponApi(values);
        message.success(t("messages.couponCreated"));
      }
      resetCouponForm();
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function warmupCoupon(activityId: number) {
    try {
      await warmupCouponActivityApi(activityId);
      message.success(t("messages.couponWarmed"));
      await refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function reconcileCoupon(activityId: number) {
    try {
      await reconcileCouponActivityApi(activityId);
      message.success(t("messages.couponReconciled"));
      await refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function retryFailedCouponTasks(activityId: number) {
    try {
      const tasks = await listCouponClaimTasksApi(activityId);
      const retryableTasks = tasks.filter((task) => task.task_status === "failed" || task.task_status === "dead");
      await Promise.all(retryableTasks.map((task) => retryCouponClaimTaskApi(task.id)));
      message.success(t("messages.couponTasksRetried", { count: retryableTasks.length }));
      await refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function saveAccount(values: AccountFormValues) {
    try {
      if (editingAccountId) {
        await updateBackendAccountApi(editingAccountId, values, "brand");
        message.success(t("messages.accountUpdated"));
      } else {
        const result = await createBackendAccountApi(values, "brand");
        message.success(t("messages.accountCreatedWithPassword", { password: result.temporary_password || t("common.set") }));
      }
      resetAccountForm();
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  async function resetPassword(accountId: number) {
    try {
      const result = await resetBackendAccountPasswordApi(accountId, "brand");
      message.success(t("common.temporaryPassword", { password: result.temporary_password }));
      refetchAll();
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  function resetStoreForm() {
    setEditingStoreId(null);
    storeForm.resetFields();
    storeForm.setFieldsValue({ business_start_time: "09:00", business_end_time: "22:00", store_status: "open", is_active: true });
  }

  function resetCategoryForm() {
    setEditingCategoryId(null);
    categoryForm.resetFields();
    categoryForm.setFieldsValue({ sort_order: 0, is_active: true });
  }

  function resetProductForm() {
    setEditingProductId(null);
    productForm.resetFields();
    productForm.setFieldsValue({ menu_status: "draft", sort_order: 0 });
  }

  function resetCouponForm() {
    setEditingCouponId(null);
    couponForm.resetFields();
    couponForm.setFieldsValue({
      activity_status: "draft",
      per_user_limit: 1,
      total_stock: 100,
      discount_amount: 8,
      minimum_order_amount: 30
    });
  }

  function resetAccountForm() {
    setEditingAccountId(null);
    accountForm.resetFields();
    accountForm.setFieldsValue({ role_code: "store_staff", default_language: "zh-CN", is_active: true });
  }

  const storeColumns: TableColumnsType<StoreSummary> = [
    { title: t("pages.tables.store"), dataIndex: "name_zh", render: (_value, row) => <TextStack title={localizedText(row.name_zh, row.name_en, i18n.language)} subtitle={row.store_code} /> },
    { title: t("pages.tables.address"), dataIndex: "address" },
    { title: t("pages.tables.businessHours"), render: (_value, row) => `${row.business_start_time}-${row.business_end_time}` },
    { title: t("pages.tables.status"), dataIndex: "store_status", render: (value: string) => <StatusTag status={value} namespace="store" /> },
    { title: t("common.enabled"), dataIndex: "is_active", render: (value: boolean) => <Tag color={value ? "green" : "red"}>{value ? t("common.enabled") : t("common.disabled")}</Tag> },
    {
      title: t("pages.tables.actions"),
      render: (_value, row) => (
        <Button
          size="small"
          onClick={() => {
            setEditingStoreId(row.id);
            storeForm.setFieldsValue({
              store_code: row.store_code,
              name_zh: row.name_zh,
              name_en: row.name_en,
              address: row.address,
              phone: row.phone,
              business_start_time: row.business_start_time,
              business_end_time: row.business_end_time,
              store_status: row.store_status as StoreFormValues["store_status"],
              temporary_close_reason: row.temporary_close_reason,
              is_active: row.is_active
            });
          }}
        >
          {t("common.edit")}
        </Button>
      )
    }
  ];

  const categoryColumns: TableColumnsType<ProductCategory> = [
    { title: t("pages.tables.category"), dataIndex: "name_zh", render: (_value, row) => <TextStack title={localizedText(row.name_zh, row.name_en, i18n.language)} subtitle={row.name_en || t("common.notProvidedEnglish")} /> },
    { title: t("pages.tables.sortOrder"), dataIndex: "sort_order" },
    { title: t("common.enabled"), dataIndex: "is_active", render: (value: boolean) => <Tag color={value ? "green" : "red"}>{value ? t("common.enabled") : t("common.disabled")}</Tag> },
    {
      title: t("pages.tables.actions"),
      render: (_value, row) => (
        <Button
          size="small"
          onClick={() => {
            setEditingCategoryId(row.id);
            categoryForm.setFieldsValue(row);
          }}
        >
          {t("common.edit")}
        </Button>
      )
    }
  ];

  const productColumns: TableColumnsType<BrandProduct> = [
    {title:t("pages.tables.product"),render:(_value,row)=><TextStack title={localizedText(row.name_zh,row.name_en,i18n.language)} subtitle={localizedText(row.category_name_zh,row.category_name_en,i18n.language)}/>},
    {title:t("pages.tables.price"),dataIndex:"base_price",render:value=><MoneyText value={value}/>},
    {title:t("pages.tables.status"),dataIndex:"menu_status",render:value=><StatusTag namespace="menu" status={value}/>},
    {title:t("erp.translations"),render:(_value,row)=>row.missing_translations?.length ? <Tag color="orange">{t("erp.missingTranslations",{fields:row.missing_translations.join(", ")})}</Tag> : <Tag color="green">{t("erp.translationsComplete")}</Tag>},
    {title:t("pages.tables.actions"),render:(_value,row)=><Space wrap>
      <Button disabled={row.menu_status==="archived"} onClick={()=>{setEditingProductId(row.id);productForm.setFieldsValue({...row,base_price:Number(row.base_price)});}}>{t("common.edit")}</Button>
      <Button onClick={()=>setVersionProduct(row)}>{t("erp.versions")}</Button>
      {["draft","draft_changes"].includes(row.menu_status)?<Button type="primary" onClick={async()=>{try{await updateProductApi(row.id,{menu_status:"published"});await refetchAll();message.success(t("erp.published"));}catch(error){message.error((error as Error).message);}}}>{t("erp.publish")}</Button>:null}
    </Space>}
  ];

  const storeProductColumns: TableColumnsType<BrandStoreProduct> = [
    { title: t("pages.tables.store"), render: (_value, row) => localizedText(row.store_name_zh || row.store_name, row.store_name_en, i18n.language) },
    { title: t("pages.tables.product"), dataIndex: "name_zh", render: (_value, row) => <TextStack title={localizedText(row.name_zh, row.name_en, i18n.language)} subtitle={localizedText(row.category_name_zh, row.category_name_en, i18n.language)} /> },
    {
      title: t("pages.tables.stock"),
      render: (_value, row) => (
        <InputNumber
          min={row.reserved_stock}
          value={row.current_stock}
          onChange={(value) => toggleStoreProduct(row, { current_stock: Number(value || row.reserved_stock) })}
        />
      )
    },
    { title: t("pages.tables.reserved"), dataIndex: "reserved_stock" },
    { title: t("pages.tables.available"), dataIndex: "available_stock" },
    { title: t("forms.available"), render: (_value, row) => <Switch checked={row.is_available} onChange={(checked) => toggleStoreProduct(row, { is_available: checked })} /> },
    { title: t("forms.soldOut"), render: (_value, row) => <Switch checked={row.is_sold_out} onChange={(checked) => toggleStoreProduct(row, { is_sold_out: checked })} /> }
  ];

  const couponColumns: TableColumnsType<CouponActivity> = [
    { title: t("pages.tables.couponActivity"), dataIndex: "activity_name_zh", render: (_value, row) => <TextStack title={localizedText(row.activity_name_zh, row.activity_name_en, i18n.language)} subtitle={`${row.start_at} - ${row.end_at}`} /> },
    { title: t("pages.tables.status"), dataIndex: "activity_status", render: (value: string) => <StatusTag status={value} namespace="coupon" /> },
    { title: t("pages.tables.remainingStock"), render: (_value, row) => `${row.metrics?.remaining_stock ?? 0}/${row.total_stock}` },
    { title: t("pages.tables.claimed"), render: (_value, row) => row.metrics?.claimed_count ?? 0 },
    { title: t("pages.tables.used"), render: (_value, row) => row.metrics?.used_count ?? 0 },
    {
      title: t("pages.tables.actions"),
      render: (_value, row) => (
        <Space>
          <Button
            size="small"
            onClick={() => {
              setEditingCouponId(row.id);
              couponForm.setFieldsValue({
                ...row,
                discount_amount: Number(row.discount_amount),
                minimum_order_amount: Number(row.minimum_order_amount)
              });
            }}
          >
            {t("common.edit")}
          </Button>
          <Button size="small" onClick={() => updateCouponApi(row.id, { activity_status: "paused" }).then(refetchAll)}>
            {t("pages.brandWorkspace.pause")}
          </Button>
          <Button size="small" onClick={() => updateCouponApi(row.id, { activity_status: "ended" }).then(refetchAll)}>
            {t("pages.brandWorkspace.end")}
          </Button>
          <Button size="small" onClick={() => warmupCoupon(row.id)}>
            {t("pages.brandWorkspace.warmup")}
          </Button>
          <Button size="small" onClick={() => reconcileCoupon(row.id)}>
            {t("pages.brandWorkspace.reconcile")}
          </Button>
          <Button size="small" onClick={() => retryFailedCouponTasks(row.id)}>
            {t("pages.brandWorkspace.retryFailed")}
          </Button>
        </Space>
      )
    }
  ];

  const accountColumns: TableColumnsType<BackendAccount> = [
    { title: t("pages.tables.account"), dataIndex: "username", render: (_value, row) => <TextStack title={row.username} subtitle={row.phone || "-"} /> },
    { title: t("pages.tables.role"), render: (_value, row) => row.roles.map((role) => <Tag key={role.role_code}>{t(`roles.${role.role_code}`, { defaultValue: role.role_name })}</Tag>) },
    {
      title: t("pages.tables.store"),
      render: (_value, row) =>
        localizedList(
          row.store_bindings.map((binding) => localizedText(binding.store_name_zh || binding.store_name, binding.store_name_en, i18n.language)),
          i18n.language
        ) || "-"
    },
    { title: t("pages.tables.status"), dataIndex: "is_active", render: (value: boolean) => <Tag color={value ? "green" : "red"}>{value ? t("common.enabled") : t("common.disabled")}</Tag> },
    {
      title: t("pages.tables.actions"),
      render: (_value, row) => (
        <Space>
          <Button
            size="small"
            onClick={() => {
              setEditingAccountId(row.id);
              accountForm.setFieldsValue({
                username: row.username,
                phone: row.phone,
                role_code: row.roles[0]?.role_code || "store_staff",
                store_id: row.store_bindings[0]?.store_id,
                default_language: row.default_language as "zh-CN" | "en-US",
                is_active: row.is_active
              });
            }}
          >
            {t("common.edit")}
          </Button>
          <Button size="small" onClick={() => updateBackendAccountApi(row.id, { is_active: !row.is_active, role_code: row.roles[0]?.role_code, store_id: row.store_bindings[0]?.store_id }, "brand").then(refetchAll)}>
            {row.is_active ? t("common.disabled") : t("common.enabled")}
          </Button>
          <Button size="small" onClick={() => resetPassword(row.id)}>
            {t("pages.systemWorkspace.resetPassword")}
          </Button>
        </Space>
      )
    }
  ];

  const logColumns: TableColumnsType<OperationLog> = [
    { title: t("pages.tables.time"), dataIndex: "created_at" },
    { title: t("pages.tables.module"), dataIndex: "operation_module" },
    { title: t("pages.tables.operation"), dataIndex: "operation_type" },
    { title: t("pages.tables.role"), dataIndex: "operator_role_code", render: (value?: string) => (value ? t(`roles.${value}`, { defaultValue: value }) : "-") },
    { title: t("pages.tables.result"), dataIndex: "operation_result", render: (value: string) => <Tag color={value === "success" ? "green" : "red"}>{t(`status.operation.${value}`, { defaultValue: value })}</Tag> }
  ];

  const report = reportQuery.data;
  const couponMetricsRows = useMemo(
    () =>
      (couponsQuery.data || []).map((coupon) => ({
        ...coupon,
        key: coupon.id
      })),
    [couponsQuery.data]
  );

  return (
    <Space direction="vertical" size={24} className="full-width">
      <section className="workspace-heading admin-heading">
        <div>
          <Typography.Text className="page-kicker">{t("pages.brandWorkspace.kicker")}</Typography.Text>
          <Typography.Title level={1}>{t("pages.brandWorkspace.title")}</Typography.Title>
          <Typography.Paragraph>{t("pages.brandWorkspace.description")}</Typography.Paragraph>
        </div>
        <Button size="large" icon={<ReloadOutlined />} onClick={refetchAll} loading={isLoading}>
          {t("common.refresh")}
        </Button>
      </section>

      <Row gutter={[16, 16]}>
        <Metric title={t("pages.brandWorkspace.storeCount")} value={overviewQuery.data?.store_count || 0} />
        <Metric title={t("pages.brandWorkspace.todayRevenue")} value={overviewQuery.data?.today_revenue || "0.00"} prefix={i18n.language === "en-US" ? "CNY" : "¥"} />
        <Metric title={t("pages.brandWorkspace.pendingOrders")} value={overviewQuery.data?.pending_order_count || 0} />
        <Metric title={t("pages.brandWorkspace.activeCoupons")} value={overviewQuery.data?.active_coupon_count || 0} />
      </Row>

      <Row gutter={[16,16]}><Metric title={t("erp.openStores")} value={overviewQuery.data?.open_store_count||0}/><Metric title={t("erp.temporarilyClosedStores")} value={overviewQuery.data?.temporarily_closed_store_count||0}/><Metric title={t("erp.closedStores")} value={overviewQuery.data?.closed_store_count||0}/><Metric title={t("erp.couponSyncProblems")} value={(overviewQuery.data?.coupon_sync_failed_count||0)+(overviewQuery.data?.coupon_sync_dead_count||0)}/></Row>
      <Tabs
        className="workspace-tabs"
        items={[
          {
            key: "overview",
            label: <span><LineChartOutlined /> {t("pages.brandWorkspace.tabOverview")}</span>,
            children: (
              <Row gutter={[16, 16]}>
                <Col xs={24} lg={12}>
                  <Card className="compact-card" title={t("pages.brandWorkspace.storeRanking")}>
                    <Table rowKey="store_id" size="small" pagination={false} dataSource={report?.store_rankings || []} columns={[
                      {title:t("erp.storeOrders"),render:(_value,row)=><Button onClick={()=>setOrderStoreId(row.store_id)}>{t("erp.details")}</Button>},
                      { title: t("pages.tables.store"), render: (_value, row) => localizedText(row.store_name_zh, row.store_name_en, i18n.language) },
                      { title: t("pages.brandWorkspace.orderCount"), dataIndex: "order_count" },
                      { title: t("pages.brandWorkspace.revenue"), dataIndex: "revenue", render: (value: string) => <MoneyText value={value} /> }
                    ]} />
                  </Card>
                </Col>
                <Col xs={24} lg={12}>
                  <Card className="compact-card" title={t("pages.brandWorkspace.popularProducts")}>
                    <Space direction="vertical" size={10} className="full-width">
                      {!report?.popular_products.length ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t("pages.brandWorkspace.noSalesData")} /> : null}
                      {report?.popular_products.map((product) => (
                        <div className="popular-row" key={product.product_id}>
                          <TextStack title={localizedText(product.product_name_zh, product.product_name_en, i18n.language)} subtitle={t("common.soldCount", { count: product.sold_quantity })} />
                          <MoneyText value={product.sales_amount} />
                        </div>
                      ))}
                    </Space>
                  </Card>
                </Col>
              </Row>
            )
          },
          {key:"store-orders",label:t("erp.storeOrders"),children:<Select placeholder={t("forms.storeBinding")} style={{minWidth:240}} value={orderStoreId} onChange={setOrderStoreId} options={storeOptions}/>},
          {key:"coupon-tasks",label:t("erp.couponTasks"),children:<CouponTasksPanel activities={couponsQuery.data||[]}/>},
          {
            key: "stores",
            label: <span><ShopOutlined /> {t("pages.brandWorkspace.tabStores")}</span>,
            children: (
              <AdminSection
                form={
                  <Form name="brand-store" layout="vertical" form={storeForm} onFinish={saveStore} initialValues={{ business_start_time: "09:00", business_end_time: "22:00", store_status: "open", is_active: true }}>
                    <FormGrid>
                      <Form.Item name="store_code" label={t("forms.storeCode")} rules={[{ required: true, message: t("validation.required") }]}><Input /></Form.Item>
                      <Form.Item name="name_zh" label={t("forms.nameZh")} rules={[{ required: true, message: t("validation.required") }]}><Input /></Form.Item>
                      <Form.Item extra={t("erp.translationHint")} name="name_en" label={t("forms.nameEn")}><Input /></Form.Item>
                      <Form.Item name="phone" label={t("forms.telephone")}><Input /></Form.Item>
                      <Form.Item name="business_start_time" label={t("forms.businessStart")} rules={[{ required: true, message: t("validation.required") }]}><Input placeholder="09:00" /></Form.Item>
                      <Form.Item name="business_end_time" label={t("forms.businessEnd")} rules={[{ required: true, message: t("validation.required") }]}><Input placeholder="22:00" /></Form.Item>
                      <Form.Item name="store_status" label={t("forms.status")}><Select options={storeStatusOptions} /></Form.Item>
                      <Form.Item name="is_active" label={t("common.enabled")} valuePropName="checked"><Switch /></Form.Item>
                    </FormGrid>
                    <Form.Item name="address" label={t("forms.address")} rules={[{ required: true, message: t("validation.required") }]}><Input /></Form.Item>
                    <Form.Item name="temporary_close_reason" label={t("forms.temporaryCloseReason")}><Input /></Form.Item>
                    <FormActions editing={Boolean(editingStoreId)} onReset={resetStoreForm} />
                  </Form>
                }
                table={<Table rowKey="id" dataSource={stores} columns={storeColumns} loading={storesQuery.isLoading} />}
              />
            )
          },
          {
            key: "menu",
            label: <span><TagsOutlined /> {t("pages.brandWorkspace.tabMenu")}</span>,
            children: (
              <Row gutter={[16, 16]}>
                <Col xs={24} xl={8}>
                  <Card className="compact-card" title={editingCategoryId ? t("pages.brandWorkspace.editCategory") : t("pages.brandWorkspace.newCategory")}>
                    <Form name="brand-category" layout="vertical" form={categoryForm} onFinish={saveCategory} initialValues={{ sort_order: 0, is_active: true }}>
                      <Form.Item name="name_zh" label={t("forms.nameZh")} rules={[{ required: true, message: t("validation.required") }]}><Input /></Form.Item>
                      <Form.Item extra={t("erp.translationHint")} name="name_en" label={t("forms.nameEn")}><Input /></Form.Item>
                      <Form.Item name="sort_order" label={t("forms.sortOrder")}><InputNumber className="full-width" min={0} /></Form.Item>
                      <Form.Item name="is_active" label={t("common.enabled")} valuePropName="checked"><Switch /></Form.Item>
                      <FormActions editing={Boolean(editingCategoryId)} onReset={resetCategoryForm} />
                    </Form>
                  </Card>
                  <Card className="compact-card admin-stack-card" title={t("pages.brandWorkspace.categoryList")}>
                    <Table rowKey="id" size="small" dataSource={categories} columns={categoryColumns} pagination={false} />
                  </Card>
                </Col>
                <Col xs={24} xl={16}>
                  <Card className="compact-card" title={editingProductId ? t("pages.brandWorkspace.editProduct") : t("pages.brandWorkspace.newProduct")}>
                    <Form name="brand-product" layout="vertical" form={productForm} onFinish={saveProduct} initialValues={{ menu_status: "draft", sort_order: 0 }}>
                      <FormGrid>
                        <Form.Item name="category_id" label={t("forms.category")} rules={[{ required: true, message: t("validation.required") }]}><Select options={categoryOptions} /></Form.Item>
                        <Form.Item name="name_zh" label={t("forms.nameZh")} rules={[{ required: true, message: t("validation.required") }]}><Input /></Form.Item>
                        <Form.Item extra={t("erp.translationHint")} name="name_en" label={t("forms.nameEn")}><Input /></Form.Item>
                        <Form.Item name="base_price" label={t("forms.price")} rules={[{ required: true, message: t("validation.required") }]}><InputNumber className="full-width" min={0} precision={2} /></Form.Item>
                        <Form.Item name="menu_status" label={t("forms.menuStatus")}><Select options={menuStatusOptions} /></Form.Item>
                        <Form.Item name="sort_order" label={t("forms.sortOrder")}><InputNumber className="full-width" min={0} /></Form.Item>
                      </FormGrid>
                      <Form.Item name="image_url" label={t("forms.imageUrl")}><Input /></Form.Item>
                      <Form.Item name="description_zh" label={t("forms.descriptionZh")}><Input.TextArea rows={2} /></Form.Item>
                      <Form.Item extra={t("erp.translationHint")} name="description_en" label={t("forms.descriptionEn")}><Input.TextArea rows={2} /></Form.Item>
                      <FormActions editing={Boolean(editingProductId)} onReset={resetProductForm} />
                    </Form>
                  </Card>
                  <Card className="compact-card admin-stack-card" title={t("pages.brandWorkspace.productList")}>
                    <Table rowKey="id" dataSource={products} columns={productColumns} />
                  </Card>
                </Col>
              </Row>
            )
          },
          {
            key: "store-products",
            label: <span><DatabaseOutlined /> {t("pages.brandWorkspace.tabStoreProducts")}</span>,
            children: (
              <AdminSection
                form={
                  <Form name="brand-storeProduct" layout="vertical" form={storeProductForm} onFinish={saveStoreProduct} initialValues={{ current_stock: 0, is_available: true, is_sold_out: false }}>
                    <FormGrid>
                      <Form.Item name="store_id" label={t("forms.store")} rules={[{ required: true, message: t("validation.required") }]}><Select options={storeOptions} /></Form.Item>
                      <Form.Item name="product_id" label={t("forms.product")} rules={[{ required: true, message: t("validation.required") }]}><Select options={productOptions} /></Form.Item>
                      <Form.Item name="current_stock" label={t("forms.stock")}><InputNumber className="full-width" min={0} /></Form.Item>
                      <Form.Item name="is_available" label={t("forms.available")} valuePropName="checked"><Switch /></Form.Item>
                      <Form.Item name="is_sold_out" label={t("forms.soldOut")} valuePropName="checked"><Switch /></Form.Item>
                    </FormGrid>
                    <Button type="primary" htmlType="submit">{t("pages.brandWorkspace.saveStoreProduct")}</Button>
                  </Form>
                }
                table={
                  <>
                    <Select allowClear className="admin-filter" placeholder={t("common.selectStoreFilter")} options={storeOptions} value={selectedStoreId} onChange={setSelectedStoreId} />
                    <Table rowKey="store_product_id" dataSource={storeProductsQuery.data || []} columns={storeProductColumns} loading={storeProductsQuery.isLoading} />
                  </>
                }
              />
            )
          },
          {
            key: "coupons",
            label: <span><GiftOutlined /> {t("pages.brandWorkspace.tabCoupons")}</span>,
            children: (
              <AdminSection
                form={
                  <Form name="brand-coupon" layout="vertical" form={couponForm} onFinish={saveCoupon} initialValues={{ activity_status: "draft", total_stock: 100, per_user_limit: 1, discount_amount: 8, minimum_order_amount: 30 }}>
                    <FormGrid>
                      <Form.Item name="activity_name_zh" label={t("forms.nameZh")} rules={[{ required: true, message: t("validation.required") }]}><Input /></Form.Item>
                      <Form.Item extra={t("erp.translationHint")} name="activity_name_en" label={t("forms.nameEn")}><Input /></Form.Item>
                      <Form.Item name="start_at" label={t("forms.startAt")} rules={[{ required: true, message: t("validation.required") }]}><Input placeholder="2026-05-26 10:00:00" /></Form.Item>
                      <Form.Item name="end_at" label={t("forms.endAt")} rules={[{ required: true, message: t("validation.required") }]}><Input placeholder="2026-05-31 22:00:00" /></Form.Item>
                      <Form.Item name="total_stock" label={t("forms.totalStock")}><InputNumber className="full-width" min={1} /></Form.Item>
                      <Form.Item name="per_user_limit" label={t("forms.perUserLimit")}><InputNumber className="full-width" min={1} /></Form.Item>
                      <Form.Item name="discount_amount" label={t("forms.discountAmount")}><InputNumber className="full-width" min={0} precision={2} /></Form.Item>
                      <Form.Item name="minimum_order_amount" label={t("forms.minimumOrderAmount")}><InputNumber className="full-width" min={0} precision={2} /></Form.Item>
                      <Form.Item name="activity_status" label={t("forms.status")}><Select options={couponStatusOptions} /></Form.Item>
                    </FormGrid>
                    <Form.Item name="store_ids" label={t("forms.applicableStores")}><Select mode="multiple" options={storeOptions} /></Form.Item>
                    <Form.Item name="product_ids" label={t("forms.applicableProducts")}><Select mode="multiple" options={productOptions} /></Form.Item>
                    <Form.Item name="description_zh" label={t("forms.descriptionZh")}><Input.TextArea rows={2} /></Form.Item>
                    <Form.Item extra={t("erp.translationHint")} name="description_en" label={t("forms.descriptionEn")}><Input.TextArea rows={2} /></Form.Item>
                    <FormActions editing={Boolean(editingCouponId)} onReset={resetCouponForm} />
                  </Form>
                }
                table={<Table rowKey="id" dataSource={couponMetricsRows} columns={couponColumns} loading={couponsQuery.isLoading} />}
              />
            )
          },
          {
            key: "report",
            label: <span><FileTextOutlined /> {t("pages.brandWorkspace.tabReport")}</span>,
            children: (
              <Row gutter={[16, 16]}>
                <Col span={24}><ReportPeriods report={report}/></Col>
                <Col xs={24} lg={8}><Card className="metric-card"><Statistic title={t("pages.brandWorkspace.last7Revenue")} value={report?.last_7_days.revenue || "0.00"} prefix={i18n.language === "en-US" ? "CNY" : "¥"} /></Card></Col>
                <Col xs={24} lg={8}><Card className="metric-card"><Statistic title={t("pages.brandWorkspace.paymentSuccessRate")} value={report?.payment_success_rate || "0.0%"} /></Card></Col>
                <Col xs={24} lg={8}><Card className="metric-card"><Statistic title={t("pages.brandWorkspace.couponUsageRate")} value={report?.coupon_summary.usage_rate || "0.0%"} /></Card></Col>
                <Col span={24}>
                  <Card className="compact-card" title={t("pages.brandWorkspace.couponPersistence")}>
                    <Table rowKey="id" dataSource={couponsQuery.data || []} pagination={false} columns={[
                      { title: t("pages.tables.couponActivity"), render: (_value, row: CouponActivity) => localizedText(row.activity_name_zh, row.activity_name_en, i18n.language) },
                      { title: t("pages.brandWorkspace.persistedClaims"), render: (_value, row: CouponActivity) => row.metrics?.claimed_count || 0 },
                      { title: t("pages.brandWorkspace.pendingPersistence"), render: (_value, row: CouponActivity) => row.metrics?.task_counts.pending || 0 },
                      { title: t("pages.brandWorkspace.failed"), render: (_value, row: CouponActivity) => row.metrics?.task_counts.failed || 0 },
                      { title: t("pages.brandWorkspace.dead"), render: (_value, row: CouponActivity) => row.metrics?.task_counts.dead || 0 }
                    ]} />
                  </Card>
                </Col>
              </Row>
            )
          },
          {
            key: "accounts",
            label: <span><TeamOutlined /> {t("pages.brandWorkspace.tabAccounts")}</span>,
            children: (
              <AdminSection
                form={
                  <Form name="brand-account" layout="vertical" form={accountForm} onFinish={saveAccount} initialValues={{ role_code: "store_staff", default_language: "zh-CN", is_active: true }}>
                    <FormGrid>
                      <Form.Item name="username" label={t("forms.username")} rules={[{ required: !editingAccountId, message: t("validation.usernameRequired") }]}><Input disabled={Boolean(editingAccountId)} /></Form.Item>
                      <Form.Item name="phone" label={t("forms.phone")}><Input /></Form.Item>
                      {!editingAccountId ? <Form.Item name="password" label={t("forms.initialPassword")}><Input.Password placeholder={t("forms.defaultPasswordPlaceholder")} /></Form.Item> : null}
                      <Form.Item name="role_code" label={t("forms.role")} rules={[{ required: true, message: t("validation.required") }]}><Select options={roleOptions} /></Form.Item>
                      <Form.Item name="store_id" label={t("forms.storeBinding")} rules={[{ required: true, message: t("validation.required") }]}><Select options={storeOptions} /></Form.Item>
                      <Form.Item name="default_language" label={t("forms.defaultLanguage")}><Select options={languageOptions} /></Form.Item>
                      <Form.Item name="is_active" label={t("common.enabled")} valuePropName="checked"><Switch /></Form.Item>
                    </FormGrid>
                    <FormActions editing={Boolean(editingAccountId)} onReset={resetAccountForm} />
                  </Form>
                }
                table={<Table rowKey="id" dataSource={accountsQuery.data || []} columns={accountColumns} loading={accountsQuery.isLoading} />}
              />
            )
          },
          {
            key: "logs",
            label: <span><ControlOutlined /> {t("pages.brandWorkspace.tabLogs")}</span>,
            children: <Card className="compact-card"><AuditLogPanel scope="brand"/></Card>
          }
        ]}
      />
      <Drawer open={Boolean(orderStoreId)} onClose={()=>setOrderStoreId(undefined)} title={t("erp.storeOrders")} width={1000}>{orderStoreId ? <StoreOrderExplorer key={orderStoreId} storeId={orderStoreId} readOnly/> : null}</Drawer>
      <Drawer open={Boolean(versionProduct)} onClose={()=>setVersionProduct(undefined)} title={t("erp.versions")} width={760}><Alert type="info" message={t("erp.pendingVersionHint")}/><Typography.Title level={4}>{t("erp.liveVersion")}</Typography.Title><pre className="erp-snapshot">{JSON.stringify(versionProduct?.published_content,null,2)}</pre><Typography.Title level={4}>{t("erp.pendingVersion")}</Typography.Title><pre className="erp-snapshot">{JSON.stringify(versionProduct?.pending_changes,null,2)}</pre></Drawer>
    </Space>
  );
}

function Metric({ title, value, prefix }: { title: string; value: string | number; prefix?: string }) {
  return (
    <Col xs={12} lg={6}>
      <Card className="metric-card">
        <Statistic title={title} value={value} prefix={prefix} />
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

function FormGrid({ children }: { children: ReactNode }) {
  return <div className="admin-form-grid">{children}</div>;
}

function FormActions({ editing, onReset }: { editing: boolean; onReset: () => void }) {
  const { t } = useTranslation();

  return (
    <Space>
      <Button type="primary" htmlType="submit">{editing ? t("common.saveChanges") : t("common.create")}</Button>
      <Button onClick={onReset}>{t("common.clear")}</Button>
    </Space>
  );
}

function AdminSection({ form, table }: { form: ReactNode; table: ReactNode }) {
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={8}>
        <Card className="compact-card">{form}</Card>
      </Col>
      <Col xs={24} xl={16}>
        <Card className="compact-card">{table}</Card>
      </Col>
    </Row>
  );
}

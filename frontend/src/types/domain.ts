export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
  };
}

export interface UserRole {
  role_code: string;
  role_name: string;
}

export interface StoreBinding {
  store_id: number;
  store_name: string;
  store_name_zh?: string;
  store_name_en?: string;
  binding_type: string;
  is_active?: boolean;
}

export interface UserProfile {
  id: number;
  username: string;
  phone?: string;
  user_type: "customer" | "staff" | "admin";
  default_language: string;
  roles: UserRole[];
  store_bindings: StoreBinding[];
}

export interface LoginResult {
  access_token: string;
  refresh_token?: string;
  user: UserProfile;
}

export interface RegisterPayload {
  username: string;
  phone: string;
  verification_code: string;
  password: string;
  confirm_password: string;
  default_language?: "zh-CN" | "en-US";
}

export interface VerificationCodeResult {
  phone: string;
  expires_in_seconds: number;
  cooldown_seconds: number;
  verification_code?: string;
}

export interface StoreSummary {
  id: number;
  store_code: string;
  name_zh: string;
  name_en?: string;
  address: string;
  phone?: string;
  business_start_time: string;
  business_end_time: string;
  store_status: string;
  temporary_close_reason?: string;
  is_active: boolean;
  can_order: boolean;
}

export interface MenuProduct {
  store_product_id: number;
  product_id: number;
  name_zh: string;
  name_en?: string;
  description_zh?: string;
  description_en?: string;
  image_url?: string;
  base_price: string;
  current_stock?: number;
  reserved_stock?: number;
  available_stock?: number;
  is_sold_out: boolean;
  can_add_to_cart: boolean;
}

export interface MenuCategory {
  id: number;
  name_zh: string;
  name_en?: string;
  products: MenuProduct[];
}

export interface StoreMenu {
  store: StoreSummary;
  categories: MenuCategory[];
}

export interface OrderItem {
  id: number;
  product_id: number;
  store_product_id: number;
  product_name_zh: string;
  product_name_en?: string;
  unit_price: string;
  quantity: number;
  subtotal_amount: string;
}

export interface PaymentSummary {
  id: number;
  payment_no: string;
  payment_method: string;
  payment_amount: string;
  payment_status: string;
  transaction_no?: string;
  card_brand?: string;
  masked_card_no?: string;
  failure_reason?: string;
  paid_at?: string;
}

export interface OrderDetail {
  id: number;
  order_no: string;
  cancel_reason?: string;
  store_address?: string;
  store_phone?: string;
  customer_name?: string;
  customer_phone_masked?: string;
  status_logs?: Array<{id:number;from_status?:string;to_status:string;reason?:string;created_at:string}>;
  payment_logs?: Array<{id:number;payment_id:number;from_status?:string;to_status:string;event_type:string;created_at:string}>;
  payments?: PaymentSummary[];
  user_id: number;
  store_id: number;
  store_name?: string;
  store_name_zh?: string;
  store_name_en?: string;
  order_type: string;
  order_status: string;
  items_amount: string;
  discount_amount: string;
  payable_amount: string;
  user_coupon_id?: number;
  pickup_code?: string;
  remark?: string;
  tableware_count: number;
  payment_deadline: string;
  paid_at?: string;
  completed_at?: string;
  created_at: string;
  items: OrderItem[];
  payment?: PaymentSummary;
  refund?: {
    id: number;
    refund_no: string;
    refund_status: string;
    refund_amount: string;
    refund_reason?: string;
    simulated_refund_no?: string;
    refunded_at?: string;
  };
}

export interface PaymentDetail extends PaymentSummary {
  order: OrderDetail;
}

export interface PaymentSimulationPayload {
  payment_method: "wechat" | "alipay" | "bank_card";
  result: "success" | "failure" | "cancel";
  idempotency_key: string;
  card_number?: string;
  cardholder_name?: string;
  phone?: string;
  verification_code?: string;
  payment_password?: string;
  expiry?: string;
  cvv?: string;
  billing_country?: string;
  billing_address?: string;
  postal_code?: string;
}

export interface RefundDetail {
  id: number;
  refund_no: string;
  order_id: number;
  payment_id: number;
  refund_amount: string;
  refund_status: string;
  refund_reason?: string;
  simulated_refund_no?: string;
  refunded_at?: string;
  order: OrderDetail;
}

export interface CartItem {
  storeProductId: number;
  productId: number;
  storeId: number;
  nameZh: string;
  nameEn?: string;
  price: string;
  quantity: number;
  availableStock: number;
  imageUrl?: string;
}

export interface StoreInventoryItem {
  store_product_id: number;
  store_id: number;
  product_id: number;
  category_id: number;
  category_name_zh?: string;
  category_name_en?: string;
  name_zh: string;
  name_en?: string;
  image_url?: string;
  base_price: string;
  menu_status: string;
  is_available: boolean;
  current_stock: number;
  reserved_stock: number;
  available_stock: number;
  is_sold_out: boolean;
  can_add_to_cart: boolean;
}

export interface StoreOverview {
  store_id: number;
  today_order_count: number;
  today_revenue: string;
  active_order_count: number;
  paid_order_count: number;
  preparing_order_count: number;
  ready_order_count: number;
  low_stock_count: number;
}

export interface StoreReportSummary {
  order_count: number;
  completed_order_count: number;
  canceled_order_count?: number;
  coupon_used_count?: number;
  revenue: string;
}

export interface StorePopularProduct {
  product_id: number;
  product_name_zh: string;
  product_name_en?: string;
  sold_quantity: number;
  sales_amount: string;
}

export interface StoreReport {
  store_id: number;
  today: StoreReportSummary;
  last_7_days: StoreReportSummary;
  last_30_days?: StoreReportSummary;
  metric_definitions?: Record<string,string>;
  popular_products: StorePopularProduct[];
}

export interface UpdateStoreInventoryPayload {
  reason?: string;
  current_stock?: number;
  is_available?: boolean;
  is_sold_out?: boolean;
}

export interface UpdateStoreStatusPayload {
  store_status: "open" | "closed" | "temporarily_closed";
  temporary_close_reason?: string;
}

export interface BackendRole {
  id: number;
  role_code: string;
  role_name: string;
  description?: string;
  permission_codes: string[];
}

export interface BackendAccount {
  id: number;
  username: string;
  phone?: string;
  user_type: "staff" | "admin";
  default_language: string;
  is_active: boolean;
  last_login_at?: string;
  created_at?: string;
  updated_at?: string;
  roles: UserRole[];
  store_bindings: StoreBinding[];
}

export interface AccountPayload {
  username?: string;
  phone?: string;
  password?: string;
  role_code: string;
  store_id?: number;
  default_language?: "zh-CN" | "en-US";
  is_active?: boolean;
}

export interface AccountMutationResult {
  account: BackendAccount;
  temporary_password?: string;
}

export interface ProductCategory {
  id: number;
  name_zh: string;
  name_en?: string;
  sort_order: number;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ProductCategoryPayload {
  name_zh: string;
  name_en?: string;
  sort_order?: number;
  is_active?: boolean;
}

export interface BrandProduct {
  published_content?: Record<string, unknown>;
  pending_changes?: Record<string, unknown> | null;
  missing_translations?: string[];
  id: number;
  category_id: number;
  category_name_zh?: string;
  category_name_en?: string;
  name_zh: string;
  name_en?: string;
  description_zh?: string;
  description_en?: string;
  image_url?: string;
  base_price: string;
  menu_status: string;
  sort_order: number;
  created_at?: string;
  updated_at?: string;
}

export interface BrandProductPayload {
  category_id: number;
  name_zh: string;
  name_en?: string;
  description_zh?: string;
  description_en?: string;
  image_url?: string;
  base_price: string | number;
  menu_status?: string;
  sort_order?: number;
}

export interface BrandStoreProduct extends StoreInventoryItem {
  store_name?: string;
  store_name_zh?: string;
  store_name_en?: string;
  store_code?: string;
}

export interface StoreProductPayload {
  store_id?: number;
  product_id?: number;
  current_stock?: number;
  is_available?: boolean;
  is_sold_out?: boolean;
}

export interface CouponMetrics {
  claimed_count: number;
  used_count: number;
  remaining_stock: number;
  usage_rate: string;
  task_counts: {
    pending: number;
    processing: number;
    succeeded: number;
    failed: number;
    dead: number;
  };
}

export interface PublicCouponActivity extends CouponActivity {
  effective_status: string;
  remaining_stock?: number;
  claimed_count?: number;
}

export interface UserCoupon {
  id: number | null;
  task_id?: number;
  task_status?: string;
  scope_stores?: Array<{id:number;name_zh:string;name_en?:string}>;
  scope_products?: Array<{id:number;name_zh:string;name_en?:string}>;
  activity_id: number;
  activity_name_zh: string;
  activity_name_en?: string;
  discount_amount: string;
  minimum_order_amount: string;
  coupon_status: string;
  claimed_at: string;
  expired_at?: string;
  used_order_id?: number;
  used_at?: string;
  store_ids: number[];
  product_ids: number[];
}

export interface CouponClaimTask {
  id: number;
  activity_id: number;
  user_id: number;
  user_coupon_id?: number;
  redis_success_time: string;
  task_status: string;
  retry_count: number;
  last_error?: string;
  next_retry_at?: string;
}

export interface CouponClaimResult {
  result: string;
  message_code: string;
  activity_id: number;
  remaining_stock?: number;
  task: CouponClaimTask;
}

export interface CouponActivity {
  id: number;
  activity_name_zh: string;
  activity_name_en?: string;
  description_zh?: string;
  description_en?: string;
  start_at: string;
  end_at: string;
  total_stock: number;
  per_user_limit: number;
  discount_amount: string;
  minimum_order_amount: string;
  activity_status: string;
  created_by?: number;
  store_ids: number[];
  product_ids: number[];
  metrics?: CouponMetrics;
  created_at?: string;
  updated_at?: string;
}

export interface CouponActivityPayload {
  activity_name_zh: string;
  activity_name_en?: string;
  description_zh?: string;
  description_en?: string;
  start_at: string;
  end_at: string;
  total_stock: number;
  per_user_limit?: number;
  discount_amount: string | number;
  minimum_order_amount?: string | number;
  activity_status?: string;
  store_ids?: number[];
  product_ids?: number[];
}

export interface BrandOverview {
  open_store_count?: number;
  temporarily_closed_store_count?: number;
  closed_store_count?: number;
  coupon_sync_pending_count?: number;
  coupon_sync_failed_count?: number;
  coupon_sync_dead_count?: number;
  store_count: number;
  active_store_count: number;
  published_product_count: number;
  active_coupon_count: number;
  today_order_count: number;
  today_revenue: string;
  low_stock_count: number;
  pending_order_count: number;
}

export interface BrandStoreRanking {
  store_id: number;
  store_name_zh: string;
  store_name_en?: string;
  order_count: number;
  revenue: string;
}

export interface BrandCouponSummary {
  claimed_count: number;
  used_count: number;
  usage_rate: string;
}

export interface BrandReport {
  today: StoreReportSummary;
  last_7_days: StoreReportSummary;
  last_30_days?: StoreReportSummary;
  metric_definitions?: Record<string,string>;
  store_rankings: BrandStoreRanking[];
  popular_products: StorePopularProduct[];
  coupon_summary: BrandCouponSummary;
  payment_success_rate: string;
}

export interface OperationLog {
  id: number;
  operator_id?: number;
  operator_role_code?: string;
  operation_module: string;
  operation_type: string;
  target_id?: number;
  store_id?: number;
  before_snapshot?: Record<string, unknown>;
  after_snapshot?: Record<string, unknown>;
  operation_result: string;
  failure_reason?: string;
  ip_address?: string;
  created_at?: string;
}

export interface SystemConfig {
  default_language: "zh-CN" | "en-US";
  payment_description: string;
  payment_mode?: string;
  coupon_max_retries?: number;
  demo_mode: boolean;
  supported_languages: string[];
  currency: string;
  payment_methods: string[];
  payment_timeout_minutes: number;
  config_storage: string;
}

export interface InventoryLog {
  id:number;store_product_id:number;change_type:string;change_quantity:number;
  before_current_stock:number;after_current_stock:number;before_reserved_stock:number;after_reserved_stock:number;
  remark?:string;operator_id?:number;created_at:string;product_name_zh?:string;product_name_en?:string;
}

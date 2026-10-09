/**
 * 文件名称：PaymentPage.tsx
 * 文件用途：显示支付摘要和结果、失败重试及终态操作保护
 * 主要职责：显示支付摘要和结果、失败重试及终态操作保护
 * 所属业务模块：支付仿真
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { OrderFacts } from "../../components/OrderFacts";
import { LoginRedirect } from "../../components/LoginRedirect";
import {
  AlipayCircleOutlined,
  CreditCardOutlined,
  SafetyCertificateOutlined,
  WechatOutlined
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Button,
  Card,
  Col,
  Form,
  Input,
  Radio,
  Row,
  Skeleton,
  Space,
  Statistic,
  Typography,
  message
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { getPaymentApi, retryPaymentApi, simulatePaymentApi } from "../../api/payments";
import { MoneyText } from "../../components/MoneyText";
import { StatusTag } from "../../components/StatusTag";
import { useAuthStore } from "../../stores/authStore";
import type { PaymentSimulationPayload } from "../../types/domain";

type SimulationResult = "success" | "failure" | "cancel";

interface PaymentFormValues {
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

export function PaymentPage() {
  const params = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const paymentId = Number(params.paymentId);
  const [form] = Form.useForm<PaymentFormValues>();
  const [paymentMethod, setPaymentMethod] = useState<PaymentSimulationPayload["payment_method"]>("wechat");
  const [submitting, setSubmitting] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(0);
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["payment", paymentId, user?.id],
    queryFn: () => getPaymentApi(paymentId),
    enabled: Boolean(user && paymentId),
    refetchInterval: (query) => {
      const status = query.state.data?.payment_status;
      return status === "pending" || status === "processing" ? 5000 : false;
    }
  });

  useEffect(() => {
    if (!data?.order.payment_deadline) {
      return;
    }
    const updateCountdown = () => {
      const deadline = new Date(data.order.payment_deadline.replace(" ", "T")).getTime();
      setSecondsRemaining(Math.max(Math.floor((deadline - Date.now()) / 1000), 0));
    };
    updateCountdown();
    const timer = window.setInterval(updateCountdown, 1000);
    return () => window.clearInterval(timer);
  }, [data?.order.payment_deadline]);

  const watchedCardNumber = Form.useWatch("card_number", form);
  const cardBrand = useMemo(() => identifyCardBrand(watchedCardNumber || ""), [watchedCardNumber]);

  if (!user) {
    return <LoginRedirect />;
  }
  if (isLoading) {
    return <Skeleton active />;
  }

  async function submitSimulation(result: SimulationResult) {
    setSubmitting(true);
    try {
      const values = paymentMethod === "bank_card" ? await form.validateFields() : {};
      const response = await simulatePaymentApi(paymentId, {
        ...values,
        payment_method: paymentMethod,
        result,
        idempotency_key: `web-${paymentId}-${result}-${Date.now()}`
      });
      await refetch();
      if (response.payment_status === "succeeded") {
        message.success(t("messages.paymentSimulated"));
        form.resetFields();
      } else {
        message.info(t(`status.payment.${response.payment_status}`));
      }
    } catch (error) {
      const requestError = error as Error & { code?: string };
      if (requestError.code === "payment_expired") {
        message.warning(t("messages.paymentExpired"));
        await refetch();
      } else if (requestError.message) {
        message.error(requestError.message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function retryPayment() {
    if (!data) {
      return;
    }
    setSubmitting(true);
    try {
      const response = await retryPaymentApi(data.order.id, paymentMethod);
      navigate(`/pay/${response.id}`, { replace: true });
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  if (error || !data) return <Alert type="error" showIcon message={(error as Error)?.message || t("errors.payment_not_found")} action={<Button onClick={() => refetch()}>{t("common.refresh")}</Button>}/>;
  const canPay = data.order.order_status === "pending_payment" && ["pending", "processing"].includes(data.payment_status);
  const isTerminal = ["succeeded", "expired"].includes(data?.payment_status || "");
  const canRetry = data.order.order_status === "pending_payment" && secondsRemaining > 0 && ["failed", "canceled"].includes(data.payment_status);

  return (
    <Row className="payment-layout" gutter={[20, 20]} align="middle">
      <Col xs={24} lg={12}>
        <section className="payment-summary-panel">
          <Typography.Text className="page-kicker">{t("pages.payment.kicker")}</Typography.Text>
          <Typography.Title level={1}>{t("pages.payment.title")}</Typography.Title>
          <Typography.Paragraph>{t("pages.payment.description")}</Typography.Paragraph>
          <div className="payment-ticket">
            <div>
              <Typography.Text type="secondary">{t("pages.payment.orderNo")}</Typography.Text>
              <strong>{data?.order.order_no}</strong>
            </div>
            {data ? <StatusTag status={data.payment_status} namespace="payment" /> : null}
          </div>
          <div className="payment-amount">
            <Typography.Text>{t("pages.payment.amount")}</Typography.Text>
            <MoneyText value={data?.payment_amount || "0"} />
          </div>
          {data.payment_status !== "succeeded" ? <Statistic.Countdown
            title={t("pages.payment.countdown")}
            value={Date.now() + secondsRemaining * 1000}
            format="mm:ss"
          /> : <Typography.Paragraph>{t("erp.paidAt")}: {data.paid_at}</Typography.Paragraph>}
          {data?.transaction_no ? (
            <Typography.Text copyable>{data.transaction_no}</Typography.Text>
          ) : null}
        </section>
      </Col>
      <Col xs={24} lg={12}>
        <Card className="payment-card">
          <Space direction="vertical" size={18} className="full-width">
            <Button onClick={() => refetch()}>{t("common.refresh")}</Button>
            <div>
              <Typography.Title level={3}>{t("pages.payment.methodTitle")}</Typography.Title>
              <Typography.Text type="secondary">{t("pages.payment.methodDescription")}</Typography.Text>
            </div>
            <Radio.Group
              className="payment-methods"
              value={paymentMethod}
              disabled={isTerminal}
              onChange={(event) => setPaymentMethod(event.target.value)}
            >
              <Radio.Button value="wechat">
                <WechatOutlined /> {t("paymentMethods.wechat")}
              </Radio.Button>
              <Radio.Button value="alipay">
                <AlipayCircleOutlined /> {t("paymentMethods.alipay")}
              </Radio.Button>
              <Radio.Button value="bank_card">
                <CreditCardOutlined /> {t("paymentMethods.bank_card")}
              </Radio.Button>
            </Radio.Group>
            {paymentMethod === "bank_card" ? (
              <BankCardForm form={form} cardBrand={cardBrand} />
            ) : (
              <div className="payment-safe-note">
                <SafetyCertificateOutlined />
                <span>{t("pages.payment.qrSimulation")}</span>
              </div>
            )}
            <div className="payment-safe-note">
              <SafetyCertificateOutlined />
              <span>{t("pages.payment.safeNote")}</span>
            </div>
            {isTerminal ? (
              <Alert
                showIcon
                type={data?.payment_status === "succeeded" ? "success" : "warning"}
                message={t(`status.payment.${data?.payment_status}`)}
                description={t("pages.payment.returnOrderDetail")}
                action={
                  <Button size="small" onClick={() => navigate(`/orders/${data?.order.id}`)}>
                    {t("pages.payment.returnOrderDetail")}
                  </Button>
                }
              />
            ) : null}
            {canRetry ? (
              <Button block size="large" type="primary" loading={submitting} onClick={retryPayment}>
                {t("pages.payment.retry")}
              </Button>
            ) : (
              <Space.Compact block>
                <Button
                  block
                  size="large"
                  type="primary"
                  loading={submitting}
                  disabled={!canPay || submitting || secondsRemaining <= 0}
                  onClick={() => submitSimulation("success")}
                >
                  {t("pages.payment.simulateSuccess")}
                </Button>
                <Button disabled={!canPay || submitting || secondsRemaining <= 0} onClick={() => submitSimulation("failure")}>
                  {t("pages.payment.simulateFailure")}
                </Button>
                <Button disabled={!canPay || submitting || secondsRemaining <= 0} onClick={() => submitSimulation("cancel")}>
                  {t("pages.payment.simulateCancel")}
                </Button>
              </Space.Compact>
            )}
          </Space>
        </Card>
      </Col>
      <Col span={24}><OrderFacts order={data.order} showLogs={false}/></Col>
    </Row>
  );
}

function BankCardForm({
  form,
  cardBrand
}: {
  form: ReturnType<typeof Form.useForm<PaymentFormValues>>[0];
  cardBrand?: "unionpay" | "visa" | "mastercard";
}) {
  const { t } = useTranslation();
  return (
    <Form form={form} layout="vertical" preserve>
      <Form.Item
        name="card_number"
        label={t("forms.cardNumber")}
        rules={[{ required: true, message: t("validation.required") }]}
      >
        <Input inputMode="numeric" autoComplete="cc-number" placeholder="4111 1111 1111 1111" />
      </Form.Item>
      {cardBrand ? <Alert type="info" showIcon message={t(`cardBrands.${cardBrand}`)} /> : null}
      <Form.Item
        name="cardholder_name"
        label={t("forms.cardholderName")}
        rules={[{ required: true, message: t("validation.required") }]}
      >
        <Input autoComplete="cc-name" />
      </Form.Item>
      {cardBrand === "unionpay" ? (
        <>
          <Form.Item name="phone" label={t("forms.phone")} rules={[{ required: true, message: t("validation.required") }]}>
            <Input autoComplete="tel" />
          </Form.Item>
          <Form.Item name="verification_code" label={t("forms.verificationCode")} rules={[{ required: true, message: t("validation.required") }]}>
            <Input inputMode="numeric" maxLength={6} />
          </Form.Item>
          <Form.Item name="payment_password" label={t("forms.paymentPassword")} rules={[{ required: true, len: 6, message: t("validation.paymentPasswordLength") }]}>
            <Input.Password inputMode="numeric" maxLength={6} />
          </Form.Item>
        </>
      ) : (
        <>
          <Space size={12} className="full-width">
            <Form.Item name="expiry" label={t("forms.expiry")} rules={[{ required: true, message: t("validation.required") }]}>
              <Input placeholder="MM/YY" autoComplete="cc-exp" />
            </Form.Item>
            <Form.Item name="cvv" label="CVV" rules={[{ required: true, message: t("validation.required") }]}>
              <Input.Password inputMode="numeric" maxLength={4} autoComplete="cc-csc" />
            </Form.Item>
          </Space>
          <Form.Item name="billing_country" label={t("forms.billingCountry")} rules={[{ required: true, message: t("validation.required") }]}>
            <Input />
          </Form.Item>
          <Form.Item name="billing_address" label={t("forms.billingAddress")} rules={[{ required: true, message: t("validation.required") }]}>
            <Input />
          </Form.Item>
          <Form.Item name="postal_code" label={t("forms.postalCode")} rules={[{ required: true, message: t("validation.required") }]}>
            <Input />
          </Form.Item>
        </>
      )}
    </Form>
  );
}

function identifyCardBrand(value: string): "unionpay" | "visa" | "mastercard" | undefined {
  const digits = value.replace(/\D/g, "");
  if (digits.startsWith("62")) {
    return "unionpay";
  }
  if (digits.startsWith("4")) {
    return "visa";
  }
  const prefixTwo = Number(digits.slice(0, 2));
  const prefixFour = Number(digits.slice(0, 4));
  if ((prefixTwo >= 51 && prefixTwo <= 55) || (prefixFour >= 2221 && prefixFour <= 2720)) {
    return "mastercard";
  }
  return undefined;
}

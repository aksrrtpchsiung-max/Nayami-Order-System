import { http, unwrapResponse } from "./http";
import type { PaymentDetail, PaymentSimulationPayload, RefundDetail } from "../types/domain";

export function getPaymentApi(paymentId: number) {
  return unwrapResponse<PaymentDetail>(http.get(`/payments/${paymentId}`));
}

export function simulatePaymentSuccessApi(paymentId: number, paymentMethod: string) {
  return unwrapResponse<PaymentDetail>(
    http.post(`/payments/${paymentId}/simulate-success`, {
      payment_method: paymentMethod,
      idempotency_key: `frontend-${paymentId}-${Date.now()}`
    })
  );
}

export function simulatePaymentApi(paymentId: number, payload: PaymentSimulationPayload) {
  return unwrapResponse<PaymentDetail>(http.post(`/payments/${paymentId}/simulate`, payload));
}

export function retryPaymentApi(orderId: number, paymentMethod: string) {
  return unwrapResponse<PaymentDetail>(http.post(`/payments/orders/${orderId}/retry`, { payment_method: paymentMethod }));
}

export function requestRefundApi(orderId: number, reason?: string) {
  return unwrapResponse<RefundDetail>(http.post(`/payments/orders/${orderId}/refund`, { reason }));
}

export function simulateRefundSuccessApi(refundId: number) {
  return unwrapResponse<RefundDetail>(http.post(`/payments/refunds/${refundId}/simulate-success`));
}

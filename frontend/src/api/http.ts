/**
 * 文件名称：http.ts
 * 文件用途：统一身份请求、刷新令牌与错误码本地化
 * 主要职责：统一身份请求、刷新令牌与错误码本地化
 * 所属业务模块：前端网络
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from "axios";
import i18next from "../i18n";
import type { ApiResponse } from "../types/domain";

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 12000
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("nayami_access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshRequest: Promise<string> | null = null;

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiResponse<unknown>>) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const refreshToken = localStorage.getItem("nayami_refresh_token");
    if (error.response?.status !== 401 || !originalRequest || originalRequest._retry || !refreshToken) {
      throw error;
    }
    originalRequest._retry = true;
    try {
      refreshRequest ||= refreshAccessToken(refreshToken);
      const accessToken = await refreshRequest;
      originalRequest.headers.Authorization = `Bearer ${accessToken}`;
      return http.request(originalRequest);
    } catch (refreshError) {
      localStorage.removeItem("nayami_access_token");
      localStorage.removeItem("nayami_refresh_token");
      localStorage.removeItem("nayami_user");
      window.dispatchEvent(new Event("nayami-auth-expired"));
      throw refreshError;
    } finally {
      refreshRequest = null;
    }
  }
);

async function refreshAccessToken(refreshToken: string): Promise<string> {
  const response = await axios.post<ApiResponse<{ access_token: string }>>(
    `${http.defaults.baseURL}/auth/refresh`,
    {},
    { headers: { Authorization: `Bearer ${refreshToken}` }, timeout: 12000 }
  );
  const accessToken = response.data.data.access_token;
  localStorage.setItem("nayami_access_token", accessToken);
  return accessToken;
}

export async function unwrapResponse<T>(request: Promise<AxiosResponse<ApiResponse<T>>>): Promise<T> {
  try {
    const response = await request;
    return response.data.data;
  } catch (error) {
    const axiosError = error as AxiosError<ApiResponse<unknown>>;
    const status = axiosError.response?.status;
    const backendCode = axiosError.response?.data?.error?.code;
    const backendMessage = axiosError.response?.data?.error?.message;
    const translatedBackendMessage = backendCode
      ? i18next.t(`errors.${backendCode}`, { defaultValue: "" })
      : "";
    const message =
      translatedBackendMessage ||
      (i18next.language.startsWith("en") ? "" : backendMessage) ||
      (status && status >= 500
        ? i18next.t("errors.serverUnavailable")
        : axiosError.request
          ? i18next.t("errors.networkUnavailable")
          : i18next.t("errors.requestFailed"));
    const requestError = new Error(message) as Error & { code?: string };
    requestError.code = backendCode;
    throw requestError;
  }
}

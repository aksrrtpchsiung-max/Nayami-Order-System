import { http, unwrapResponse } from "./http";
import type { LoginResult, RegisterPayload, UserProfile, VerificationCodeResult } from "../types/domain";

export function loginApi(username: string, password: string) {
  return unwrapResponse<LoginResult>(http.post("/auth/login", { username, password }));
}

export function registerApi(payload: RegisterPayload) {
  return unwrapResponse<LoginResult>(http.post("/auth/register", payload));
}

export function sendVerificationCodeApi(phone: string) {
  return unwrapResponse<VerificationCodeResult>(http.post("/auth/verification-code", { phone }));
}

export function logoutApi() {
  return unwrapResponse<{ logged_out: boolean }>(http.post("/auth/logout"));
}

export function currentUserApi() {
  return unwrapResponse<UserProfile>(http.get("/auth/me"));
}

import { http, unwrapResponse } from "./http";
import type { AccountMutationResult, AccountPayload, BackendAccount } from "../types/domain";

type AccountScope = "brand" | "system";

function accountBasePath(scope: AccountScope) {
  return scope === "brand" ? "/brand/accounts" : "/system/accounts";
}

export function listBackendAccountsApi(scope: AccountScope = "system") {
  return unwrapResponse<BackendAccount[]>(http.get(accountBasePath(scope)));
}

export function createBackendAccountApi(payload: AccountPayload, scope: AccountScope = "system") {
  return unwrapResponse<AccountMutationResult>(http.post(accountBasePath(scope), payload));
}

export function updateBackendAccountApi(accountId: number, payload: Partial<AccountPayload>, scope: AccountScope = "system") {
  return unwrapResponse<BackendAccount>(http.patch(`${accountBasePath(scope)}/${accountId}`, payload));
}

export function resetBackendAccountPasswordApi(accountId: number, scope: AccountScope = "system") {
  return unwrapResponse<AccountMutationResult>(http.post(`${accountBasePath(scope)}/${accountId}/reset-password`));
}

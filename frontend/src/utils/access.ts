import type { UserProfile } from "../types/domain";

export const STORE_ROLES = ["store_staff", "store_manager"];
export const STORE_MANAGER_ROLES = ["store_manager"];
export const BRAND_ROLES = ["brand_admin"];
export const SYSTEM_ROLES = ["system_admin"];

export function hasRole(user: UserProfile | null | undefined, roleCodes: string[]) {
  return Boolean(user?.roles?.some((role) => roleCodes.includes(role.role_code)));
}

export function isStoreWorkspaceUser(user: UserProfile | null | undefined) {
  return hasRole(user, STORE_ROLES);
}

export function isStoreManager(user: UserProfile | null | undefined) {
  return hasRole(user, STORE_MANAGER_ROLES);
}

export function isBrandAdmin(user: UserProfile | null | undefined) {
  return hasRole(user, BRAND_ROLES);
}

export function isSystemAdmin(user: UserProfile | null | undefined) {
  return hasRole(user, SYSTEM_ROLES);
}

export function isBackofficeUser(user: UserProfile | null | undefined) {
  return isStoreWorkspaceUser(user) || isBrandAdmin(user) || isSystemAdmin(user);
}

export function defaultRouteForUser(user: UserProfile) {
  if (isSystemAdmin(user)) {
    return "/system/workspace";
  }
  if (isBrandAdmin(user)) {
    return "/brand/workspace";
  }
  if (isStoreWorkspaceUser(user)) {
    return user.store_bindings?.[0] ? "/store/workspace" : "/store/unbound";
  }
  return "/stores";
}

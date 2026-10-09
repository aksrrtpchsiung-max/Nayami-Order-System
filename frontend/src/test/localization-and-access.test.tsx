/**
 * 文件名称：localization-and-access.test.tsx
 * 文件用途：验证前端国际化展示、语言化路由和角色入口规则
 * 主要职责：覆盖双语回退、状态翻译、无前缀路径补全和角色默认工作台
 * 所属业务模块：前端自动化测试
 * 创建时间：2026-08-06 11:59
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusTag } from "../components/StatusTag";
import i18next from "../i18n";
import { formatCny, localizedText } from "../i18n/localizedText";
import { buildLocalizedLegacyPath } from "../i18n/routing";
import type { UserProfile } from "../types/domain";
import { defaultRouteForUser, isStoreManager } from "../utils/access";

function userWithRole(roleCode: string): UserProfile {
  return {
    id: 1,
    username: "test-user",
    user_type: "staff",
    default_language: "zh-CN",
    roles: [{ role_code: roleCode, role_name: roleCode }],
    store_bindings: []
  };
}

describe("localized business presentation", () => {
  it("uses English text when available and falls back to Chinese", () => {
    expect(localizedText("招牌牛肉饭", "Signature Beef Rice", "en-US")).toBe("Signature Beef Rice");
    expect(localizedText("招牌牛肉饭", null, "en-US")).toBe("招牌牛肉饭");
    expect(formatCny("38.00", "en-US")).toContain("38.00");
  });

  it("renders translated order statuses", async () => {
    await i18next.changeLanguage("en-US");
    render(<StatusTag status="paid" namespace="order" />);
    expect(screen.getByText("Paid")).toBeInTheDocument();
  });
});

describe("localized application routing", () => {
  it("keeps the requested page when adding a missing Chinese language prefix", () => {
    expect(buildLocalizedLegacyPath("/login", "zh-CN")).toBe("/zh/login");
    expect(buildLocalizedLegacyPath("/checkout", "zh-CN", "?from=cart", "#payment")).toBe(
      "/zh/checkout?from=cart#payment"
    );
  });

  it("uses the English prefix and sends the root path to stores", () => {
    expect(buildLocalizedLegacyPath("/login", "en-US")).toBe("/en/login");
    expect(buildLocalizedLegacyPath("/", "en-US")).toBe("/en/stores");
  });
});

describe("role-based workspace routing", () => {
  it("keeps system, brand and store roles in separate default workspaces", () => {
    expect(defaultRouteForUser(userWithRole("system_admin"))).toBe("/system/workspace");
    expect(defaultRouteForUser(userWithRole("brand_admin"))).toBe("/brand/workspace");
    expect(defaultRouteForUser(userWithRole("store_staff"))).toBe("/store/unbound");
    expect(isStoreManager(userWithRole("store_manager"))).toBe(true);
  });
});

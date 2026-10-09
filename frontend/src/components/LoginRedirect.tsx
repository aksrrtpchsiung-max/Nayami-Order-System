/**
 * 文件名称：LoginRedirect.tsx
 * 文件用途：保存未登录用户的业务目标
 * 主要职责：语言路由回跳与外部跳转防护
 * 所属业务模块：身份认证
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import type { UserProfile } from "../types/domain";
import { Navigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function safeReturnPath(value: unknown, fallback: string): string {
  // 仅允许已知业务页面，拒绝协议、反斜杠及重复编码的路径分隔符。
  if (
    typeof value !== "string" ||
    /[\\\u0000-\u001f]/.test(value) ||
    /%25|%2f|%5c/i.test(value)
  )
    return fallback;
  return /^\/(zh|en)\/(checkout|pay\/\d+|orders\/\d+|my\/(orders|coupons)|coupons|me|stores(?:\/\d+\/menu)?|(?:store|brand|system)\/workspace)(?:[?#].*)?$/.test(
    value,
  )
    ? value
    : fallback;
}

export function LoginRedirect() {
  const location = useLocation();
  const { i18n } = useTranslation();
  const language = i18n.language === "en-US" ? "en" : "zh";
  const returnTo = location.pathname + location.search + location.hash;
  return (
    <Navigate
      to={`/${language}/login?returnTo=${encodeURIComponent(returnTo)}`}
      replace
    />
  );
}

/**
 * 函数名称：returnPathForUser
 * 函数用途：登录后恢复与当前角色相符的目标，防止切换账号后进入旧角色流程。
 * 参数说明：value 为回跳参数，user 为登录响应用户，fallback 为角色默认入口。
 * 返回值说明：当前角色可用的站内路径。核心逻辑：先检查路径，再限制后台账号回到其工作台。
 * 异常或失败情况：无效路径或角色不匹配时返回默认入口。
 * 最近修改时间：2026-10-09 14:06；修改人：Project Maintainers
 */
export function returnPathForUser(
  value: unknown,
  user: UserProfile,
  fallback: string,
): string {
  const target = safeReturnPath(value, fallback);
  if (user.user_type === "customer")
    return /^\/(zh|en)\/(store|brand|system)\//.test(target)
      ? fallback
      : target;
  return target.split(/[?#]/)[0] === fallback.split(/[?#]/)[0]
    ? target
    : fallback;
}

/**
 * 文件名称：routing.ts
 * 文件用途：集中生成带界面语言前缀的前端路由
 * 主要职责：为无语言前缀的历史路径补充 zh/en 前缀，并保留查询参数与页面锚点
 * 所属业务模块：国际化与前端路由
 * 创建时间：2026-08-06 12:02
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */

export function buildLocalizedLegacyPath(
  pathname: string,
  interfaceLanguage: string,
  search = "",
  hash = ""
): string {
  /**
   * 函数名称：buildLocalizedLegacyPath
   * 函数用途：将无语言前缀的应用路径转换成可直接访问的中英文路径
   * 参数说明：pathname 为业务路径，interfaceLanguage 为当前界面语言，search/hash 为查询参数和锚点
   * 返回值说明：返回以 /zh 或 /en 开头的完整前端路径
   * 核心逻辑：根路径默认进入门店列表，其余路径保持原业务目标并补充当前语言前缀
   * 异常或失败情况：无；空路径按根路径处理
   * 相关业务规则：路由补前缀时不得丢失登录、结算等原目标页面，也不得丢失查询参数和锚点
   * 最近修改时间：2026-10-09 14:06
   * 修改人：Project Maintainers
   */

  const languagePrefix = interfaceLanguage === "en-US" ? "en" : "zh";
  const normalizedPathname = !pathname || pathname === "/"
    ? "/stores"
    : pathname.startsWith("/")
      ? pathname
      : `/${pathname}`;
  return `/${languagePrefix}${normalizedPathname}${search}${hash}`;
}

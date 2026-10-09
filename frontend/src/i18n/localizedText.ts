export function isEnglishLanguage(language?: string) {
  return Boolean(language?.toLowerCase().startsWith("en"));
}

export function localizedText(
  zhText?: string | null,
  enText?: string | null,
  language?: string,
  fallback = "-"
) {
  const normalizedZhText = zhText?.trim();
  const normalizedEnText = enText?.trim();
  if (isEnglishLanguage(language)) {
    return normalizedEnText || normalizedZhText || fallback;
  }
  return normalizedZhText || normalizedEnText || fallback;
}

export function localizedList(items: string[], language?: string) {
  return items.join(isEnglishLanguage(language) ? ", " : "，");
}

export function formatCny(value: string | number | undefined | null, language?: string) {
  return new Intl.NumberFormat(isEnglishLanguage(language) ? "en-US" : "zh-CN", {
    style: "currency",
    currency: "CNY",
    currencyDisplay: isEnglishLanguage(language) ? "code" : "symbol"
  }).format(Number(value || 0));
}

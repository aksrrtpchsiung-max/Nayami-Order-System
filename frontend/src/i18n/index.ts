import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import enUS from "./locales/en-US.json";
import zhCN from "./locales/zh-CN.json";

const STORAGE_LANGUAGE_KEY = "nayami_language";
const supportedLanguages = ["zh-CN", "en-US"];
const storedLanguage = localStorage.getItem(STORAGE_LANGUAGE_KEY);
const initialLanguage = storedLanguage && supportedLanguages.includes(storedLanguage) ? storedLanguage : "zh-CN";

i18next.use(initReactI18next).init({
  resources: {
    "zh-CN": { translation: zhCN },
    "en-US": { translation: enUS }
  },
  lng: initialLanguage,
  fallbackLng: "zh-CN",
  supportedLngs: supportedLanguages,
  interpolation: { escapeValue: false }
});

i18next.on("languageChanged", (language) => {
  if (supportedLanguages.includes(language)) {
    localStorage.setItem(STORAGE_LANGUAGE_KEY, language);
    document.documentElement.lang = language;
  }
});

document.documentElement.lang = initialLanguage;

export default i18next;

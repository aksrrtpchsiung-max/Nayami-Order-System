import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import enUS from "antd/locale/en_US";
import zhCN from "antd/locale/zh_CN";
import { useTranslation } from "react-i18next";
import "antd/dist/reset.css";
import "./i18n";
import "./styles/global.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <LocalizedConfigProvider>
      <App />
    </LocalizedConfigProvider>
  </React.StrictMode>
);

function LocalizedConfigProvider({ children }: { children: React.ReactNode }) {
  const { i18n } = useTranslation();

  return (
    <ConfigProvider
      locale={i18n.language === "en-US" ? enUS : zhCN}
      theme={{
        token: {
          colorPrimary: "#f47a1f",
          colorInfo: "#177b78",
          colorSuccess: "#6f7d32",
          colorWarning: "#ffc766",
          colorError: "#df4e24",
          borderRadius: 8,
          fontFamily: 'Bahnschrift, "Microsoft YaHei UI", "Segoe UI", sans-serif'
        }
      }}
    >
      {children}
    </ConfigProvider>
  );
}

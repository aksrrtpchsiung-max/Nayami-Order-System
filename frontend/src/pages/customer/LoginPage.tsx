/**
 * 文件名称：LoginPage.tsx
 * 文件用途：处理注册登录、验证码与当前角色安全回跳
 * 主要职责：处理注册登录、验证码与当前角色安全回跳
 * 所属业务模块：顾客认证
 * 创建时间：2026-09-08 17:47
 * 最近修改时间：2026-10-09 14:06
 * 修改人：Project Maintainers
 */
import { returnPathForUser } from "../../components/LoginRedirect";
import { LoginOutlined, UserAddOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Space, Tabs, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { loginApi, registerApi, sendVerificationCodeApi } from "../../api/auth";
import nayamiLogoUrl from "../../assets/nayami-logo.png";
import { useAuthStore } from "../../stores/authStore";
import { defaultRouteForUser } from "../../utils/access";

interface LoginForm {
  username: string;
  password: string;
}

interface RegisterForm {
  username: string;
  phone: string;
  verification_code: string;
  password: string;
  confirm_password: string;
}

type AuthMode = "login" | "register";

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnAfterAuth = (user: import("../../types/domain").UserProfile) => returnPathForUser(searchParams.get("returnTo"), user, `/${i18n.language === "en-US" ? "en" : "zh"}${defaultRouteForUser(user)}`);
  const { t, i18n } = useTranslation();
  const setAuth = useAuthStore((state) => state.setAuth);
  const [loading, setLoading] = useState(false);
  const [activeMode, setActiveMode] = useState<AuthMode>("login");
  const [registerForm] = Form.useForm<RegisterForm>();
  const [verificationCooldown, setVerificationCooldown] = useState(0);

  useEffect(() => {
    if (verificationCooldown <= 0) {
      return;
    }
    const timer = window.setTimeout(() => setVerificationCooldown((value) => value - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [verificationCooldown]);

  async function handleLogin(values: LoginForm) {
    setLoading(true);
    try {
      const result = await loginApi(values.username, values.password);
      setAuth(result.access_token, result.user, result.refresh_token);
      message.success(t("messages.loginSuccess"));
      navigate(returnAfterAuth(result.user), { replace: true });
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(values: RegisterForm) {
    setLoading(true);
    try {
      const result = await registerApi({ ...values, default_language: i18n.language === "en-US" ? "en-US" : "zh-CN" });
      setAuth(result.access_token, result.user, result.refresh_token);
      message.success(t("messages.registerSuccess"));
      navigate(returnAfterAuth(result.user), { replace: true });
    } catch (error) {
      message.error((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function sendVerificationCode() {
    const phone = registerForm.getFieldValue("phone");
    if (!phone) {
      message.warning(t("validation.phoneRequired"));
      return;
    }
    try {
      const result = await sendVerificationCodeApi(phone);
      setVerificationCooldown(result.cooldown_seconds);
      message.success(
        result.verification_code
          ? t("messages.verificationCodeDemo", { code: result.verification_code })
          : t("messages.verificationCodeSent")
      );
    } catch (error) {
      message.error((error as Error).message);
    }
  }

  return (
    <div className="center-page">
      <Card className="login-panel">
        <Space direction="vertical" size={16} className="full-width">
          <div className="login-brand">
            <img className="brand-logo" src={nayamiLogoUrl} alt="Nayami Bistro" />
            <div>
              <Typography.Text className="page-kicker">{t("app.brandFull")}</Typography.Text>
              <Typography.Title level={2}>
                {activeMode === "login" ? t("pages.login.titleLogin") : t("pages.login.titleRegister")}
              </Typography.Title>
            </div>
          </div>
          <Tabs
            activeKey={activeMode}
            onChange={(key) => setActiveMode(key as AuthMode)}
            items={[
              {
                key: "login",
                label: t("pages.login.titleLogin"),
                children: (
                  <Form<LoginForm>
                    layout="vertical"
                    onFinish={handleLogin}
                  >
                    <Form.Item name="username" label={t("forms.username")} rules={[{ required: true, message: t("validation.usernameRequired") }]}>
                      <Input autoComplete="username" />
                    </Form.Item>
                    <Form.Item name="password" label={t("forms.password")} rules={[{ required: true, message: t("validation.passwordRequired") }]}>
                      <Input.Password autoComplete="current-password" />
                    </Form.Item>
                    <Button block size="large" type="primary" htmlType="submit" icon={<LoginOutlined />} loading={loading}>
                      {t("pages.login.submitLogin")}
                    </Button>
                  </Form>
                )
              },
              {
                key: "register",
                label: t("pages.login.titleRegister"),
                children: (
                  <Form<RegisterForm>
                    form={registerForm}
                    layout="vertical"
                    onFinish={handleRegister}
                  >
                    <Form.Item
                      name="username"
                      label={t("forms.username")}
                      rules={[
                        { required: true, message: t("validation.usernameRequired") },
                        { max: 64, message: t("validation.usernameMax") }
                      ]}
                    >
                      <Input autoComplete="username" placeholder={t("forms.usernamePlaceholder")} />
                    </Form.Item>
                    <Form.Item
                      name="phone"
                      label={t("forms.phone")}
                      rules={[
                        { required: true, message: t("validation.phoneRequired") },
                        { max: 32, message: t("validation.phoneMax") }
                      ]}
                    >
                      <Input autoComplete="tel" placeholder={t("forms.phonePlaceholder")} />
                    </Form.Item>
                    <Form.Item label={t("forms.verificationCode")} required>
                      <Space.Compact block>
                        <Form.Item
                          name="verification_code"
                          noStyle
                          rules={[{ required: true, message: t("validation.verificationCodeRequired") }]}
                        >
                          <Input inputMode="numeric" maxLength={6} autoComplete="one-time-code" />
                        </Form.Item>
                        <Button disabled={verificationCooldown > 0} onClick={sendVerificationCode}>
                          {verificationCooldown > 0
                            ? t("forms.resendSeconds", { count: verificationCooldown })
                            : t("forms.sendVerificationCode")}
                        </Button>
                      </Space.Compact>
                    </Form.Item>
                    <Form.Item
                      name="password"
                      label={t("forms.password")}
                      rules={[
                        { required: true, message: t("validation.passwordRequired") },
                        { min: 8, message: t("validation.passwordMin") }
                      ]}
                    >
                      <Input.Password autoComplete="new-password" />
                    </Form.Item>
                    <Form.Item
                      name="confirm_password"
                      label={t("forms.confirmPassword")}
                      dependencies={["password"]}
                      rules={[
                        { required: true, message: t("validation.confirmPasswordRequired") },
                        ({ getFieldValue }) => ({
                          validator(_, value) {
                            return !value || getFieldValue("password") === value
                              ? Promise.resolve()
                              : Promise.reject(new Error(t("validation.passwordMismatch")));
                          }
                        })
                      ]}
                    >
                      <Input.Password autoComplete="new-password" />
                    </Form.Item>
                    <Button block size="large" type="primary" htmlType="submit" icon={<UserAddOutlined />} loading={loading}>
                      {t("pages.login.submitRegister")}
                    </Button>
                  </Form>
                )
              }
            ]}
          />
        </Space>
      </Card>
    </div>
  );
}

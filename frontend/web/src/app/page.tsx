"use client";

import { LanguageToggle } from "@/components/language-toggle";
import { RubikCube } from "@/components/rubik-cube";
import { ScrollReveal } from "@/components/scroll-reveal";
import { apiRequest, AuthResponse, VerificationResponse } from "@/lib/api";
import { clearPersistedAuth, isAuthenticated, persistAuth, persistLocale, readPersistedAuth, readPersistedLocale } from "@/lib/auth";
import { Locale, dictionary } from "@/lib/content";
import { ArrowRight, Languages, LoaderCircle, LogIn, LogOut, MailCheck, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

export default function Home() {
  const router = useRouter();
  const [locale, setLocale] = useState<Locale>("vi");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authInfo, setAuthInfo] = useState<string | null>(null);
  const [verificationInfo, setVerificationInfo] = useState<VerificationResponse | null>(null);
  const [authResult, setAuthResult] = useState<AuthResponse | null>(null);
  const [hydratedAuth, setHydratedAuth] = useState(false);
  const [submittingRegister, setSubmittingRegister] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setAuthResult(readPersistedAuth());
      setLocale(readPersistedLocale() ?? "vi");
      setHydratedAuth(true);
    });

    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    persistLocale(locale);
  }, [locale]);

  const [submittingVerify, setSubmittingVerify] = useState(false);
  const [submittingLogin, setSubmittingLogin] = useState(false);
  const [authForm, setAuthForm] = useState({
    fullName: "",
    email: "",
    password: "",
    code: "",
  });

  const t = useMemo(() => dictionary[locale], [locale]);
  const signedIn = hydratedAuth && isAuthenticated(authResult);
  const authEyebrow = signedIn ? (locale === "vi" ? "Đăng nhập thành công" : "Signed in") : locale === "vi" ? "Xác thực email" : "Email verification";
  const authSubtitle = signedIn
    ? locale === "vi"
      ? "Bạn đã có phiên đăng nhập. Có thể vào dashboard hoặc đăng xuất."
      : "You already have an active session. You can open the dashboard or sign out."
    : locale === "vi"
      ? "Đăng ký, xác thực email, rồi đăng nhập để mở dashboard cá nhân."
      : "Register, verify your email, then sign in to unlock your personal dashboard.";
  const authHelper = signedIn
    ? locale === "vi"
      ? `Bạn đang đăng nhập với ${authResult?.user.full_name}.`
      : `You are signed in as ${authResult?.user.full_name}.`
    : locale === "vi"
      ? "Đăng ký để nhận OTP qua email, xác thực tài khoản, rồi dùng cùng email và mật khẩu để đăng nhập."
      : "Register to receive an OTP by email, verify the account, then sign in with the same email and password.";

  const goToDashboard = () => {
    router.push("/dashboard");
  };

  const handleRegister = async () => {
    if (!authForm.fullName || !authForm.email || !authForm.password) {
      setAuthError(locale === "vi" ? "Vui lòng điền đầy đủ thông tin đăng ký." : "Please complete the registration form.");
      return;
    }

    try {
      setSubmittingRegister(true);
      setAuthError(null);
      const response = await apiRequest<VerificationResponse>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          full_name: authForm.fullName,
          email: authForm.email,
          password: authForm.password,
        }),
      });
      setVerificationInfo(response);
      setAuthInfo(
        locale === "vi"
          ? `Mã xác thực đã được gửi (${response.delivery_mode}). Vui lòng kiểm tra email. Hết hạn: ${new Date(response.expires_at).toLocaleString("vi-VN")}.`
          : `Verification code sent (${response.delivery_mode}). Please check your email. Expires: ${new Date(response.expires_at).toLocaleString("en-US")}.`,
      );
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Registration failed");
    } finally {
      setSubmittingRegister(false);
    }
  };

  const handleVerify = async () => {
    if (!authForm.email || !authForm.code) {
      setAuthError(locale === "vi" ? "Vui lòng nhập email và mã xác thực." : "Please enter email and verification code.");
      return;
    }

    try {
      setSubmittingVerify(true);
      setAuthError(null);
      const response = await apiRequest<AuthResponse>("/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ email: authForm.email, code: authForm.code }),
      });
      persistAuth(response);
      setAuthResult(response);
      setVerificationInfo(null);
      setAuthInfo(
        locale === "vi"
          ? `Xác thực thành công và đã đăng nhập cho ${response.user.full_name}.`
          : `Verification completed and signed in as ${response.user.full_name}.`,
      );
      goToDashboard();
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Verification failed");
    } finally {
      setSubmittingVerify(false);
    }
  };

  const handleLogin = async () => {
    if (!authForm.email || !authForm.password) {
      setAuthError(locale === "vi" ? "Vui lòng nhập email và mật khẩu để đăng nhập." : "Please enter email and password to sign in.");
      return;
    }

    try {
      setSubmittingLogin(true);
      setAuthError(null);
      const response = await apiRequest<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: authForm.email, password: authForm.password }),
      });
      persistAuth(response);
      setAuthResult(response);
      setAuthInfo(
        locale === "vi"
          ? `Đăng nhập thành công. Chào mừng ${response.user.full_name} quay lại dashboard.`
          : `Login successful. Welcome ${response.user.full_name} back to the dashboard.`,
      );
      goToDashboard();
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Login failed");
    } finally {
      setSubmittingLogin(false);
    }
  };

  const handleLogout = () => {
    clearPersistedAuth();
    setAuthResult(null);
    setVerificationInfo(null);
    setAuthError(null);
    setAuthInfo(locale === "vi" ? "Bạn đã đăng xuất khỏi dashboard." : "You have signed out of the dashboard.");
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(120,119,198,0.14),_transparent_30%),radial-gradient(circle_at_85%_15%,_rgba(34,211,238,0.08),_transparent_24%),linear-gradient(180deg,#0b1020_0%,#0f172a_34%,#f8fafc_34%,#f8fafc_100%)] text-white">
      <section className="relative mx-auto flex w-full max-w-7xl flex-col overflow-hidden px-4 pb-18 pt-6 sm:px-6 lg:px-8">
        <div className="pointer-events-none absolute inset-x-[-8%] top-[-10%] z-0 h-64 bg-[radial-gradient(circle,_rgba(124,58,237,0.16),_transparent_52%)] blur-3xl" />
        <div className="pointer-events-none absolute right-[-10%] top-28 z-0 h-72 w-72 rounded-full bg-[radial-gradient(circle,_rgba(34,211,238,0.12),_transparent_56%)] blur-3xl" />
        <ScrollReveal className="relative z-10 rounded-[28px] border border-white/10 bg-white/5 px-4 py-3 shadow-[0_24px_80px_rgba(2,6,23,0.28)] backdrop-blur sm:px-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-black">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-white/60">AI Research Workspace</p>
                <h1 className="text-lg font-semibold tracking-tight">{t.brand}</h1>
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <nav className="flex items-center gap-5 text-sm text-white/70">
                <a href="#features" className="transition hover:text-white">{t.navFeatures}</a>
                <a href={signedIn ? "/dashboard" : "#auth"} className="transition hover:text-white">{t.navDashboard}</a>
                <a href="#auth" className="transition hover:text-white">{signedIn ? (locale === "vi" ? "Tài khoản" : "Account") : t.navAuth}</a>
              </nav>
              <LanguageToggle locale={locale} onChange={setLocale} />
            </div>
          </div>
        </ScrollReveal>

        <div className="relative z-10 grid items-center gap-10 overflow-hidden py-12 lg:grid-cols-[1.12fr_0.88fr] lg:py-20">
          {!signedIn ? (
            <>
              <div className="pointer-events-none absolute inset-y-[-6%] right-[-16%] hidden w-[58%] lg:block">
                <div className="absolute inset-0 rounded-[72px] bg-[radial-gradient(circle_at_62%_44%,_rgba(124,58,237,0.22),_transparent_32%),radial-gradient(circle_at_55%_60%,_rgba(34,211,238,0.16),_transparent_28%),radial-gradient(circle_at_70%_35%,_rgba(244,114,182,0.08),_transparent_24%)] blur-3xl" />
                <div className="absolute inset-0 opacity-88">
                  <RubikCube />
                </div>
                <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(11,16,32,0.998)_0%,rgba(11,16,32,0.986)_14%,rgba(11,16,32,0.92)_28%,rgba(11,16,32,0.58)_48%,rgba(11,16,32,0.18)_68%,rgba(11,16,32,0.03)_84%,rgba(11,16,32,0)_100%)]" />
              </div>
              <div className="pointer-events-none absolute inset-y-0 left-0 z-[1] hidden w-[58%] bg-[radial-gradient(circle_at_left,_rgba(11,16,32,0.3),_transparent_68%)] lg:block" />
              <div className="pointer-events-none absolute inset-0 z-[1] hidden bg-[linear-gradient(180deg,rgba(255,255,255,0.02)_0%,rgba(11,16,32,0)_24%,rgba(11,16,32,0)_72%,rgba(11,16,32,0.08)_100%)] lg:block" />
              <div className="pointer-events-none absolute inset-y-0 right-0 z-[1] hidden w-[36%] bg-[radial-gradient(circle_at_right,_rgba(124,58,237,0.1),_transparent_60%),radial-gradient(circle_at_85%_55%,_rgba(34,211,238,0.07),_transparent_48%)] lg:block" />
            </>
          ) : null}

          <div className="absolute inset-y-0 left-0 z-[2] hidden w-[54%] bg-[linear-gradient(90deg,rgba(11,16,32,0.18)_0%,rgba(11,16,32,0.07)_60%,rgba(11,16,32,0)_100%)] lg:block" />

          <ScrollReveal className="relative z-10 space-y-8 lg:pr-6">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/6 px-4 py-2 text-sm text-white/72 shadow-[0_12px_40px_rgba(2,6,23,0.18)] backdrop-blur">
              <Languages className="h-4 w-4" />
              {t.heroBadge}
            </div>

            <div className="max-w-3xl space-y-5">
              <h2 className="text-4xl font-semibold leading-tight tracking-tight text-white sm:text-5xl lg:text-6xl">
                {t.heroTitle}
              </h2>
              <p className="max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
                {t.heroSubtitle}
              </p>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                onClick={() => {
                  if (signedIn) {
                    goToDashboard();
                    return;
                  }
                  document.getElementById("auth")?.scrollIntoView({ behavior: "smooth" });
                }}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-medium text-slate-950 shadow-[0_18px_50px_rgba(255,255,255,0.12)] transition hover:-translate-y-0.5 hover:bg-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/70"
              >
                {signedIn ? (locale === "vi" ? "Vào dashboard" : "Open dashboard") : t.heroCtaPrimary}
                <ArrowRight className="h-4 w-4" />
              </button>
              <a
                href="#workflow"
                className="inline-flex items-center justify-center rounded-full border border-white/15 bg-white/5 px-5 py-3 text-sm font-medium text-white/85 transition hover:-translate-y-0.5 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/50"
              >
                {t.heroCtaSecondary}
              </a>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {[t.heroStat1, t.heroStat2, t.heroStat3].map((item) => (
                <div
                  key={item}
                  className="rounded-2xl border border-white/10 bg-white/[0.055] px-4 py-4 text-sm text-white/75 shadow-[0_18px_40px_rgba(2,6,23,0.18)] backdrop-blur transition hover:-translate-y-1 hover:bg-white/[0.075]"
                >
                  {item}
                </div>
              ))}
            </div>
          </ScrollReveal>

          <ScrollReveal delay={0.15}>
            <div className="rounded-[32px] border border-white/10 bg-white/6 p-4 shadow-[0_32px_100px_rgba(2,6,23,0.34)] backdrop-blur sm:p-5">
              <div className="rounded-[28px] border border-white/10 bg-slate-950/58 p-6 sm:p-7">
                <div className="space-y-4">
                  <p className="text-sm text-white/50">{signedIn ? (locale === "vi" ? "Phiên đăng nhập đang hoạt động" : "Active session") : (locale === "vi" ? "Đăng nhập để bắt đầu" : "Sign in to begin")}</p>
                  <h3 className="text-2xl font-semibold text-white">
                    {signedIn
                      ? locale === "vi"
                        ? `Sẵn sàng vào dashboard của ${authResult?.user.full_name}`
                        : `Ready to open ${authResult?.user.full_name}'s dashboard`
                      : locale === "vi"
                        ? "Một dashboard riêng cho việc tóm tắt"
                        : "A dedicated dashboard for summarization"}
                  </h3>
                  <p className="text-sm leading-7 text-white/70">
                    {signedIn
                      ? locale === "vi"
                        ? "Từ đây bạn có thể đi thẳng tới màn hình dashboard riêng để xem lịch sử, nhập bài báo, tạo tóm tắt và chat với tài liệu."
                        : "From here you can jump straight into the dedicated dashboard screen for history, document input, summaries, and article chat."
                      : locale === "vi"
                        ? "Landing page giờ chỉ dành cho giới thiệu và đăng nhập. Sau khi xác thực hoặc đăng nhập thành công, bạn sẽ được chuyển sang một trang dashboard riêng biệt."
                        : "The landing page is now focused on product information and authentication. After successful verification or sign-in, you will be taken to a dedicated dashboard page."}
                  </p>
                  <div className="flex flex-col gap-3 sm:flex-row">
                    {signedIn ? (
                      <>
                        <button
                          onClick={goToDashboard}
                          className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-medium text-slate-950 shadow-[0_18px_50px_rgba(255,255,255,0.12)] transition hover:-translate-y-0.5 hover:bg-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/70"
                        >
                          <LogIn className="h-4 w-4" />
                          {locale === "vi" ? "Mở dashboard" : "Open dashboard"}
                        </button>
                        <button
                          onClick={handleLogout}
                          className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 bg-white/5 px-5 py-3 text-sm font-medium text-white transition hover:-translate-y-0.5 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/50"
                        >
                          <LogOut className="h-4 w-4" />
                          {locale === "vi" ? "Đăng xuất" : "Logout"}
                        </button>
                      </>
                    ) : (
                      <a
                        href="#auth"
                        className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-medium text-slate-950 shadow-[0_18px_50px_rgba(255,255,255,0.12)] transition hover:-translate-y-0.5 hover:bg-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/70"
                      >
                        {locale === "vi" ? "Đi tới đăng nhập" : "Go to sign in"}
                        <ArrowRight className="h-4 w-4" />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </ScrollReveal>
        </div>
      </section>

      <section id="features" className="bg-slate-50 text-slate-950">
        <div className="mx-auto max-w-7xl px-4 py-18 sm:px-6 lg:px-8 lg:py-24">
          <ScrollReveal className="max-w-3xl space-y-3">
            <p className="text-sm font-medium text-slate-500">Product direction</p>
            <h3 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t.featuresTitle}</h3>
            <p className="text-base leading-8 text-slate-600">{t.featuresSubtitle}</p>
          </ScrollReveal>

          <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {[
              [t.feature1Title, t.feature1Text],
              [t.feature2Title, t.feature2Text],
              [t.feature3Title, t.feature3Text],
              [t.feature4Title, t.feature4Text],
            ].map(([title, text], index) => (
              <ScrollReveal key={title} delay={index * 0.08}>
                <div className="h-full rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
                  <p className="text-lg font-semibold text-slate-950">{title}</p>
                  <p className="mt-3 text-sm leading-7 text-slate-600">{text}</p>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      <section id="auth" className="bg-slate-50 text-slate-950">
        <div className="mx-auto max-w-7xl px-4 pb-18 sm:px-6 lg:px-8 lg:pb-24">
          <ScrollReveal className="rounded-[32px] border border-slate-200/90 bg-white/95 p-6 shadow-[0_30px_80px_rgba(15,23,42,0.08)] sm:p-8">
            <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
              <div className="space-y-4">
                <p className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-sm font-medium text-slate-500">{authEyebrow}</p>
                <h3 className="text-3xl font-semibold tracking-tight">{t.authTitle}</h3>
                <p className="text-base leading-8 text-slate-600">{authSubtitle}</p>
                <p className="text-sm leading-7 text-slate-500">{authHelper}</p>
                <div className="grid gap-3 sm:grid-cols-3">
                  {[t.authCard1, t.authCard2, t.authCard3].map((item) => (
                    <div key={item} className="rounded-3xl border border-slate-200/90 bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] p-5 shadow-[0_12px_30px_rgba(15,23,42,0.05)] transition hover:-translate-y-1 hover:shadow-[0_20px_40px_rgba(15,23,42,0.08)]">
                      <MailCheck className="h-5 w-5 text-slate-500" />
                      <p className="mt-6 text-sm font-medium text-slate-900">{item}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-[28px] border border-slate-200/90 bg-[linear-gradient(180deg,#f8fafc_0%,#f1f5f9_100%)] p-5 shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
                <div className="grid gap-3 sm:grid-cols-2">
                  <input
                    value={authForm.fullName}
                    onChange={(event) => setAuthForm((current) => ({ ...current, fullName: event.target.value }))}
                    placeholder={locale === "vi" ? "Họ và tên" : "Full name"}
                    className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-400/60 focus:ring-4 focus:ring-sky-100"
                  />
                  <input
                    value={authForm.email}
                    onChange={(event) => setAuthForm((current) => ({ ...current, email: event.target.value }))}
                    placeholder="Email"
                    className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-400/60 focus:ring-4 focus:ring-sky-100"
                  />
                  <input
                    type="password"
                    value={authForm.password}
                    onChange={(event) => setAuthForm((current) => ({ ...current, password: event.target.value }))}
                    placeholder={locale === "vi" ? "Mật khẩu" : "Password"}
                    className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-400/60 focus:ring-4 focus:ring-sky-100"
                  />
                  <input
                    value={authForm.code}
                    onChange={(event) => setAuthForm((current) => ({ ...current, code: event.target.value }))}
                    placeholder={locale === "vi" ? "Mã xác thực" : "Verification code"}
                    className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-400/60 focus:ring-4 focus:ring-sky-100"
                  />
                </div>
                <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                  <button
                    onClick={handleRegister}
                    disabled={submittingRegister}
                    className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-950 px-4 py-3 text-sm font-medium text-white shadow-[0_16px_40px_rgba(15,23,42,0.14)] transition hover:-translate-y-0.5 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/60 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {submittingRegister ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                    {locale === "vi" ? "Đăng ký & gửi mã" : "Register & send code"}
                  </button>
                  <button
                    onClick={handleVerify}
                    disabled={submittingVerify}
                    className="inline-flex items-center justify-center gap-2 rounded-full border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-900 shadow-sm transition hover:-translate-y-0.5 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/60 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {submittingVerify ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                    {locale === "vi" ? "Xác thực email" : "Verify email"}
                  </button>
                  <button
                    onClick={signedIn ? goToDashboard : handleLogin}
                    disabled={submittingLogin}
                    className="inline-flex items-center justify-center gap-2 rounded-full border border-slate-950 bg-slate-950 px-4 py-3 text-sm font-medium text-white shadow-[0_16px_40px_rgba(15,23,42,0.14)] transition hover:-translate-y-0.5 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/60 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {submittingLogin ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                    {signedIn ? (locale === "vi" ? "Vào dashboard" : "Open dashboard") : locale === "vi" ? "Đăng nhập" : "Login"}
                  </button>
                </div>
                {verificationInfo && authInfo ? (
                  <p className="mt-4 rounded-2xl border border-emerald-200/90 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 shadow-sm">
                    {authInfo}
                  </p>
                ) : null}
                {authResult ? (
                  <p className="mt-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
                    {locale === "vi"
                      ? `Bạn đang đăng nhập với ${authResult.user.full_name}. Bấm vào dashboard để tiếp tục làm việc.`
                      : `You are signed in as ${authResult.user.full_name}. Open the dashboard to continue.`}
                  </p>
                ) : null}
                {authError ? (
                  <p className="mt-3 rounded-2xl border border-rose-200/90 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-sm">
                    {authError}
                  </p>
                ) : null}
                {!verificationInfo && !authResult && authInfo ? (
                  <p className="mt-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
                    {authInfo}
                  </p>
                ) : null}
              </div>
            </div>
          </ScrollReveal>
        </div>
      </section>

      <section id="workflow" className="bg-slate-950 text-white">
        <div className="mx-auto max-w-7xl px-4 py-18 sm:px-6 lg:px-8 lg:py-24">
          <ScrollReveal className="max-w-3xl space-y-3">
            <p className="text-sm font-medium text-white/45">Notebook to product</p>
            <h3 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t.workflowTitle}</h3>
            <p className="text-base leading-8 text-white/65">{t.workflowSubtitle}</p>
          </ScrollReveal>

          <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {[t.workflow1, t.workflow2, t.workflow3, t.workflow4].map((item, index) => (
              <ScrollReveal key={item} delay={index * 0.08}>
                <div className="rounded-[28px] border border-white/10 bg-white/5 p-6 backdrop-blur">
                  <p className="text-sm text-white/45">0{index + 1}</p>
                  <p className="mt-4 text-lg font-medium text-white">{item}</p>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-white/10 bg-slate-950 px-4 py-6 text-center text-sm text-white/40 sm:px-6 lg:px-8">
        {t.footer}
      </footer>
    </main>
  );
}

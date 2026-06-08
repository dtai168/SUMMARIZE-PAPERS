"use client";

import { DashboardWorkspace } from "@/components/dashboard-workspace";
import { AuthResponse } from "@/lib/api";
import { readPersistedAuth, readPersistedLocale } from "@/lib/auth";
import { dictionary, Locale } from "@/lib/content";
import { LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

function DashboardGate({ locale }: { locale: Locale }) {
  const t = dictionary[locale];

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(120,119,198,0.12),_transparent_35%),linear-gradient(180deg,#0b1020_0%,#0f172a_100%)] text-white">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl items-center justify-center px-4 py-10 sm:px-6 lg:px-8">
        <div className="w-full max-w-lg rounded-[32px] border border-white/10 bg-white/6 p-4 shadow-[0_32px_100px_rgba(2,6,23,0.34)] backdrop-blur sm:p-5">
          <div className="rounded-[28px] border border-white/10 bg-slate-950/58 p-8 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full border border-white/10 bg-white/5 text-white/80">
              <LoaderCircle className="h-6 w-6 animate-spin" />
            </div>
            <p className="mt-5 text-sm text-white/50">{locale === "vi" ? "Đang kiểm tra phiên đăng nhập" : "Checking your session"}</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">{locale === "vi" ? "Đang mở dashboard" : "Opening dashboard"}</h1>
            <p className="mt-3 text-sm leading-7 text-white/65">
              {locale === "vi"
                ? "Hệ thống đang khôi phục tài khoản và ngôn ngữ đã lưu trước khi tải không gian làm việc của bạn."
                : "The app is restoring your saved session and language before loading your workspace."}
            </p>
            <div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white/70">
              {t.dashboardTitle}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [locale, setLocale] = useState<Locale>("vi");
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [isHydratingAuth, setIsHydratingAuth] = useState(true);
  const gateLocale = useMemo(() => locale, [locale]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const persisted = readPersistedAuth();
      setLocale(readPersistedLocale() ?? "vi");

      if (!persisted?.access_token) {
        setIsHydratingAuth(false);
        router.replace("/#auth");
        return;
      }

      setAuth(persisted);
      setIsHydratingAuth(false);
    });

    return () => window.cancelAnimationFrame(frame);
  }, [router]);

  if (isHydratingAuth) {
    return <DashboardGate locale={gateLocale} />;
  }

  if (!auth) {
    return null;
  }

  return (
    <DashboardWorkspace
      locale={locale}
      auth={auth}
      onBackToLanding={() => {
        router.push("/");
      }}
      onLogout={() => {
        router.replace("/");
      }}
    />
  );
}

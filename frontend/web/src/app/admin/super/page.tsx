"use client";

import {
  AuthResponse,
  fetchSuperAdminInsights,
  fetchSuperAdminKpis,
  fetchSuperAdminMe,
  fetchSuperAdminRecent,
  fetchSuperAdminSeries,
} from "@/lib/api";
import { readPersistedAuth, readPersistedLocale } from "@/lib/auth";
import { Locale } from "@/lib/content";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-white/10 bg-white/[0.04] p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-white/50">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export default function SuperAdminPage() {
  const router = useRouter();
  const [locale, setLocale] = useState<Locale>("vi");
  const [auth, setAuth] = useState<AuthResponse | null>(null);
  const [kpis, setKpis] = useState<Awaited<ReturnType<typeof fetchSuperAdminKpis>> | null>(null);
  const [series, setSeries] = useState<Awaited<ReturnType<typeof fetchSuperAdminSeries>> | null>(null);
  const [recent, setRecent] = useState<Awaited<ReturnType<typeof fetchSuperAdminRecent>> | null>(null);
  const [insights, setInsights] = useState<Awaited<ReturnType<typeof fetchSuperAdminInsights>> | null>(null);

  useEffect(() => {
    const persisted = readPersistedAuth();
    setLocale(readPersistedLocale() ?? "vi");
    if (!persisted?.access_token) {
      router.replace("/#auth");
      return;
    }
    setAuth(persisted);
  }, [router]);

  useEffect(() => {
    if (!auth?.access_token) return;
    const token = auth.access_token;

    let cancelled = false;
    async function load() {
      try {
        await fetchSuperAdminMe(token);
        const [nextKpis, nextSeries, nextRecent, nextInsights] = await Promise.all([
          fetchSuperAdminKpis(token),
          fetchSuperAdminSeries(token, 30),
          fetchSuperAdminRecent(token, 20),
          fetchSuperAdminInsights(token, 30),
        ]);
        if (cancelled) return;
        setKpis(nextKpis);
        setSeries(nextSeries);
        setRecent(nextRecent);
        setInsights(nextInsights);
      } catch {
        if (!cancelled) router.replace("/admin");
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [auth?.access_token, router]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(120,119,198,0.12),_transparent_35%),linear-gradient(180deg,#0b1020_0%,#0f172a_100%)] text-white">
      <section className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        <header className="flex items-end justify-between">
          <div>
            <p className="text-sm text-white/55">{locale === "vi" ? "Tầng 2" : "Tier 2"}</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Super Admin BI</h1>
          </div>
          <div className="flex gap-2">
            <Link href="/admin" className="rounded-2xl border border-white/12 bg-white/[0.06] px-4 py-2.5 text-sm font-medium text-white/90">
              {locale === "vi" ? "Về Admin" : "Back to Admin"}
            </Link>
            <button type="button" onClick={() => router.push("/dashboard")} className="rounded-2xl border border-white/12 bg-white/[0.06] px-4 py-2.5 text-sm font-medium text-white/90">
              {locale === "vi" ? "Về Dashboard" : "Back to Dashboard"}
            </button>
          </div>
        </header>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Users" value={kpis ? String(kpis.users.total) : "—"} />
          <MetricCard label="Documents" value={kpis ? String(kpis.documents.total) : "—"} />
          <MetricCard label="Summaries" value={kpis ? String(kpis.summaries.total) : "—"} />
          <MetricCard label="Avg rating" value={kpis ? String(kpis.summaries.average_rating) : "—"} />
        </div>

        <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6">
            <p className="text-sm font-semibold text-white">{locale === "vi" ? "Top users theo documents" : "Top users by documents"}</p>
            <div className="mt-4 space-y-2">
              {(insights?.top_users_by_documents ?? []).map((item, idx) => (
                <div key={`${item.user_id}-${idx}`} className="rounded-xl border border-white/10 px-3 py-2 text-sm text-white/90">
                  {item.user_id ?? "unknown user"} · {item.count}
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6">
            <p className="text-sm font-semibold text-white">{locale === "vi" ? "Low-rated summaries" : "Low-rated summaries"}</p>
            <div className="mt-4 space-y-2">
              {(insights?.low_rated_summaries ?? []).map((item) => (
                <div key={item.id} className="rounded-xl border border-white/10 px-3 py-2 text-sm text-white/90">
                  {item.method} · ★ {item.rating_average ?? 0} · {new Date(item.created_at).toLocaleString()}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6">
            <p className="text-sm font-semibold text-white">{locale === "vi" ? "Anomalies" : "Anomalies"}</p>
            <p className="mt-3 text-sm text-white/80">orphan_summaries: {insights?.anomalies.orphan_summaries ?? 0}</p>
            <p className="mt-2 text-xs text-white/50">{locale === "vi" ? "Phát hiện cơ bản từ dữ liệu hiện có." : "Basic anomaly checks from current data."}</p>
          </div>

          <div className="rounded-[28px] border border-white/10 bg-slate-950/40 p-6">
            <p className="text-sm font-semibold text-white">{locale === "vi" ? "Recent tổng hợp" : "Merged recent activity"}</p>
            <div className="mt-4 space-y-2">
              {(recent?.summaries ?? []).slice(0, 6).map((s) => (
                <div key={s.id} className="rounded-xl border border-white/10 px-3 py-2 text-sm text-white/90">
                  summary · {s.method} · {new Date(s.created_at).toLocaleString()}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-8 rounded-[28px] border border-white/10 bg-slate-950/40 p-6">
          <p className="text-sm font-semibold text-white">{locale === "vi" ? "Quick trend" : "Quick trend"}</p>
          <p className="mt-2 text-xs text-white/50">users points: {series?.users.length ?? 0} · docs points: {series?.documents.length ?? 0} · summaries points: {series?.summaries.length ?? 0}</p>
        </div>
      </section>
    </main>
  );
}

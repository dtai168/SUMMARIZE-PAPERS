"use client";

import { Locale } from "@/lib/content";

export function LanguageToggle({
  locale,
  onChange,
}: {
  locale: Locale;
  onChange: (locale: Locale) => void;
}) {
  return (
    <div className="inline-flex rounded-full border border-white/10 bg-white/5 p-1 text-sm shadow-[0_12px_40px_rgba(2,6,23,0.18)] backdrop-blur">
      {(["vi", "en"] as const).map((value) => {
        const active = locale === value;

        return (
          <button
            key={value}
            type="button"
            onClick={() => onChange(value)}
            aria-pressed={active}
            className={`rounded-full px-3 py-1.5 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300/60 ${
              active
                ? "bg-white text-black shadow-sm"
                : "text-white/72 hover:-translate-y-0.5 hover:bg-white/8 hover:text-white"
            }`}
          >
            {value.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}

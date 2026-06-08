import { AuthResponse } from "@/lib/api";
import { Locale } from "@/lib/content";

const AUTH_STORAGE_KEY = "summarize-ai-auth";
const LOCALE_STORAGE_KEY = "summarize-ai-locale";

type StoredAuth = Pick<AuthResponse, "access_token" | "token_type" | "user">;

function isStoredAuth(value: unknown): value is StoredAuth {
  if (!value || typeof value !== "object") {
    return false;
  }

  const auth = value as Partial<StoredAuth>;
  return typeof auth.access_token === "string" && typeof auth.token_type === "string" && !!auth.user;
}

export function persistAuth(auth: AuthResponse) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
}

export function clearPersistedAuth() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function readPersistedAuth(): AuthResponse | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    return isStoredAuth(parsed) ? (parsed as AuthResponse) : null;
  } catch {
    return null;
  }
}

export function persistLocale(locale: Locale) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
}

export function readPersistedLocale(): Locale | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return raw === "vi" || raw === "en" ? raw : null;
}

export function isAuthenticated(auth: AuthResponse | null) {
  return Boolean(auth?.access_token);
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8002/api";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = payload?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail
          ? JSON.stringify(detail)
          : "Request failed";
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  return parseResponse<T>(response);
}

export async function apiAuthedRequest<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  return apiRequest<T>(path, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
}

export async function apiFormRequest<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });

  return parseResponse<T>(response);
}

export async function apiAuthedFormRequest<T>(path: string, token: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });

  return parseResponse<T>(response);
}

export type DocumentResponse = {
  id: string;
  title: string;
  source_type: "text" | "pdf";
  language: "vi" | "en";
  created_at: string;
  extraction_method?: string | null;
  reused_existing?: boolean;
};

export type UploadDocumentResponse = {
  id: string;
  title: string;
  source_type: "pdf";
  language: "vi" | "en";
  created_at: string;
  extraction_method?: string | null;
  reused_existing?: boolean;
};

export type SummaryRatingValue = 1 | 2 | 3 | 4 | 5;

export type SummaryResponse = {
  summary_id: string;
  document_id: string;
  source: string;
  language: "vi" | "en";
  summary: string;
  extractive_summary?: string | null;
  word_count: number;
  method: string;
  rating_average: number;
  rating_count: number;
  current_user_rating?: number | null;
  created_at: string;
};

export type SummaryRateRequest = {
  rating: SummaryRatingValue;
};

export type SummaryRatingResponse = {
  summary: SummaryResponse;
  message: string;
  preferred_for_document: boolean;
};

export type SummaryHistoryItem = {
  id: string;
  title: string;
  source_type: "text" | "pdf";
  created_at: string;
  status: "ready" | "processing";
  has_summary: boolean;
  extraction_method?: string | null;
  summary_created_at?: string | null;
  summary_id?: string | null;
  rating_average: number;
  rating_count: number;
  current_user_rating?: number | null;
};

export type SummaryDetailResponse = {
  document: DocumentResponse;
  summary: SummaryResponse | null;
  latest_summary: SummaryResponse | null;
  preferred_summary: SummaryResponse | null;
  available_summaries: SummaryResponse[];
};

export type ChatResponse = {
  answer: string;
  method: string;
  source: string;
  created_at: string;
};

export type ChatMessage = {
  id: string;
  document_id: string;
  question: string;
  answer: string;
  method: string;
  source: string;
  created_at: string;
};

export type ChatHistoryResponse = {
  items: ChatMessage[];
  document_id: string;
  limit: number;
  total_returned: number;
};

export async function fetchChatHistory(token: string, documentId: string, limit = 50): Promise<ChatHistoryResponse> {
  return apiAuthedRequest<ChatHistoryResponse>(`/chat/history?document_id=${encodeURIComponent(documentId)}&limit=${limit}`, token);
}

export type VerificationResponse = {
  message: string;
  delivery_mode: string;
  expires_at: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    full_name: string;
    is_verified: boolean;
    created_at: string;
  };
};

export type NamedCount = { name: string; count: number };

export type AdminKpisResponse = {
  users: {
    total: number;
    verified: number;
    verification_rate: number;
  };
  documents: {
    total: number;
    pdf: number;
    text: number;
    pdf_ratio: number;
    extraction_methods: NamedCount[];
  };
  summaries: {
    total: number;
    today: number;
    last_7d: number;
    rated: number;
    rated_ratio: number;
    average_rating: number;
    methods: NamedCount[];
  };
};

export type AdminSeriesPoint = {
  date: string;
  count: number;
};

export type AdminRatingSeriesPoint = {
  date: string;
  average_rating: number;
};

export type AdminSeriesResponse = {
  users: AdminSeriesPoint[];
  verified_users: AdminSeriesPoint[];
  documents: AdminSeriesPoint[];
  summaries: AdminSeriesPoint[];
  average_rating: AdminRatingSeriesPoint[];
  document_sources: NamedCount[];
};

export type SuperAdminInsightsResponse = {
  top_users_by_documents: { user_id: string | null; count: number }[];
  low_rated_summaries: {
    id: string;
    document_id: string | null;
    method: string;
    rating_average?: number | null;
    rating_count?: number | null;
    created_at: string;
  }[];
  anomalies: {
    orphan_summaries: number;
  };
};

export type SuperAdminUserDetailResponse = {
  user: {
    id: string;
    email: string;
    full_name: string | null;
    is_verified: boolean;
    created_at: string;
  };
  stats: {
    total_documents: number;
    total_summaries: number;
  };
};

export type AdminMeResponse = { ok: true; role: "admin" | "super_admin" };

export type AdminRecentUser = {
  id: string;
  email: string;
  full_name: string | null;
  is_verified: boolean;
  created_at: string;
};

export type AdminRecentDocument = {
  id: string;
  title: string;
  source_type: "text" | "pdf";
  original_filename?: string | null;
  extraction_method?: string | null;
  created_at: string;
};

export type AdminRecentSummary = {
  id: string;
  document_id: string | null;
  method: string;
  source: string;
  rating_average?: number | null;
  rating_count?: number | null;
  created_at: string;
};

export type AdminRecentResponse = {
  users: AdminRecentUser[];
  documents: AdminRecentDocument[];
  summaries: AdminRecentSummary[];
};

export async function fetchAdminKpis(token: string): Promise<AdminKpisResponse> {
  return apiAuthedRequest<AdminKpisResponse>("/admin/kpis", token);
}

export async function fetchAdminSeries(token: string, days = 30): Promise<AdminSeriesResponse> {
  return apiAuthedRequest<AdminSeriesResponse>(`/admin/series?days=${days}`, token);
}

export async function fetchAdminRecent(token: string, limit = 10): Promise<AdminRecentResponse> {
  return apiAuthedRequest<AdminRecentResponse>(`/admin/recent?limit=${limit}`, token);
}

export async function fetchAdminMe(token: string): Promise<AdminMeResponse> {
  return apiAuthedRequest<AdminMeResponse>("/admin/me", token);
}

export async function fetchSuperAdminMe(token: string): Promise<AdminMeResponse> {
  return apiAuthedRequest<AdminMeResponse>("/admin/super/me", token);
}

export async function fetchSuperAdminKpis(token: string): Promise<AdminKpisResponse> {
  return apiAuthedRequest<AdminKpisResponse>("/admin/super/kpis", token);
}

export async function fetchSuperAdminSeries(token: string, days = 30): Promise<AdminSeriesResponse> {
  return apiAuthedRequest<AdminSeriesResponse>(`/admin/super/series?days=${days}`, token);
}

export async function fetchSuperAdminRecent(token: string, limit = 20): Promise<AdminRecentResponse> {
  return apiAuthedRequest<AdminRecentResponse>(`/admin/super/recent?limit=${limit}`, token);
}

export async function fetchSuperAdminInsights(token: string, days = 30): Promise<SuperAdminInsightsResponse> {
  return apiAuthedRequest<SuperAdminInsightsResponse>(`/admin/super/insights?days=${days}`, token);
}

export async function fetchSuperAdminUserDetail(token: string, userId: string): Promise<SuperAdminUserDetailResponse> {
  return apiAuthedRequest<SuperAdminUserDetailResponse>(`/admin/super/users/${encodeURIComponent(userId)}`, token);
}

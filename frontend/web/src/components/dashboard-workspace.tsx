"use client";

import {
  apiAuthedRequest,
  apiAuthedFormRequest,
  apiFormRequest,
  apiRequest,
  AuthResponse,
  ChatHistoryResponse,
  ChatMessage,
  ChatResponse,
  fetchChatHistory,
  DocumentResponse,
  SummaryDetailResponse,
  SummaryHistoryItem,
  SummaryRatingResponse,
  SummaryRatingValue,
  SummaryResponse,
  UploadDocumentResponse,
} from "@/lib/api";
import { clearPersistedAuth } from "@/lib/auth";
import { Locale, dictionary } from "@/lib/content";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Bot, FileText, History, LoaderCircle, LogOut, RotateCcw, Sparkles, Star, Upload } from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";

type DashboardWorkspaceProps = {
  locale: Locale;
  auth: AuthResponse;
  onBackToLanding: () => void;
  onLogout: () => void;
};

export function DashboardWorkspace({ locale, auth, onBackToLanding, onLogout }: DashboardWorkspaceProps) {
  const [articleText, setArticleText] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeDocument, setActiveDocument] = useState<DocumentResponse | UploadDocumentResponse | null>(null);
  const [summary, setSummary] = useState("");
  const [summaryMeta, setSummaryMeta] = useState<SummaryResponse | null>(null);
  const [showExtractiveSummary, setShowExtractiveSummary] = useState(false);
  const [availableSummaries, setAvailableSummaries] = useState<SummaryResponse[]>([]);
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [showChatHistory, setShowChatHistory] = useState(false);
  const [chatMeta, setChatMeta] = useState<ChatResponse | null>(null);
  const [currentChatTurn, setCurrentChatTurn] = useState<{ question: string; answer: string; method: string; source: string } | null>(null);
  const [historyItems, setHistoryItems] = useState<SummaryHistoryItem[]>([]);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [ratingError, setRatingError] = useState<string | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingHistoryDetail, setLoadingHistoryDetail] = useState(false);
  const [submittingSummary, setSubmittingSummary] = useState(false);
  const [submittingChat, setSubmittingChat] = useState(false);
  const [creatingDocument, setCreatingDocument] = useState(false);
  const [submittingRating, setSubmittingRating] = useState(false);
  const [reusedMessage, setReusedMessage] = useState<string | null>(null);

  const t = useMemo(() => dictionary[locale], [locale]);
  const loadingLabel = locale === "vi" ? "Đang xử lý..." : "Processing...";
  const submitLabel = locale === "vi" ? "Gửi" : "Send";

  const [summaryTargetWords, setSummaryTargetWords] = useState(500);
  const summaryTargetLabel = locale === "vi" ? "Số từ mục tiêu" : "Target words";
  const summaryTargetHint = locale === "vi" ? "Điều chỉnh độ dài bản tóm tắt." : "Adjust the summary length.";
  const summaryTargetMin = 150;
  const summaryTargetMax = 2000;
  const summaryTargetStep = 50;
  const summaryTargetId = "summary-target-words";
  const summaryTargetValueLabel = `${summaryTargetWords} ${locale === "vi" ? "từ" : "words"}`;
  const summaryTargetNormalized = (summaryTargetWords - summaryTargetMin) / (summaryTargetMax - summaryTargetMin);
  const summaryTargetRail = `linear-gradient(90deg, rgba(56,189,248,0.65) 0%, rgba(56,189,248,0.65) ${Math.max(0, Math.min(100, summaryTargetNormalized * 100))}%, rgba(255,255,255,0.12) ${Math.max(0, Math.min(100, summaryTargetNormalized * 100))}%, rgba(255,255,255,0.12) 100%)`;

  const formatRatingAverage = (value: number | null | undefined) => (typeof value === "number" ? value : 0).toFixed(1);
  const getRatingCount = (value: number | null | undefined) => (typeof value === "number" ? value : 0);


  const loadHistory = useCallback(async () => {
    try {
      setLoadingHistory(true);
      const items = await apiAuthedRequest<SummaryHistoryItem[]>("/summary/history", auth.access_token);
      setHistoryItems(items);
      setHistoryError(null);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "Failed to load history");
    } finally {
      setLoadingHistory(false);
    }
  }, [auth.access_token]);

  useEffect(() => {
    Promise.resolve().then(loadHistory);
  }, [loadHistory]);

  const resetWorkspace = () => {
    setSummary("");
    setSummaryMeta(null);
    setAvailableSummaries([]);
    setChatMessages([]);
    setChatMeta(null);
    setCurrentChatTurn(null);
    setSummaryError(null);
    setChatError(null);
    setRatingError(null);
    setReusedMessage(null);
  };

  const applySummarySelection = (nextSummary: SummaryResponse | null, allSummaries: SummaryResponse[] = []) => {
    setSummary(nextSummary?.summary ?? "");
    setSummaryMeta(nextSummary);
    setAvailableSummaries(allSummaries);
    setShowExtractiveSummary(false);
    setRatingError(null);
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setActiveDocument(null);
    resetWorkspace();
  };

  const createDocumentFromText = async () => {
    const title = articleText.trim().split("\n")[0]?.slice(0, 80) || (locale === "vi" ? "Văn bản đã dán" : "Pasted text");
    return apiRequest<DocumentResponse>("/summary/text", {
      method: "POST",
      body: JSON.stringify({ text: articleText, language: locale, title }),
    });
  };

  const createDocumentFromPdf = async () => {
    if (!selectedFile) {
      throw new Error(locale === "vi" ? "Vui lòng chọn file PDF trước." : "Please choose a PDF first.");
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("language", locale);
    return apiAuthedFormRequest<UploadDocumentResponse>("/summary/upload", auth.access_token, formData);
  };

  const ensureActiveDocument = async () => {
    if (!articleText.trim() && !selectedFile && !activeDocument) {
      throw new Error(
        locale === "vi"
          ? "Vui lòng dán nội dung bài báo hoặc chọn file PDF trước."
          : "Please paste article text or choose a PDF first.",
      );
    }

    if (activeDocument) {
      return activeDocument;
    }

    setCreatingDocument(true);
    try {
      const document = selectedFile ? await createDocumentFromPdf() : await createDocumentFromText();
      setActiveDocument(document);
      if (document.reused_existing) {
        setReusedMessage(
          locale === "vi"
            ? "Tài liệu này đã từng được lưu trước đó. Hệ thống sẽ ưu tiên dùng lại bản tóm tắt được đánh giá tốt nhất."
            : "This document was already saved before. The workspace will prefer the highest-rated summary.",
        );
      } else {
        setReusedMessage(null);
      }
      await loadHistory();
      return document;
    } finally {
      setCreatingDocument(false);
    }
  };

  const handleGenerateSummary = async (forceRegenerate = false) => {
    try {
      setSubmittingSummary(true);
      setSummaryError(null);
      const document = await ensureActiveDocument();
      const response = await apiAuthedRequest<SummaryResponse>(`/summary/${document.id}/generate`, auth.access_token, {
        method: "POST",
        body: JSON.stringify({ language: locale, force_regenerate: forceRegenerate, target_words: summaryTargetWords }),
      });
      applySummarySelection(response, response ? [response, ...availableSummaries.filter((item) => item.summary_id !== response.summary_id)] : []);
      await loadHistory();
    } catch (error) {
      setSummaryError(error instanceof Error ? error.message : "Summary request failed");
    } finally {
      setSubmittingSummary(false);
    }
  };

  const handleLoadHistoryItem = async (documentId: string) => {
    try {
      setLoadingHistoryDetail(true);
      setHistoryError(null);
      const detail = await apiAuthedRequest<SummaryDetailResponse>(`/summary/${documentId}`, auth.access_token);
      setActiveDocument(detail.document);
      setSelectedFile(null);
      setArticleText("");
      applySummarySelection(detail.summary, detail.available_summaries);
      try {
        const history = await fetchChatHistory(auth.access_token, documentId);
        setChatMessages(history.items);
      } catch {
        setChatMessages([]);
      }
      setChatMeta(null);
      setSummaryError(null);
      setChatError(null);
      setReusedMessage(
        locale === "vi"
          ? "Bạn đang xem lại tài liệu đã lưu trong lịch sử. Hệ thống đang ưu tiên bản tóm tắt có đánh giá tốt nhất."
          : "You are viewing a document restored from history. The workspace is prioritizing the highest-rated summary.",
      );
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : "Failed to load summary detail");
    } finally {
      setLoadingHistoryDetail(false);
    }
  };

  const handleAskQuestion = async () => {
    if (!chatQuestion.trim()) {
      setChatError(locale === "vi" ? "Vui lòng nhập câu hỏi trước." : "Please enter a question first.");
      return;
    }

    try {
      setSubmittingChat(true);
      setChatError(null);
      const document = await ensureActiveDocument();
      const question = chatQuestion.trim();
      const response = await apiAuthedRequest<ChatResponse>("/chat", auth.access_token, {
        method: "POST",
        body: JSON.stringify({
          document_id: document.id,
          question,
          locale,
        }),
      });
      setChatMeta(response);
      setCurrentChatTurn({
        question,
        answer: response.answer,
        method: response.method,
        source: response.source,
      });
      setChatQuestion("");
      const history = await fetchChatHistory(auth.access_token, document.id);
      setChatMessages(history.items);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : "Chat request failed");
    } finally {
      setSubmittingChat(false);
    }
  };

  const handleRateSummary = async (rating: SummaryRatingValue) => {
    if (!activeDocument || !summaryMeta?.summary_id) {
      setRatingError(locale === "vi" ? "Bản tóm tắt hiện tại chưa có mã đánh giá hợp lệ. Vui lòng tải lại lịch sử hoặc tạo lại bản tóm tắt." : "The current summary does not have a valid rating ID yet. Please reload history or regenerate the summary.");
      return;
    }

    try {
      setSubmittingRating(true);
      setRatingError(null);
      const response = await apiAuthedRequest<SummaryRatingResponse>(
        `/summary/${activeDocument.id}/summaries/${summaryMeta.summary_id}/rate`,
        auth.access_token,
        {
          method: "POST",
          body: JSON.stringify({ rating }),
        },
      );
      const updatedSummary = response.summary;
      const nextSummaries = availableSummaries.length
        ? availableSummaries
            .map((item) => (item.summary_id === updatedSummary.summary_id ? updatedSummary : item))
            .sort((a, b) => {
              if (b.rating_average !== a.rating_average) return b.rating_average - a.rating_average;
              if (b.rating_count !== a.rating_count) return b.rating_count - a.rating_count;
              return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
            })
        : [updatedSummary];
      applySummarySelection(updatedSummary, nextSummaries);
      await loadHistory();
    } catch (error) {
      setRatingError(error instanceof Error ? error.message : "Rating request failed");
    } finally {
      setSubmittingRating(false);
    }
  };

  const handleLogout = () => {
    clearPersistedAuth();
    onLogout();
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(120,119,198,0.12),_transparent_35%),linear-gradient(180deg,#0b1020_0%,#0f172a_100%)] text-white">
      <section className="mx-auto flex w-full max-w-7xl flex-col px-4 pb-18 pt-6 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: "easeOut" }}
          className="rounded-[28px] border border-white/10 bg-white/5 px-4 py-3 backdrop-blur sm:px-6"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-white/60">{locale === "vi" ? "Không gian làm việc cá nhân" : "Personal workspace"}</p>
              <h1 className="text-3xl font-semibold tracking-tight text-white">{locale === "vi" ? `Dashboard của ${auth.user.full_name}` : `${auth.user.full_name}'s dashboard`}</h1>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">
                {locale === "vi" ? `Đã đăng nhập với ${auth.user.email}` : `Signed in as ${auth.user.email}`}
              </div>
              <button
                onClick={onBackToLanding}
                className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:-translate-y-0.5 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60"
              >
                <ArrowLeft className="h-4 w-4" />
                {locale === "vi" ? "Về landing" : "Back to landing"}
              </button>
              <button
                onClick={handleLogout}
                className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:-translate-y-0.5 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60"
              >
                <LogOut className="h-4 w-4" />
                {locale === "vi" ? "Đăng xuất" : "Logout"}
              </button>
            </div>
          </div>
        </motion.div>

        <div className="pt-8">
          <div className="rounded-[32px] border border-white/10 bg-white/5 p-4 shadow-2xl shadow-slate-950/40 backdrop-blur sm:p-5">
            <div className="rounded-[28px] border border-white/10 bg-slate-950/60 p-4 sm:p-5">
              <div className="mb-5 flex items-center justify-between border-b border-white/10 pb-4">
                <div>
                  <p className="text-sm text-white/50">{locale === "vi" ? "Không gian tóm tắt" : "Summarization workspace"}</p>
                  <h2 className="text-xl font-semibold text-white">{locale === "vi" ? "Dashboard tóm tắt" : "Summary dashboard"}</h2>
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[0.82fr_1.18fr]">
                <div className="space-y-4">
                  <Panel title={t.historyTitle} icon={<History className="h-4 w-4" />} collapsible defaultCollapsed>
                    <div className="space-y-3">
                      {loadingHistory ? (
                        <SkeletonList rows={4} />
                      ) : historyError ? (
                        <ErrorCard message={historyError} />
                      ) : historyItems.length ? (
                        historyItems.map((item, index) => (
                          <motion.button
                            key={item.id}
                            type="button"
                            onClick={() => handleLoadHistoryItem(item.id)}
                            disabled={loadingHistoryDetail}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.28, delay: index * 0.04 }}
                            whileHover={{ y: -2 }}
                            whileTap={{ scale: 0.99 }}
                            className="w-full rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-left transition hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 disabled:cursor-not-allowed disabled:opacity-70"
                          >
                            <p className="text-sm font-medium text-white">{item.title}</p>
                            <p className="mt-1 text-xs text-white/45">
                              {item.source_type.toUpperCase()} · {item.status.toUpperCase()} · {new Date(item.created_at).toLocaleDateString(locale === "vi" ? "vi-VN" : "en-US")}
                            </p>
                            {item.has_summary ? (
                              <p className="mt-1 text-xs text-amber-300/90">
                                {locale === "vi" ? "Điểm trung bình" : "Average rating"}: {formatRatingAverage(item.rating_average)} · {getRatingCount(item.rating_count)} {locale === "vi" ? "lượt" : "ratings"}
                              </p>
                            ) : null}
                            {item.extraction_method ? <p className="mt-1 text-xs text-white/35">{item.extraction_method}</p> : null}
                          </motion.button>
                        ))
                      ) : (
                        <EmptyState
                          icon={<History className="h-5 w-5" />}
                          title={locale === "vi" ? "Chưa có lịch sử" : "No history yet"}
                          description={locale === "vi" ? "Hãy tạo bản tóm tắt đầu tiên để lưu tài liệu và điểm đánh giá tại đây." : "Create your first summary to keep saved documents and ratings here."}
                        />
                      )}
                    </div>
                  </Panel>

                  <Panel title={t.inputTitle} icon={<Upload className="h-4 w-4" />}>
                    <div className="space-y-3">
                      <textarea
                        value={articleText}
                        onChange={(event) => {
                          setArticleText(event.target.value);
                          if (event.target.value.trim()) {
                            setSelectedFile(null);
                          }
                          setActiveDocument(null);
                          resetWorkspace();
                        }}
                        placeholder={t.inputPlaceholder}
                        className="min-h-36 w-full rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white outline-none placeholder:text-white/35 focus:border-sky-400/40 focus:ring-2 focus:ring-sky-400/20"
                      />
                      <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <label htmlFor={summaryTargetId} className="text-sm font-medium text-white/80">
                            {summaryTargetLabel}
                          </label>
                          <span className="text-sm font-semibold text-white/90 tabular-nums">{summaryTargetValueLabel}</span>
                        </div>
                        <p className="mt-1 text-xs text-white/45">{summaryTargetHint}</p>
                        <input
                          id={summaryTargetId}
                          type="range"
                          min={summaryTargetMin}
                          max={summaryTargetMax}
                          step={summaryTargetStep}
                          value={summaryTargetWords}
                          onChange={(event) => {
                            setSummaryTargetWords(Number(event.target.value));
                          }}
                          className="mt-3 h-2 w-full cursor-pointer appearance-none rounded-full bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/50"
                          style={{ background: summaryTargetRail }}
                        />
                      </div>
                      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                        <label className="inline-flex items-center justify-center rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80 transition hover:-translate-y-0.5 hover:bg-white/10 focus-within:ring-2 focus-within:ring-sky-400/40">
                          {selectedFile ? selectedFile.name : t.uploadLabel}
                          <input type="file" accept="application/pdf" className="hidden" onChange={handleFileChange} />
                        </label>
                        <button
                          onClick={() => handleGenerateSummary(false)}
                          disabled={submittingSummary || creatingDocument}
                          className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-medium text-slate-950 transition hover:-translate-y-0.5 hover:bg-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 disabled:cursor-not-allowed disabled:opacity-70"
                        >
                          {submittingSummary || creatingDocument ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                          {submittingSummary || creatingDocument ? loadingLabel : t.generateLabel}
                        </button>
                        <button
                          onClick={() => handleGenerateSummary(true)}
                          disabled={submittingSummary || creatingDocument || !activeDocument}
                          className="inline-flex items-center justify-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:-translate-y-0.5 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <RotateCcw className="h-4 w-4" />
                          {locale === "vi" ? "Tóm tắt lại" : "Regenerate"}
                        </button>
                      </div>
                      {activeDocument ? (
                        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200">
                          {locale === "vi" ? "Tài liệu hiện tại đã sẵn sàng để tóm tắt và chat." : "Current document is ready for summary and chat."}
                          <div className="mt-1 text-xs text-emerald-100/80">
                            {activeDocument.title} · {activeDocument.source_type.toUpperCase()} · {activeDocument.extraction_method ?? "saved"}
                          </div>
                        </motion.div>
                      ) : null}
                      {reusedMessage ? (
                        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl border border-sky-400/20 bg-sky-400/10 px-4 py-3 text-sm text-sky-200">{reusedMessage}</motion.div>
                      ) : null}
                      {summaryError ? <ErrorCard message={summaryError} /> : null}
                    </div>
                  </Panel>
                </div>

                <div className="grid gap-4">
                  <Panel title={t.outputTitle} icon={<FileText className="h-4 w-4" />}>
                    <AnimatePresence mode="wait" initial={false}>
                      {submittingSummary || creatingDocument || loadingHistoryDetail ? (
                        <motion.div
                          key="summary-loading"
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                        >
                          <SummarySkeleton />
                        </motion.div>
                      ) : summary ? (
                        <motion.div
                          key={summaryMeta?.summary_id ?? summary}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                          transition={{ duration: 0.26 }}
                          className="space-y-3"
                        >
                          {summaryMeta?.extractive_summary ? (
                            <div className="flex justify-end">
                              <button
                                type="button"
                                onClick={() => setShowExtractiveSummary((v) => !v)}
                                className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/50"
                              >
                                {showExtractiveSummary
                                  ? locale === "vi"
                                    ? "Xem bản Qwen"
                                    : "Show Qwen version"
                                  : locale === "vi"
                                    ? "Xem bản TextRank"
                                    : "Show TextRank version"}
                              </button>
                            </div>
                          ) : null}
                          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm leading-7 text-white/70">
                            {showExtractiveSummary && summaryMeta?.extractive_summary ? summaryMeta.extractive_summary : summary}
                          </div>
                        </motion.div>
                      ) : (
                        <motion.div
                          key="summary-empty"
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                        >
                          <EmptyState
                            icon={<Sparkles className="h-5 w-5" />}
                            title={locale === "vi" ? "Chưa có bản tóm tắt" : "No summary yet"}
                            description={locale === "vi" ? "Dán nội dung hoặc tải PDF lên để tạo bản tóm tắt đầu tiên." : "Paste text or upload a PDF to generate your first summary."}
                          />
                        </motion.div>
                      )}
                    </AnimatePresence>
                    {summaryMeta ? (
                      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-3 space-y-3">
                        <p className="text-xs text-white/45">
                          {summaryMeta.method} · {summaryMeta.source}
                        </p>
                        <p className="text-xs text-white/45">
                          {locale === "vi" ? "Số từ" : "Word count"}: {summaryMeta.word_count}/{summaryTargetWords} · {(() => {
                            const tol = 0.08;
                            const minOk = Math.max(120, Math.floor(summaryTargetWords * (1 - tol)));
                            const maxOk = Math.floor(summaryTargetWords * (1 + tol));
                            const ok = summaryMeta.word_count >= minOk && summaryMeta.word_count <= maxOk;
                            return ok ? (locale === "vi" ? "Trong ngưỡng" : "In range") : (locale === "vi" ? "Ngoài ngưỡng" : "Out of range");
                          })()}
                        </p>
                        <div className="rounded-2xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                            <div>
                              <p className="font-medium text-amber-200">{locale === "vi" ? "Đánh giá bản tóm tắt" : "Rate this summary"}</p>
                              <p className="mt-1 text-xs text-amber-100/80">
                                {locale === "vi" ? "Điểm trung bình" : "Average rating"}: {formatRatingAverage(summaryMeta.rating_average)} · {getRatingCount(summaryMeta.rating_count)} {locale === "vi" ? "lượt đánh giá" : "ratings"}
                              </p>
                            </div>
                            <div className="flex items-center gap-1">
                              {[1, 2, 3, 4, 5].map((value) => {
                                const active = value <= (summaryMeta.current_user_rating ?? 0);
                                return (
                                  <button
                                    key={value}
                                    type="button"
                                    onClick={() => handleRateSummary(value as SummaryRatingValue)}
                                    disabled={submittingRating}
                                    className="rounded-full p-1 text-amber-200 transition hover:scale-105 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-300/60 disabled:cursor-not-allowed disabled:opacity-60"
                                    aria-label={`${locale === "vi" ? "Đánh giá" : "Rate"} ${value}`}
                                  >
                                    <Star className={`h-5 w-5 ${active ? "fill-current" : ""}`} />
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                          {ratingError ? <p className="mt-2 text-xs text-rose-200">{ratingError}</p> : null}
                        </div>
                        {availableSummaries.length > 1 ? (
                          <div className="space-y-2">
                            <p className="text-xs font-medium text-white/55">{locale === "vi" ? "Các phiên bản tóm tắt đã lưu" : "Saved summary versions"}</p>
                            <div className="space-y-2">
                              {availableSummaries.map((item) => (
                                <button
                                  key={item.summary_id}
                                  type="button"
                                  onClick={() => applySummarySelection(item, availableSummaries)}
                                  className={`w-full rounded-2xl border px-3 py-3 text-left text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 ${summaryMeta.summary_id === item.summary_id ? "border-sky-400/40 bg-sky-400/10 text-white" : "border-white/10 bg-white/[0.03] text-white/70 hover:bg-white/[0.06]"}`}
                                >
                                  <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                                    <span>{new Date(item.created_at).toLocaleString(locale === "vi" ? "vi-VN" : "en-US")}</span>
                                    <span className="text-xs text-amber-300/90">{formatRatingAverage(item.rating_average)} · {getRatingCount(item.rating_count)}★</span>
                                  </div>
                                  <p className="mt-2 line-clamp-3 text-xs text-white/55">{item.summary}</p>
                                </button>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </motion.div>
                    ) : null}
                  </Panel>

                  <Panel title={t.chatTitle} icon={<Bot className="h-4 w-4" />}>
                    <div className="space-y-3">
                      <div className="flex items-center justify-end">
                        <button
                          type="button"
                          onClick={() => setShowChatHistory((value) => !value)}
                          className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/50"
                        >
                          {showChatHistory
                            ? locale === "vi"
                              ? "Ẩn lịch sử chat"
                              : "Hide chat history"
                            : locale === "vi"
                              ? "Hiện lịch sử chat"
                              : "Show chat history"}
                        </button>
                      </div>
                      <AnimatePresence mode="wait" initial={false}>
                        {submittingChat ? (
                          <motion.div
                            key="chat-loading"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                          >
                            <ChatSkeleton />
                          </motion.div>
                        ) : currentChatTurn || showChatHistory || chatMessages.length ? (
                          <motion.div
                            key={activeDocument?.id ?? "chat"}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                            className="space-y-3"
                          >
                            {currentChatTurn ? (
                              <div className="space-y-2 rounded-2xl border border-sky-300/20 bg-sky-300/5 p-3">
                                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-white/80">
                                  <p className="text-xs font-medium text-white/60">{locale === "vi" ? "Hỏi (hiện tại)" : "Question (current)"}</p>
                                  <p className="mt-1 whitespace-pre-wrap leading-6">{currentChatTurn.question}</p>
                                </div>
                                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-white/70">
                                  <p className="text-xs font-medium text-white/60">{locale === "vi" ? "Đáp (hiện tại)" : "Answer (current)"}</p>
                                  <p className="mt-1 whitespace-pre-wrap leading-6">{currentChatTurn.answer}</p>
                                </div>
                              </div>
                            ) : null}

                            {showChatHistory ? (
                              chatMessages.length ? (
                                chatMessages.map((item) => (
                                  <div key={item.id} className="space-y-2">
                                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-white/80">
                                      <p className="text-xs font-medium text-white/60">{locale === "vi" ? "Hỏi" : "Question"}</p>
                                      <p className="mt-1 whitespace-pre-wrap leading-6">{item.question}</p>
                                    </div>
                                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-white/70">
                                      <p className="text-xs font-medium text-white/60">{locale === "vi" ? "Đáp" : "Answer"}</p>
                                      <p className="mt-1 whitespace-pre-wrap leading-6">{item.answer}</p>
                                      <p className="mt-2 text-xs text-white/45">
                                        {item.method} · {item.source}
                                      </p>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <EmptyState
                                  icon={<History className="h-5 w-5" />}
                                  title={locale === "vi" ? "Chưa có lịch sử chat cũ" : "No prior chat history"}
                                  description={locale === "vi" ? "Lượt chat hiện tại vẫn hiển thị ở trên, chưa có lượt nào cũ hơn." : "Your current turn is shown above, and there are no older turns yet."}
                                />
                              )
                            ) : null}
                          </motion.div>
                        ) : (
                          <motion.div
                            key="chat-empty"
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -10 }}
                          >
                            <EmptyState
                              icon={<Bot className="h-5 w-5" />}
                              title={locale === "vi" ? "Chưa có cuộc hội thoại" : "No conversation yet"}
                              description={locale === "vi" ? "Đặt câu hỏi về tài liệu hiện tại để nhận câu trả lời theo ngữ cảnh." : "Ask about the current document to get context-aware answers."}
                            />
                          </motion.div>
                        )}
                      </AnimatePresence>
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <input
                          value={chatQuestion}
                          onChange={(event) => setChatQuestion(event.target.value)}
                          placeholder={t.chatPlaceholder}
                          className="flex-1 rounded-full border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white outline-none placeholder:text-white/35 focus:border-sky-400/40 focus:ring-2 focus:ring-sky-400/20"
                        />
                        <button
                          onClick={handleAskQuestion}
                          disabled={submittingChat || creatingDocument || loadingHistoryDetail}
                          className="inline-flex items-center justify-center gap-2 rounded-full bg-white px-4 py-3 text-sm font-medium text-slate-950 transition hover:-translate-y-0.5 hover:bg-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/60 disabled:cursor-not-allowed disabled:opacity-70"
                        >
                          {submittingChat || creatingDocument ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                          {submittingChat || creatingDocument ? loadingLabel : submitLabel}
                        </button>
                      </div>
                      {chatError ? <ErrorCard message={chatError} /> : null}
                    </div>
                  </Panel>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function Panel({
  title,
  icon,
  children,
  collapsible = false,
  defaultCollapsed = false,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  collapsible?: boolean;
  defaultCollapsed?: boolean;
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  return (
    <div className="rounded-[26px] border border-white/10 bg-white/[0.02] p-4">
      <div className="mb-4 flex items-center justify-between gap-3 text-sm font-medium text-white/75">
        <div className="flex items-center gap-2">
          <span className="text-white/45">{icon}</span>
          <span>{title}</span>
        </div>
        {collapsible ? (
          <button
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/50"
          >
            {collapsed ? "Mở" : "Ẩn"}
          </button>
        ) : null}
      </div>
      {collapsed ? null : children}
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
      {message}
    </div>
  );
}

function EmptyState({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-center">
      <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-white/65">
        {icon}
      </div>
      <p className="mt-3 text-sm font-medium text-white">{title}</p>
      <p className="mt-1 text-sm leading-6 text-white/50">{description}</p>
    </div>
  );
}

function SkeletonLine({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-full bg-white/8 ${className ?? "h-3 w-full"}`} />;
}

function SkeletonList({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
          <SkeletonLine className="h-4 w-2/3" />
          <SkeletonLine className="mt-3 h-3 w-5/6" />
          <SkeletonLine className="mt-2 h-3 w-1/2" />
        </div>
      ))}
    </div>
  );
}

function SummarySkeleton() {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <SkeletonLine className="h-4 w-11/12" />
      <SkeletonLine className="mt-3 h-4 w-full" />
      <SkeletonLine className="mt-3 h-4 w-10/12" />
      <SkeletonLine className="mt-3 h-4 w-9/12" />
      <SkeletonLine className="mt-3 h-4 w-7/12" />
    </div>
  );
}

function ChatSkeleton() {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <SkeletonLine className="h-4 w-3/4" />
      <SkeletonLine className="mt-3 h-4 w-full" />
      <SkeletonLine className="mt-3 h-4 w-8/12" />
    </div>
  );
}

/* duplicate helper block removed */

import axios from "axios";

const api = axios.create({ baseURL: "/api/v1" }); // Vite proxy handles routing

export default api;

// ── Chat ────────────────────────────────────────────────────────────────────
export const sendMessage = (question, session_id = null) =>
  api.post("/chat", { question, session_id }).then((r) => r.data);

// ── Sessions ─────────────────────────────────────────────────────────────────

/** Returns PaginatedResponse<SessionOut> */
export const getSessions = (page = 1, pageSize = 20, search = null) => {
  const params = new URLSearchParams({ page, page_size: pageSize });
  if (search) params.set("search", search);
  return api.get(`/sessions?${params}`).then((r) => r.data);
};

export const getSession = (id) => api.get(`/sessions/${id}`).then((r) => r.data);
export const deleteSession = (id) => api.delete(`/sessions/${id}`);
export const renameSession = (id, title) =>
  api.patch(`/sessions/${id}`, { title }).then((r) => r.data);

// ── Feedback ──────────────────────────────────────────────────────────────────
export const submitFeedback = (message_id, rating, comment = null) =>
  api.post(`/messages/${message_id}/feedback`, { rating, comment }).then((r) => r.data);

// ── Metrics ───────────────────────────────────────────────────────────────────
export const getDashboard = (days = null) => {
  const params = days != null ? `?days=${days}` : "";
  return api.get(`/metrics/dashboard${params}`).then((r) => r.data);
};

export const getEvalRuns = () => api.get("/metrics/eval").then((r) => r.data);
export const importEvalRun = (tag) =>
  api.post(`/metrics/eval/import?tag=${encodeURIComponent(tag)}`).then((r) => r.data);

/** Returns the log items array filtered by days (for timeline charts). */
export const getLogs = (limit = 100, days = null) => {
  const params = new URLSearchParams({ page: 1, page_size: limit });
  if (days != null) params.set("days", days);
  return api.get(`/metrics/logs?${params}`).then((r) => r.data.items);
};

/** Returns the full PaginatedResponse for paginated log views. */
export const getLogsPage = (page = 1, pageSize = 50) =>
  api.get(`/metrics/logs?page=${page}&page_size=${pageSize}`).then((r) => r.data);

export const getMyDashboard = (days = null) => {
  const params = days != null ? `?days=${days}` : "";
  return api.get(`/metrics/my-dashboard${params}`).then((r) => r.data);
};

export const getDailySessions = (days = null) => {
  const params = days != null ? `?days=${days}` : "";
  return api.get(`/metrics/daily-sessions${params}`).then((r) => r.data);
};

export const getFeedbackTrend = (days = null) => {
  const params = days != null ? `?days=${days}` : "";
  return api.get(`/metrics/feedback-trend${params}`).then((r) => r.data);
};

export const getTopQuestions = (days = null, limit = 10) => {
  const params = new URLSearchParams({ limit });
  if (days != null) params.set("days", days);
  return api.get(`/metrics/top-questions?${params}`).then((r) => r.data);
};

// ── Documents ─────────────────────────────────────────────────────────────────
export const uploadDocument = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/documents/upload", form).then((r) => r.data);
};

export const getDocumentJob = (jobId) =>
  api.get(`/documents/jobs/${jobId}`).then((r) => r.data);

export const getDocuments = () =>
  api.get("/documents").then((r) => r.data);

// ── Profile ───────────────────────────────────────────────────────────────────
export const getProfile = () =>
  api.get("/auth/profile").then((r) => r.data);

export const updateEmail = (email) =>
  api.patch("/auth/profile/email", { email }).then((r) => r.data);

export const updatePassword = (current_password, new_password) =>
  api.patch("/auth/profile/password", { current_password, new_password }).then((r) => r.data);

export const deleteAccount = () =>
  api.delete("/auth/profile");

// ── Admin ──────────────────────────────────────────────────────────────────────
export const getAdminUsers = () =>
  api.get("/admin/users").then((r) => r.data);

export const getSystemStatus = () =>
  api.get("/admin/system-status").then((r) => r.data);

export const getHourlyQueries = (days = 7) =>
  api.get(`/admin/hourly-queries?days=${days}`).then((r) => r.data);

export const getLatencyDaily = (days = 30) =>
  api.get(`/admin/latency-daily?days=${days}`).then((r) => r.data);

export const getAdminSettings = () =>
  api.get("/admin/settings").then((r) => r.data);

export const patchAdminSettings = (body) =>
  api.patch("/admin/settings", body).then((r) => r.data);

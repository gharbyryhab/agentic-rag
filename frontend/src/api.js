import axios from "axios";

const api = axios.create({ baseURL: "" }); // Vite proxy handles routing

// ── Chat ────────────────────────────────────────────────────────────────────
export const sendMessage = (question, session_id = null) =>
  api.post("/chat", { question, session_id }).then((r) => r.data);

// ── Sessions ─────────────────────────────────────────────────────────────────
export const getSessions = () => api.get("/sessions").then((r) => r.data);
export const getSession = (id) => api.get(`/sessions/${id}`).then((r) => r.data);
export const deleteSession = (id) => api.delete(`/sessions/${id}`);

// ── Feedback ──────────────────────────────────────────────────────────────────
export const submitFeedback = (message_id, rating, comment = null) =>
  api.post(`/messages/${message_id}/feedback`, { rating, comment }).then((r) => r.data);

// ── Metrics ───────────────────────────────────────────────────────────────────
export const getDashboard = () => api.get("/metrics/dashboard").then((r) => r.data);
export const getEvalRuns = () => api.get("/metrics/eval").then((r) => r.data);
export const importEvalRun = (tag) =>
  api.post(`/metrics/eval/import?tag=${encodeURIComponent(tag)}`).then((r) => r.data);
export const getLogs = (limit = 100) =>
  api.get(`/metrics/logs?limit=${limit}`).then((r) => r.data);

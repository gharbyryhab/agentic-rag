import { useState, useRef, useEffect, useCallback } from "react";
import {
  Upload, X, CheckCircle, AlertCircle,
  RefreshCw, Inbox, RotateCw, Database, FileText,
} from "lucide-react";
import { uploadDocument, getDocumentJob, getDocuments } from "../api";
import { useToast } from "../context/ToastContext";

const ALLOWED_EXTS = new Set([".pdf", ".docx", ".txt"]);
const MAX_BYTES = 50 * 1024 * 1024;

function formatBytes(bytes) {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024)        return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function getFileType(name) {
  const ext = name.slice(name.lastIndexOf(".")).toLowerCase();
  if (ext === ".pdf")  return { label: "PDF",  bg: "rgba(239,68,68,0.15)",  border: "rgba(239,68,68,0.3)",  color: "#fca5a5", dot: "#ef4444" };
  if (ext === ".docx") return { label: "DOCX", bg: "rgba(59,130,246,0.15)", border: "rgba(59,130,246,0.3)", color: "#93c5fd", dot: "#3b82f6" };
  if (ext === ".txt")  return { label: "TXT",  bg: "rgba(16,185,129,0.15)", border: "rgba(16,185,129,0.3)", color: "#6ee7b7", dot: "#10b981" };
  return { label: ext.slice(1).toUpperCase(), bg: "rgba(255,255,255,0.06)", border: "rgba(255,255,255,0.1)", color: "#94a3b8", dot: "#64748b" };
}

function FileTypeIcon({ name, size = 14 }) {
  const ft = getFileType(name);
  return (
    <div className="w-9 h-9 rounded-xl flex flex-col items-center justify-center flex-shrink-0"
         style={{ background: ft.bg, border: `1px solid ${ft.border}` }}>
      <FileText size={size} style={{ color: ft.color }} />
      <span className="text-[8px] font-black leading-none mt-0.5" style={{ color: ft.color }}>{ft.label}</span>
    </div>
  );
}

export default function DocumentsPage() {
  const [documents, setDocuments]     = useState([]);
  const [activeJobs, setActiveJobs]   = useState({});
  const [dragging, setDragging]       = useState(false);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const fileInputRef = useRef(null);
  const prevJobStatusRef = useRef({});
  const { addToast } = useToast();

  const fetchDocuments = useCallback(async () => {
    try { setDocuments(await getDocuments()); }
    catch { /* silent */ }
    finally { setLoadingDocs(false); }
  }, []);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  useEffect(() => {
    Object.entries(activeJobs).forEach(([id, job]) => {
      const prev = prevJobStatusRef.current[id];
      if (prev === "processing") {
        if (job.status === "done") {
          addToast(`"${job.filename}" indexed successfully`, "success");
          fetchDocuments();
        } else if (job.status === "error") {
          addToast(`Ingestion failed for "${job.filename}"`, "error");
        }
      }
    });
    prevJobStatusRef.current = Object.fromEntries(
      Object.entries(activeJobs).map(([id, j]) => [id, j.status])
    );
  }, [activeJobs, addToast, fetchDocuments]);

  useEffect(() => {
    const processingIds = Object.keys(activeJobs).filter((id) => activeJobs[id].status === "processing");
    if (processingIds.length === 0) return;
    const timer = setTimeout(async () => {
      const updates = {};
      await Promise.all(processingIds.map(async (jobId) => {
        try {
          const job = await getDocumentJob(jobId);
          updates[jobId] = { status: job.status, message: job.message };
        } catch { /* keep polling */ }
      }));
      if (Object.keys(updates).length > 0) {
        setActiveJobs((prev) => {
          const next = { ...prev };
          Object.entries(updates).forEach(([id, u]) => { next[id] = { ...next[id], ...u }; });
          return next;
        });
      }
    }, 2000);
    return () => clearTimeout(timer);
  }, [activeJobs]);

  const handleFiles = async (fileList) => {
    for (const file of Array.from(fileList)) {
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!ALLOWED_EXTS.has(ext)) { addToast(`Unsupported type: ${file.name}`, "error"); continue; }
      if (file.size > MAX_BYTES)  { addToast(`File too large (max 50 MB): ${file.name}`, "error"); continue; }
      try {
        const res = await uploadDocument(file);
        setActiveJobs((prev) => ({
          ...prev,
          [res.job_id]: { status: "processing", filename: res.filename, message: "" },
        }));
      } catch (err) {
        addToast(err.response?.data?.detail || "Upload failed", "error");
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrop      = (e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); };
  const handleDragOver  = (e) => { e.preventDefault(); setDragging(true); };
  const handleDragLeave = (e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false); };
  const dismissJob      = (jobId) => setActiveJobs((prev) => { const n = { ...prev }; delete n[jobId]; return n; });

  const jobList    = Object.entries(activeJobs);
  const anyPending = jobList.some(([, j]) => j.status === "processing");

  return (
    <div className="h-full overflow-y-auto" style={{ background: "#08091a" }}>
      <div className="max-w-4xl mx-auto px-8 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Database size={12} className="text-indigo-400" />
              <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-[0.15em]">Knowledge Base</span>
            </div>
            <h1 className="text-xl font-bold text-white">Documents</h1>
            <p className="text-sm text-slate-600 mt-0.5">
              Upload PDF, DOCX, or TXT files to expand the knowledge base
            </p>
          </div>
          {!loadingDocs && documents.length > 0 && (
            <div className="flex-shrink-0 flex items-center gap-2 px-4 py-2 rounded-2xl"
                 style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)" }}>
              <div className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
              <span className="text-xs font-semibold text-indigo-300">{documents.length} file{documents.length !== 1 ? "s" : ""} indexed</span>
            </div>
          )}
        </div>

        {/* Drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed rounded-2xl px-8 py-14 flex flex-col items-center
                     gap-4 cursor-pointer select-none transition-all duration-200"
          style={{
            borderColor: dragging ? "#6366f1" : "rgba(255,255,255,0.1)",
            background:  dragging ? "rgba(99,102,241,0.08)" : "rgba(255,255,255,0.02)",
            transform:   dragging ? "scale(1.01)" : "scale(1)",
          }}
          onMouseEnter={e => { if (!dragging) { e.currentTarget.style.borderColor = "rgba(99,102,241,0.4)"; e.currentTarget.style.background = "rgba(99,102,241,0.04)"; } }}
          onMouseLeave={e => { if (!dragging) { e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)"; e.currentTarget.style.background = "rgba(255,255,255,0.02)"; } }}
        >
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center transition-all duration-200"
               style={{
                 background: dragging ? "rgba(99,102,241,0.2)" : "rgba(255,255,255,0.05)",
                 border: `1px solid ${dragging ? "rgba(99,102,241,0.4)" : "rgba(255,255,255,0.08)"}`,
               }}>
            <Upload size={22} style={{ color: dragging ? "#818cf8" : "#475569" }} />
          </div>
          <div className="text-center pointer-events-none space-y-1">
            <p className="font-semibold text-slate-300 text-base">
              {dragging ? "Drop files here" : "Drag & drop files here"}
            </p>
            <p className="text-sm text-slate-600">or click to browse</p>
            {/* File type pills */}
            <div className="flex items-center justify-center gap-2 pt-2">
              {[
                { label: "PDF",  color: "#fca5a5", bg: "rgba(239,68,68,0.12)"  },
                { label: "DOCX", color: "#93c5fd", bg: "rgba(59,130,246,0.12)" },
                { label: "TXT",  color: "#6ee7b7", bg: "rgba(16,185,129,0.12)" },
              ].map(({ label, color, bg }) => (
                <span key={label} className="text-[10px] font-bold px-2 py-1 rounded-lg"
                      style={{ background: bg, color }}>
                  {label}
                </span>
              ))}
              <span className="text-[10px] text-slate-700">· max 50 MB each</span>
            </div>
          </div>
          <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt" multiple className="hidden"
            onChange={(e) => handleFiles(e.target.files)} />
        </div>

        {/* Active upload jobs */}
        {jobList.length > 0 && (
          <div className="space-y-2">
            <p className="text-[10px] font-bold text-slate-600 uppercase tracking-[0.12em]">
              Uploads
              {anyPending && <span className="ml-2 text-indigo-500 normal-case font-normal">· indexing in background…</span>}
            </p>
            {jobList.map(([jobId, job]) => (
              <JobCard key={jobId} job={job} onDismiss={() => dismissJob(jobId)} />
            ))}
          </div>
        )}

        {/* Document grid */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <p className="text-[10px] font-bold text-slate-600 uppercase tracking-[0.12em]">Indexed files</p>
            <button onClick={fetchDocuments}
              className="flex items-center gap-1.5 text-xs text-slate-700 hover:text-slate-300 transition-colors duration-150">
              <RefreshCw size={10} />
              Refresh
            </button>
          </div>

          {loadingDocs ? (
            <div className="flex justify-center p-10 rounded-2xl"
                 style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <RotateCw size={18} className="text-slate-800 animate-spin" />
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-2xl p-14 flex flex-col items-center gap-3"
                 style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
                   style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)" }}>
                <Inbox size={22} className="text-indigo-800" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-slate-600">No documents yet</p>
                <p className="text-xs text-slate-700 mt-1">Upload a file above to start building your knowledge base</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {documents.map((doc) => {
                const ft = getFileType(doc.name);
                return (
                  <div key={doc.name}
                       className="rounded-2xl p-4 flex flex-col gap-3 transition-all duration-200"
                       style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
                       onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.borderColor = `${ft.dot}30`; }}
                       onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)"; }}>
                    <div className="flex items-start gap-3">
                      <FileTypeIcon name={doc.name} />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-slate-300 truncate leading-snug">{doc.name}</p>
                        <p className="text-[10px] text-slate-700 mt-1">{formatBytes(doc.size)}</p>
                      </div>
                    </div>
                    <div className="flex items-center justify-between pt-2"
                         style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>
                      <span className="text-[10px] text-slate-700">
                        {new Date(doc.modified_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                      </span>
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md"
                            style={{ background: ft.bg, color: ft.color, border: `1px solid ${ft.border}` }}>
                        {ft.label}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="h-4" />
      </div>
    </div>
  );
}

// ── JobCard ───────────────────────────────────────────────────────────────────

function JobCard({ job, onDismiss }) {
  const done  = job.status === "done";
  const error = job.status === "error";
  const busy  = job.status === "processing";
  const [progress, setProgress] = useState(15);

  // Animate progress bar while busy
  useEffect(() => {
    if (!busy) { setProgress(done ? 100 : 0); return; }
    const tick = setInterval(() => {
      setProgress(p => p < 85 ? p + Math.random() * 6 : p);
    }, 600);
    return () => clearInterval(tick);
  }, [busy, done]);

  return (
    <div className="rounded-2xl px-4 py-3 space-y-2.5 transition-all duration-200"
         style={{
           background: done  ? "rgba(16,185,129,0.07)"  : error ? "rgba(239,68,68,0.07)" : "rgba(255,255,255,0.03)",
           border:     done  ? "1px solid rgba(16,185,129,0.2)" : error ? "1px solid rgba(239,68,68,0.2)" : "1px solid rgba(255,255,255,0.08)",
         }}>
      <div className="flex items-center gap-3">
        <div className="flex-shrink-0 w-5 flex justify-center">
          {busy  && <RotateCw    size={14} className="text-indigo-400 animate-spin" />}
          {done  && <CheckCircle size={14} className="text-emerald-400" />}
          {error && <AlertCircle size={14} className="text-red-400" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-300 truncate">{job.filename}</p>
          <p className="text-xs mt-0.5 leading-snug"
             style={{ color: done ? "#6ee7b7" : error ? "#fca5a5" : "#64748b" }}>
            {busy  ? "Indexing into knowledge base…"       :
             done  ? job.message || "Indexed successfully" :
                     job.message || "Ingestion failed"}
          </p>
        </div>
        {!busy && (
          <button onClick={onDismiss} title="Dismiss"
            className="flex-shrink-0 p-1 rounded-lg text-slate-700 hover:text-slate-300 transition-all duration-150">
            <X size={12} />
          </button>
        )}
      </div>

      {/* Progress bar */}
      {(busy || done) && (
        <div className="h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
          <div className="h-full rounded-full transition-all duration-700 ease-out"
               style={{
                 width: `${done ? 100 : progress}%`,
                 background: done ? "linear-gradient(90deg,#10b981,#6ee7b7)" : "linear-gradient(90deg,#6366f1,#8b5cf6)",
               }} />
        </div>
      )}
    </div>
  );
}

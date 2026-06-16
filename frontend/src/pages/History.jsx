import { useEffect, useRef, useState } from "react";
import {
  Trash2, MessageSquare, ChevronRight, ChevronLeft, BookOpen, Globe,
  ThumbsUp, ThumbsDown, Sparkles, Clock, Inbox, Search, History,
} from "lucide-react";
import { getSessions, getSession, deleteSession, renameSession } from "../api";
import { useToast } from "../context/ToastContext";
import MarkdownMessage from "../components/MarkdownMessage";

const ROUTE_BADGE = {
  simple:          "badge-emerald",
  agent:           "badge-violet",
  memory:          "badge-sky",
  out_of_domain:   "badge-slate",
  simple_fallback: "badge-amber",
  agent_fallback:  "badge-amber",
};

const PANEL_BG  = { background: "rgba(255,255,255,0.02)", borderRight: "1px solid rgba(255,255,255,0.06)" };
const CARD_DARK = { background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14 };

function relTime(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d === 1) return "yesterday";
  if (d < 7)  return `${d}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function HistoryPage() {
  const [sessions, setSessions]           = useState([]);
  const [selected, setSelected]           = useState(null);
  const [detail, setDetail]               = useState(null);
  const [loadingList, setLoadingList]     = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const { addToast } = useToast();

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch]           = useState("");
  const [page, setPage]               = useState(1);
  const [total, setTotal]             = useState(0);
  const [pages, setPages]             = useState(1);
  const [refreshKey, setRefreshKey]   = useState(0);

  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    setLoadingList(true);
    (async () => {
      try {
        const data = await getSessions(page, 20, search || null);
        setSessions(data.items); setTotal(data.total); setPages(data.pages);
      } finally { setLoadingList(false); }
    })();
  }, [page, search, refreshKey]);

  const handleSelect = async (id) => {
    if (selected === id) return;
    setSelected(id); setDetail(null); setLoadingDetail(true);
    try { setDetail(await getSession(id)); }
    finally { setLoadingDetail(false); }
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    await deleteSession(id);
    if (selected === id) { setSelected(null); setDetail(null); }
    addToast("Session deleted", "success");
    const remaining = sessions.filter((s) => s.id !== id).length;
    if (remaining === 0 && page > 1) setPage((p) => p - 1);
    else setRefreshKey((k) => k + 1);
  };

  const handleRename = async (newTitle) => {
    if (!selected) return;
    try {
      const updated = await renameSession(selected, newTitle);
      setDetail((d) => (d ? { ...d, title: updated.title } : d));
      setSessions((prev) => prev.map((s) => (s.id === selected ? { ...s, title: updated.title } : s)));
      addToast("Session renamed", "success");
    } catch { addToast("Could not rename session", "error"); }
  };

  return (
    <div className="flex h-full" style={{ background: "#08091a" }}>
      {/* ── Session list panel ─────────────────────────────────────────────── */}
      <div className="w-[264px] flex-shrink-0 flex flex-col" style={PANEL_BG}>

        {/* Header */}
        <div className="px-4 pt-5 pb-3 space-y-3"
             style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-baseline justify-between">
            <h1 className="font-semibold text-slate-200 text-sm">Session History</h1>
            {!loadingList && (
              <span className="text-[10px] text-slate-700 tabular-nums">
                {total} session{total !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          {/* Search */}
          <div className="relative">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-700 pointer-events-none" />
            <input type="search" placeholder="Search sessions…" value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs rounded-xl transition-all duration-150"
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)", color: "#cbd5e1" }}
              onFocus={e => e.target.style.borderColor = "rgba(99,102,241,0.4)"}
              onBlur={e => e.target.style.borderColor = "rgba(255,255,255,0.07)"}
            />
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {loadingList && (
            <div className="flex justify-center pt-10">
              <div className="w-4 h-4 border-2 rounded-full animate-spin"
                   style={{ borderColor: "rgba(255,255,255,0.1)", borderTopColor: "#6366f1" }} />
            </div>
          )}

          {!loadingList && sessions.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 px-6 pb-10 text-center">
              <Inbox size={32} className="text-slate-800" />
              <p className="text-xs text-slate-700">
                {search ? "No sessions match your search." : "No sessions yet. Start a chat!"}
              </p>
            </div>
          )}

          {sessions.map((s) => (
            <button key={s.id} onClick={() => handleSelect(s.id)}
              className="w-full text-left px-3 py-3 group flex items-start gap-2.5 transition-all duration-150"
              style={{
                borderBottom: "1px solid rgba(255,255,255,0.04)",
                borderLeft: `2px solid ${selected === s.id ? "#6366f1" : "transparent"}`,
                background: selected === s.id ? "rgba(99,102,241,0.08)" : "transparent",
              }}
              onMouseEnter={e => { if (selected !== s.id) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
              onMouseLeave={e => { if (selected !== s.id) e.currentTarget.style.background = "transparent"; }}
            >
              <div className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                   style={{ background: selected === s.id ? "rgba(99,102,241,0.2)" : "rgba(255,255,255,0.04)" }}>
                <MessageSquare size={10} style={{ color: selected === s.id ? "#818cf8" : "#475569" }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[11px] font-semibold truncate leading-snug"
                   style={{ color: selected === s.id ? "#a5b4fc" : "#94a3b8" }}>
                  {s.title}
                </p>
                {s.preview && (
                  <p className="text-[10px] text-slate-700 mt-0.5 truncate leading-snug italic">
                    {s.preview}
                  </p>
                )}
                <p className="text-[9px] text-slate-700 mt-1 flex items-center gap-1">
                  <Clock size={7} />
                  {s.message_count} msg · {relTime(s.updated_at)}
                </p>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150 flex-shrink-0">
                <button onClick={(e) => handleDelete(s.id, e)} title="Delete"
                  className="p-1 rounded-lg transition-colors text-slate-700 hover:text-red-400">
                  <Trash2 size={10} />
                </button>
              </div>
            </button>
          ))}
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex-shrink-0 px-4 py-2.5 flex items-center justify-between"
               style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
              className="p-1 rounded-lg text-slate-700 hover:text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed transition-all">
              <ChevronLeft size={14} />
            </button>
            <span className="text-xs text-slate-700 tabular-nums">{page} / {pages}</span>
            <button onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page >= pages}
              className="p-1 rounded-lg text-slate-700 hover:text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed transition-all">
              <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>

      {/* ── Detail panel ──────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto" style={{ background: "#08091a" }}>
        {!selected && (
          <div className="flex flex-col items-center justify-center h-full gap-4 select-none px-8">
            <div className="relative">
              <div className="absolute inset-0 rounded-3xl blur-2xl opacity-30"
                   style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }} />
              <div className="relative w-16 h-16 rounded-3xl flex items-center justify-center"
                   style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)" }}>
                <History size={26} className="text-indigo-700" />
              </div>
            </div>
            <div className="text-center">
              <p className="font-semibold text-slate-500 text-sm">Pick a session</p>
              <p className="text-xs text-slate-700 mt-1">Select a conversation from the left to read through it</p>
            </div>
          </div>
        )}

        {selected && loadingDetail && (
          <div className="flex items-center justify-center h-full gap-3 text-slate-600">
            <div className="w-4 h-4 border-2 rounded-full animate-spin"
                 style={{ borderColor: "rgba(255,255,255,0.1)", borderTopColor: "#6366f1" }} />
            <span className="text-sm">Loading session…</span>
          </div>
        )}

        {detail && !loadingDetail && (
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-5 animate-fade-in">
            {/* Session header */}
            <div className="rounded-2xl p-4 flex items-start gap-4" style={CARD_DARK}>
              <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                   style={{ background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.25)" }}>
                <MessageSquare size={15} className="text-indigo-400" />
              </div>
              <div className="flex-1 min-w-0">
                <InlineTitle value={detail.title} onCommit={handleRename} />
                <p className="text-[11px] text-slate-600 mt-0.5">
                  {detail.message_count} messages · Started {new Date(detail.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>

            {detail.messages.map((msg) => (
              <HistoryMessage key={msg.id} msg={msg} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── InlineTitle ───────────────────────────────────────────────────────────────

function InlineTitle({ value, onCommit }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef(null);

  useEffect(() => { setDraft(value); }, [value]);
  useEffect(() => { if (editing) inputRef.current?.select(); }, [editing]);

  const commit = () => {
    const trimmed = draft.trim();
    if (trimmed && trimmed !== value) onCommit(trimmed);
    else setDraft(value);
    setEditing(false);
  };

  if (editing) {
    return (
      <input ref={inputRef} value={draft} maxLength={100}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); commit(); }
          if (e.key === "Escape") { setDraft(value); setEditing(false); }
        }}
        className="w-full font-semibold text-sm bg-transparent outline-none pb-0.5"
        style={{ color: "#e2e8f0", borderBottom: "2px solid #6366f1" }}
      />
    );
  }

  return (
    <h2 onDoubleClick={() => setEditing(true)} title="Double-click to rename"
      className="font-semibold text-slate-200 truncate cursor-text hover:text-indigo-300 transition-colors duration-150 text-sm">
      {value}
    </h2>
  );
}

// ── HistoryMessage ────────────────────────────────────────────────────────────

function HistoryMessage({ msg }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="rounded-2xl rounded-tr-sm px-4 py-3 max-w-xl text-sm leading-relaxed text-white"
             style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)", boxShadow: "0 4px 20px rgba(99,102,241,0.25)" }}>
          {msg.content}
        </div>
      </div>
    );
  }

  const badgeClass = ROUTE_BADGE[msg.route] || "badge-slate";
  const hasSources = msg.sources?.length > 0;

  return (
    <div className="flex gap-3 items-start">
      <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5"
           style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.3))", border: "1px solid rgba(99,102,241,0.3)", boxShadow: "0 0 15px rgba(99,102,241,0.15)" }}>
        <Sparkles size={13} className="text-indigo-300" />
      </div>

      <div className="flex-1 max-w-2xl space-y-2">
        <div className="rounded-2xl px-4 py-3.5" style={CARD_DARK}>
          <MarkdownMessage content={msg.content} />
        </div>

        <div className="flex items-center gap-2 text-xs px-0.5 flex-wrap">
          {msg.route && <span className={badgeClass}>{msg.route.replace("_", " ")}</span>}
          {msg.latency_s != null && <span className="text-slate-700">{msg.latency_s}s</span>}
          {msg.feedback_rating === 1 && (
            <span className="flex items-center gap-1 text-emerald-400 font-medium text-[11px]">
              <ThumbsUp size={10} /> Helpful
            </span>
          )}
          {msg.feedback_rating === -1 && (
            <span className="flex items-center gap-1 text-red-400 font-medium text-[11px]">
              <ThumbsDown size={10} /> Not helpful
            </span>
          )}
          {hasSources && (
            <button onClick={() => setSourcesOpen((o) => !o)}
              className="flex items-center gap-1 text-[11px] text-slate-700 hover:text-indigo-400 transition-colors duration-150">
              <BookOpen size={10} />
              {sourcesOpen ? "Hide" : "Show"} {msg.sources.length} source{msg.sources.length !== 1 ? "s" : ""}
            </button>
          )}
        </div>

        {sourcesOpen && hasSources && (
          <div className="space-y-1.5 pl-0.5 animate-fade-in">
            {msg.sources.map((s, i) => (
              <HistorySourceCard key={i} source={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function HistorySourceCard({ source }) {
  const isWeb = source.source?.startsWith("http") || source.source?.includes("tool:");
  return (
    <div className="rounded-xl px-3.5 py-2.5 text-xs space-y-1.5"
         style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="flex items-center gap-2 font-medium text-slate-400">
        {isWeb
          ? <Globe   size={10} className="text-indigo-400 flex-shrink-0" />
          : <BookOpen size={10} className="text-slate-600 flex-shrink-0" />
        }
        <span className="truncate">{source.book_title || source.source || "Source"}</span>
        {source.page && <span className="text-slate-700 flex-shrink-0 font-normal">· p.{source.page}</span>}
      </div>
      {source.snippet && (
        <p className="text-slate-600 leading-relaxed line-clamp-2">{source.snippet}</p>
      )}
    </div>
  );
}

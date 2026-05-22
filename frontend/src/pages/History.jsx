import { useEffect, useState } from "react";
import {
  Trash2, MessageSquare, ChevronRight, BookOpen, Globe,
  ThumbsUp, ThumbsDown, Sparkles, Clock, Inbox,
} from "lucide-react";
import { getSessions, getSession, deleteSession } from "../api";

const ROUTE_BADGE = {
  simple:          "badge-emerald",
  agent:           "badge-violet",
  memory:          "badge-sky",
  out_of_domain:   "badge-slate",
  simple_fallback: "badge-amber",
  agent_fallback:  "badge-amber",
};

export default function HistoryPage() {
  const [sessions, setSessions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const data = await getSessions();
        setSessions(data);
      } finally {
        setLoadingList(false);
      }
    })();
  }, []);

  const handleSelect = async (id) => {
    if (selected === id) return;
    setSelected(id);
    setDetail(null);
    setLoadingDetail(true);
    try {
      const data = await getSession(id);
      setDetail(data);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    await deleteSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (selected === id) {
      setSelected(null);
      setDetail(null);
    }
  };

  return (
    <div className="flex h-full">
      {/* ── Session list ──────────────────────────────────────────────────── */}
      <div className="w-72 flex-shrink-0 border-r border-slate-100 bg-white flex flex-col">
        <div className="px-5 py-4 border-b border-slate-100">
          <h1 className="font-semibold text-slate-800 text-sm">Session History</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            {loadingList ? "Loading…" : `${sessions.length} conversation${sessions.length !== 1 ? "s" : ""}`}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto">
          {!loadingList && sessions.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-300 px-6 pb-10">
              <Inbox size={36} />
              <p className="text-sm text-center">No sessions yet.<br />Start a chat!</p>
            </div>
          )}

          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => handleSelect(s.id)}
              className={`w-full text-left px-4 py-3.5 border-b border-slate-50 transition-all duration-150 group flex items-start gap-3 ${
                selected === s.id
                  ? "bg-indigo-50 border-l-2 border-l-indigo-500"
                  : "hover:bg-slate-50"
              }`}
            >
              <MessageSquare
                size={14}
                className={`mt-0.5 flex-shrink-0 ${selected === s.id ? "text-indigo-400" : "text-slate-300"}`}
              />
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium truncate ${selected === s.id ? "text-indigo-700" : "text-slate-700"}`}>
                  {s.title}
                </p>
                <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-1.5">
                  <Clock size={10} />
                  {s.message_count} msg · {new Date(s.updated_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                <button
                  onClick={(e) => handleDelete(s.id, e)}
                  className="btn-danger-ghost"
                  title="Delete session"
                >
                  <Trash2 size={12} />
                </button>
                <ChevronRight size={12} className="text-slate-300" />
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* ── Session detail ────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto bg-slate-50">
        {/* Placeholder — nothing selected */}
        {!selected && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-300 select-none">
            <MessageSquare size={40} />
            <p className="text-sm">Select a session to view its messages</p>
          </div>
        )}

        {/* Loading detail */}
        {selected && loadingDetail && (
          <div className="flex items-center justify-center h-full text-slate-400 gap-2">
            <div className="w-4 h-4 border-2 border-slate-300 border-t-indigo-500 rounded-full animate-spin" />
            <span className="text-sm">Loading session…</span>
          </div>
        )}

        {/* Session messages */}
        {detail && !loadingDetail && (
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-5 animate-fade-in">
            {/* Session header */}
            <div className="card p-4 flex items-start gap-4">
              <div className="w-9 h-9 rounded-xl bg-indigo-100 flex items-center justify-center flex-shrink-0">
                <MessageSquare size={16} className="text-indigo-600" />
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="font-semibold text-slate-800 truncate">{detail.title}</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  {detail.message_count} messages · Started {new Date(detail.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>

            {/* Messages */}
            {detail.messages.map((msg) => (
              <HistoryMessage key={msg.id} msg={msg} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── HistoryMessage ────────────────────────────────────────────────────────────

function HistoryMessage({ msg }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-gradient-to-br from-indigo-600 to-indigo-700 text-white
                        rounded-2xl rounded-tr-sm px-4 py-3 max-w-xl text-sm leading-relaxed shadow-sm">
          {msg.content}
        </div>
      </div>
    );
  }

  const badgeClass = ROUTE_BADGE[msg.route] || "badge-slate";
  const hasSources = msg.sources?.length > 0;

  return (
    <div className="flex gap-3 items-start">
      {/* Avatar */}
      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600
                      flex items-center justify-center flex-shrink-0 shadow-sm mt-0.5">
        <Sparkles size={13} className="text-white" />
      </div>

      <div className="flex-1 max-w-2xl space-y-2">
        {/* Content */}
        <div className="card px-4 py-3.5">
          <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-800">{msg.content}</p>
        </div>

        {/* Meta */}
        <div className="flex items-center gap-2 text-xs text-slate-400 px-0.5 flex-wrap">
          {msg.route && <span className={badgeClass}>{msg.route.replace("_", " ")}</span>}
          {msg.latency_s != null && (
            <span className="text-slate-400">{msg.latency_s}s</span>
          )}
          {msg.feedback_rating === 1 && (
            <span className="flex items-center gap-1 text-emerald-500 font-medium">
              <ThumbsUp size={11} /> Helpful
            </span>
          )}
          {msg.feedback_rating === -1 && (
            <span className="flex items-center gap-1 text-red-400 font-medium">
              <ThumbsDown size={11} /> Not helpful
            </span>
          )}
          {hasSources && (
            <button
              onClick={() => setSourcesOpen((o) => !o)}
              className="text-slate-400 hover:text-indigo-600 transition-colors duration-150 flex items-center gap-1"
            >
              <BookOpen size={11} />
              {sourcesOpen ? "Hide" : "Show"} {msg.sources.length} source{msg.sources.length !== 1 ? "s" : ""}
            </button>
          )}
        </div>

        {/* Sources */}
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
  const isWeb =
    source.source?.startsWith("http") ||
    source.source?.includes("tool:");

  return (
    <div className="bg-white border border-slate-100 rounded-xl px-3.5 py-2.5 text-xs space-y-1.5 shadow-sm">
      <div className="flex items-center gap-2 font-medium text-slate-700">
        {isWeb ? (
          <Globe size={11} className="text-indigo-400 flex-shrink-0" />
        ) : (
          <BookOpen size={11} className="text-slate-400 flex-shrink-0" />
        )}
        <span className="truncate">{source.book_title || source.source || "Source"}</span>
        {source.page && (
          <span className="text-slate-400 flex-shrink-0 font-normal">· p.{source.page}</span>
        )}
      </div>
      {source.snippet && (
        <p className="text-slate-500 leading-relaxed line-clamp-2">{source.snippet}</p>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { Trash2, MessageSquare, ChevronRight, ArrowLeft, BookOpen, Globe, ThumbsUp, ThumbsDown } from "lucide-react";
import { getSessions, getSession, deleteSession } from "../api";

export default function HistoryPage() {
  const [sessions, setSessions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadSessions = async () => {
    setLoading(true);
    try {
      const data = await getSessions();
      setSessions(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadSessions(); }, []);

  const handleSelect = async (id) => {
    setSelected(id);
    setDetail(null);
    const data = await getSession(id);
    setDetail(data);
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    await deleteSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (selected === id) { setSelected(null); setDetail(null); }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-full text-slate-400">Loading…</div>;
  }

  return (
    <div className="flex h-full">
      {/* Sessions list */}
      <div className="w-72 flex-shrink-0 border-r border-slate-200 bg-white flex flex-col">
        <div className="px-4 py-4 border-b border-slate-100">
          <h1 className="font-semibold text-slate-800">Session History</h1>
          <p className="text-xs text-slate-400 mt-0.5">{sessions.length} conversation{sessions.length !== 1 ? "s" : ""}</p>
        </div>
        <div className="flex-1 overflow-y-auto">
          {sessions.length === 0 && (
            <p className="text-sm text-slate-400 text-center mt-12 px-4">No sessions yet. Start a chat!</p>
          )}
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => handleSelect(s.id)}
              className={`w-full text-left px-4 py-3.5 border-b border-slate-50 hover:bg-slate-50 transition-colors group flex items-start gap-3 ${
                selected === s.id ? "bg-blue-50 border-l-2 border-l-blue-500" : ""
              }`}
            >
              <MessageSquare size={15} className="text-slate-300 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-700 truncate">{s.title}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {s.message_count} messages · {new Date(s.updated_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => handleDelete(s.id, e)}
                  className="p-1 rounded hover:bg-red-50 hover:text-red-500 text-slate-300 transition-colors"
                >
                  <Trash2 size={13} />
                </button>
                <ChevronRight size={13} className="text-slate-300" />
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Session detail */}
      <div className="flex-1 overflow-y-auto bg-slate-50">
        {!selected && (
          <div className="flex flex-col items-center justify-center h-full text-slate-300 gap-3">
            <MessageSquare size={40} />
            <p className="text-sm">Select a session to view its messages</p>
          </div>
        )}
        {selected && !detail && (
          <div className="flex items-center justify-center h-full text-slate-400">Loading session…</div>
        )}
        {detail && (
          <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
            <div className="flex items-center gap-3">
              <button onClick={() => { setSelected(null); setDetail(null); }} className="btn-ghost p-2">
                <ArrowLeft size={16} />
              </button>
              <div>
                <h2 className="font-semibold text-slate-800">{detail.title}</h2>
                <p className="text-xs text-slate-400">
                  {detail.message_count} messages · {new Date(detail.created_at).toLocaleDateString()}
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

function HistoryMessage({ msg }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 max-w-xl text-sm leading-relaxed">
          {msg.content}
        </div>
      </div>
    );
  }

  const routeBadge = msg.route === "agent" ? "bg-purple-100 text-purple-700" : "bg-green-100 text-green-700";

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 text-white text-xs font-bold">
        AI
      </div>
      <div className="flex-1 max-w-2xl space-y-2">
        <div className="card px-4 py-3">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400 px-1">
          {msg.route && <span className={`px-2 py-0.5 rounded-full font-medium ${routeBadge}`}>{msg.route}</span>}
          {msg.latency_s != null && <span>{msg.latency_s}s</span>}
          {msg.feedback_rating === 1 && <span className="flex items-center gap-1 text-green-500"><ThumbsUp size={12} /> Helpful</span>}
          {msg.feedback_rating === -1 && <span className="flex items-center gap-1 text-red-400"><ThumbsDown size={12} /> Not helpful</span>}
          {msg.sources?.length > 0 && (
            <button onClick={() => setSourcesOpen((o) => !o)} className="hover:text-slate-600 transition-colors">
              {sourcesOpen ? "Hide" : "Show"} {msg.sources.length} source{msg.sources.length > 1 ? "s" : ""}
            </button>
          )}
        </div>
        {sourcesOpen && msg.sources?.map((s, i) => (
          <div key={i} className="card px-3 py-2 text-xs text-slate-500">
            <span className="font-medium text-slate-700">{s.book_title || s.source}</span>
            {s.page && <span className="ml-1 text-slate-400">p.{s.page}</span>}
            {s.snippet && <p className="mt-1 line-clamp-2">{s.snippet}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

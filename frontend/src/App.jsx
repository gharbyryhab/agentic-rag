import { Routes, Route, NavLink, Navigate, useNavigate } from "react-router-dom";
import { MessageSquare, LayoutDashboard, History, Plus, Trash2, Brain } from "lucide-react";
import { useEffect, useState, useCallback } from "react";
import ChatPage from "./pages/Chat";
import DashboardPage from "./pages/Dashboard";
import HistoryPage from "./pages/History";
import { ChatProvider, useChatContext } from "./context/ChatContext";
import { getSessions, deleteSession } from "./api";

function Sidebar() {
  const [sessions, setSessions] = useState([]);
  const { sessionId, newChat, loadSession } = useChatContext();
  const navigate = useNavigate();

  const fetchSessions = useCallback(async () => {
    try {
      const data = await getSessions();
      setSessions(data);
    } catch {
      // backend not ready yet
    }
  }, []);

  // Single effect: runs on mount (sessionId = null) and whenever a new session is confirmed
  useEffect(() => {
    fetchSessions();
  }, [sessionId, fetchSessions]);

  const handleNew = () => {
    newChat();
    navigate("/chat");
  };

  const handleSelect = async (id) => {
    await loadSession(id);
    navigate("/chat");
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    await deleteSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (sessionId === id) newChat();
  };

  const navItems = [
    { to: "/chat", label: "Chat", icon: MessageSquare },
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { to: "/history", label: "History", icon: History },
  ];

  return (
    <aside className="w-64 flex-shrink-0 bg-sidebar flex flex-col h-full select-none">
      {/* Logo */}
      <div className="px-4 py-5 flex items-center gap-3">
        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-900/40 flex-shrink-0">
          <Brain size={15} className="text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-white font-semibold text-sm tracking-tight leading-tight">Agentic RAG</p>
          <p className="text-slate-500 text-[10px] leading-tight mt-0.5">DS / ML Knowledge Base</p>
        </div>
      </div>

      {/* Main navigation */}
      <nav className="px-2 mb-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 mb-0.5 ${
                isActive
                  ? "bg-indigo-600 text-white shadow-sm shadow-indigo-900/30"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              }`
            }
          >
            <Icon size={15} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Divider */}
      <div className="mx-4 my-2 h-px bg-white/5" />

      {/* New conversation */}
      <div className="px-2 mb-3">
        <button
          onClick={handleNew}
          className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium
                     text-slate-400 hover:text-indigo-300
                     border border-white/8 hover:border-indigo-500/40 hover:bg-indigo-500/10
                     transition-all duration-150"
        >
          <Plus size={14} />
          New conversation
        </button>
      </div>

      {/* Sessions label */}
      <div className="px-4 pb-1.5">
        <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-widest">Recent</p>
      </div>

      {/* Sessions list */}
      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-0.5">
        {sessions.length === 0 && (
          <p className="text-xs text-slate-600 text-center mt-8 px-4 leading-relaxed">
            No conversations yet.<br />Start a new chat!
          </p>
        )}
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => handleSelect(s.id)}
            className={`w-full text-left px-3 py-2.5 rounded-lg group flex items-start gap-2.5 transition-all duration-150 ${
              sessionId === s.id
                ? "bg-indigo-600/20 text-indigo-300"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
            }`}
          >
            <MessageSquare size={11} className="mt-0.5 flex-shrink-0 opacity-50" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate leading-snug">{s.title}</p>
              <p className="text-[10px] text-slate-600 mt-0.5 leading-tight">
                {s.message_count} msg · {new Date(s.updated_at).toLocaleDateString()}
              </p>
            </div>
            <button
              onClick={(e) => handleDelete(s.id, e)}
              className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:text-red-400
                         transition-all duration-150 flex-shrink-0 mt-0.5"
            >
              <Trash2 size={11} />
            </button>
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-white/5">
        <p className="text-[10px] text-slate-600 leading-relaxed">Gemma-4 · BGE · ChromaDB</p>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <ChatProvider>
      <div className="flex h-screen overflow-hidden bg-slate-50">
        <Sidebar />
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/history" element={<HistoryPage />} />
          </Routes>
        </main>
      </div>
    </ChatProvider>
  );
}

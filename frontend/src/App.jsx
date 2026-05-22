import { Routes, Route, NavLink, Navigate, useNavigate } from "react-router-dom";
import { MessageSquare, LayoutDashboard, History, Plus, Trash2 } from "lucide-react";
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

  // Charger la liste au montage
  useEffect(() => { fetchSessions(); }, [fetchSessions]);

  // Rafraîchir quand sessionId change (nouveau message envoyé)
  useEffect(() => { fetchSessions(); }, [sessionId, fetchSessions]);

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
    // Si on supprime la session active → nouveau chat
    if (sessionId === id) {
      newChat();
    }
  };

  const navItems = [
    { to: "/chat", label: "Chat", icon: MessageSquare },
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { to: "/history", label: "History", icon: History },
  ];

  return (
    <aside className="w-60 flex-shrink-0 bg-white border-r border-slate-200 flex flex-col h-full">
      {/* Logo */}
      <div className="px-5 py-4 border-b border-slate-100">
        <span className="text-lg font-bold text-blue-600">Agentic RAG</span>
        <p className="text-xs text-slate-400 mt-0.5">DS/ML Knowledge Base</p>
      </div>

      {/* Navigation principale */}
      <nav className="px-3 pt-3 pb-2 space-y-0.5">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-50 text-blue-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Bouton nouvelle discussion */}
      <div className="px-3 pb-2">
        <button
          onClick={handleNew}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 border border-dashed border-slate-200 hover:border-blue-300 hover:text-blue-600 transition-colors"
        >
          <Plus size={15} />
          Nouvelle discussion
        </button>
      </div>

      <div className="px-4 py-1">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Discussions</p>
      </div>

      {/* Liste des sessions */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {sessions.length === 0 && (
          <p className="text-xs text-slate-300 text-center mt-6 px-4">
            Aucune discussion.<br />Pose ta première question !
          </p>
        )}
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => handleSelect(s.id)}
            className={`w-full text-left px-3 py-2.5 rounded-lg mb-0.5 group flex items-start gap-2 transition-colors ${
              sessionId === s.id
                ? "bg-blue-50 text-blue-700"
                : "hover:bg-slate-50 text-slate-600"
            }`}
          >
            <MessageSquare size={13} className="mt-0.5 flex-shrink-0 opacity-50" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate leading-snug">{s.title}</p>
              <p className="text-[10px] text-slate-400 mt-0.5">
                {s.message_count} msg · {new Date(s.updated_at).toLocaleDateString("fr-FR")}
              </p>
            </div>
            <button
              onClick={(e) => handleDelete(s.id, e)}
              className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:text-red-400 transition-all flex-shrink-0"
            >
              <Trash2 size={12} />
            </button>
          </button>
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-slate-100">
        <p className="text-[10px] text-slate-400">Gemma-4 · BGE · ChromaDB</p>
      </div>
    </aside>
  );
}

export default function App() {
  return (
    <ChatProvider>
      <div className="flex h-screen overflow-hidden">
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

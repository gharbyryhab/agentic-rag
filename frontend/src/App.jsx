import { Routes, Route, NavLink, Navigate, useNavigate, useLocation } from "react-router-dom";
import {
  MessageSquare, LayoutDashboard, History, Plus, Trash2,
  Brain, FileText, LogOut, Settings, Sparkles, ChevronRight,
  PanelLeftClose, PanelLeftOpen, ShieldCheck, Users, Activity,
} from "lucide-react";
import { useEffect, useState, useCallback } from "react";
import ChatPage       from "./pages/Chat";
import AdminDashboard from "./pages/AdminDashboard";
import UserDashboard  from "./pages/UserDashboard";
import HistoryPage    from "./pages/History";
import DocumentsPage  from "./pages/Documents";
import SettingsPage   from "./pages/Settings";
import LoginPage      from "./pages/Login";
import { ChatProvider, useChatContext } from "./context/ChatContext";
import { AuthProvider, useAuth }        from "./context/AuthContext";
import { useToast }                     from "./context/ToastContext";
import { ToastContainer }               from "./components/Toast";
import { getSessions, deleteSession }   from "./api";

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

// ── Tooltip wrapper for collapsed icon mode ────────────────────────────────
function IconTooltip({ label, children }) {
  return (
    <div className="relative group/tip">
      {children}
      <div className="absolute left-full top-1/2 -translate-y-1/2 ml-3 px-2.5 py-1.5 rounded-lg
                      pointer-events-none opacity-0 group-hover/tip:opacity-100
                      transition-opacity duration-150 whitespace-nowrap z-50 text-xs font-medium text-white"
           style={{ background: "#1e1f3a", border: "1px solid rgba(99,102,241,0.25)", boxShadow: "0 4px 16px rgba(0,0,0,0.4)" }}>
        {label}
        <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent"
             style={{ borderRightColor: "#1e1f3a" }} />
      </div>
    </div>
  );
}

// ── Sidebar ────────────────────────────────────────────────────────────────────
function Sidebar({ collapsed, setCollapsed }) {
  const [sessions, setSessions] = useState([]);
  const { sessionId, newChat, loadSession } = useChatContext();
  const { addToast } = useToast();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isAdmin  = user?.role === "admin";

  const fetchSessions = useCallback(async () => {
    try {
      const data = await getSessions();
      setSessions(Array.isArray(data) ? data : (data.items ?? []));
    } catch { /* silent */ }
  }, []);

  useEffect(() => { fetchSessions(); }, [sessionId, fetchSessions]);

  const handleNew    = ()         => { newChat(); navigate("/chat"); };
  const handleSelect = async (id) => { await loadSession(id); navigate("/chat"); };
  const handleDelete = async (id, e) => {
    e.stopPropagation();
    await deleteSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (sessionId === id) newChat();
    addToast("Session deleted", "success");
  };
  const handleLogout = () => { logout(); navigate("/login", { replace: true }); };

  // Nav items — top section (no Settings here, it moves to bottom)
  const topNav = [
    { to: "/chat",      label: "Chat",      icon: MessageSquare,   adminOnly: false },
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, adminOnly: false },
    { to: "/history",   label: "History",   icon: History,         adminOnly: false },
    { to: "/documents", label: "Documents", icon: FileText,        adminOnly: true  },
  ].filter((item) => !item.adminOnly || isAdmin);

  const avatarLetter = user?.email?.[0]?.toUpperCase() ?? "?";
  const W = collapsed ? "64px" : "240px";

  const NavItem = ({ to, label, icon: Icon }) => {
    const active = location.pathname.startsWith(to);
    const inner = (
      <NavLink to={to}
        className={`flex items-center rounded-xl font-medium transition-all duration-200
                    ${collapsed ? "justify-center w-10 h-10 mx-auto" : "gap-3 px-3 py-2.5 text-sm"}
                    ${active ? "nav-active" : "nav-inactive"}`}
        style={collapsed && active ? {
          background: "rgba(99,102,241,0.18)",
          borderLeft: "none",
          outline: "1px solid rgba(99,102,241,0.3)",
        } : collapsed ? { borderLeft: "none" } : {}}
      >
        <Icon size={15} className={active ? "text-indigo-400" : ""} />
        {!collapsed && <><span className="flex-1">{label}</span>{active && <ChevronRight size={12} className="text-indigo-400 opacity-60" />}</>}
      </NavLink>
    );
    return collapsed ? <IconTooltip label={label}>{inner}</IconTooltip> : inner;
  };

  return (
    <aside className="flex-shrink-0 flex flex-col h-full select-none relative overflow-hidden transition-all duration-300"
           style={{ width: W, background: "#080912", borderRight: "1px solid rgba(255,255,255,0.05)" }}>

      {/* Top glow */}
      <div className="absolute top-0 left-0 right-0 h-40 pointer-events-none"
           style={{ background: "radial-gradient(ellipse at top, rgba(99,102,241,0.06) 0%, transparent 70%)" }} />

      {/* ── Logo + collapse toggle ─────────────────────────── */}
      <div className={`relative z-10 flex items-center py-5 flex-shrink-0
                       ${collapsed ? "justify-center px-0" : "px-4 gap-3"}`}>
        {/* Logo icon */}
        <div className="relative flex-shrink-0">
          <div className="absolute inset-0 rounded-xl blur-md opacity-60"
               style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }} />
          <div className="relative w-9 h-9 rounded-xl flex items-center justify-center"
               style={{ background: "linear-gradient(135deg, #6366f1 0%, #7c3aed 100%)", boxShadow: "0 0 20px rgba(99,102,241,0.4)" }}>
            <Brain size={16} className="text-white" />
          </div>
        </div>

        {/* Title — hidden when collapsed */}
        {!collapsed && (
          <div className="flex-1 min-w-0">
            <p className="text-white font-bold text-sm tracking-tight leading-tight">Agentic RAG</p>
            <p className="text-slate-600 text-[10px] leading-tight mt-0.5 flex items-center gap-1">
              <Sparkles size={8} className="text-indigo-500" />
              DS / ML Assistant
            </p>
          </div>
        )}

        {/* Collapse toggle */}
        {!collapsed && (
          <button onClick={() => setCollapsed(true)} title="Collapse sidebar"
            className="flex-shrink-0 p-1.5 rounded-lg text-slate-700 hover:text-slate-300 transition-all duration-150"
            onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.06)"}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
            <PanelLeftClose size={14} />
          </button>
        )}
      </div>

      {/* Expand button — only when collapsed */}
      {collapsed && (
        <div className="relative z-10 flex justify-center mb-2">
          <IconTooltip label="Expand sidebar">
            <button onClick={() => setCollapsed(false)}
              className="p-1.5 rounded-lg text-slate-700 hover:text-slate-300 transition-all duration-150"
              onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.06)"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
              <PanelLeftOpen size={14} />
            </button>
          </IconTooltip>
        </div>
      )}

      {/* ── New chat button ────────────────────────────────── */}
      <div className={`relative z-10 mb-3 ${collapsed ? "flex justify-center" : "px-3"}`}>
        {collapsed ? (
          <IconTooltip label="New conversation">
            <button onClick={handleNew}
              className="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-150"
              style={{ background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.2)" }}
              onMouseEnter={e => { e.currentTarget.style.background = "rgba(99,102,241,0.22)"; e.currentTarget.style.borderColor = "rgba(99,102,241,0.4)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "rgba(99,102,241,0.12)"; e.currentTarget.style.borderColor = "rgba(99,102,241,0.2)"; }}>
              <Plus size={15} className="text-indigo-400" />
            </button>
          </IconTooltip>
        ) : (
          <button onClick={handleNew}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium
                       text-slate-500 hover:text-slate-200 transition-all duration-200"
            style={{ border: "1px solid rgba(255,255,255,0.06)" }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(99,102,241,0.3)"; e.currentTarget.style.background = "rgba(99,102,241,0.07)"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)"; e.currentTarget.style.background = "transparent"; }}>
            <div className="w-5 h-5 rounded-lg flex items-center justify-center flex-shrink-0"
                 style={{ background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.2)" }}>
              <Plus size={11} className="text-indigo-400" />
            </div>
            New conversation
          </button>
        )}
      </div>

      {/* ── Top nav ───────────────────────────────────────── */}
      <nav className={`relative z-10 space-y-0.5 ${collapsed ? "px-2" : "px-3"}`}>
        {topNav.map(({ to, label, icon }) => (
          <NavItem key={to} to={to} label={label} icon={icon} />
        ))}
      </nav>

      {/* ── Divider ───────────────────────────────────────── */}
      {!collapsed && <div className="relative z-10 mx-4 my-3 divider" />}
      {collapsed  && <div className="my-3" />}

      {/* ── Recent sessions — hidden when collapsed ────────── */}
      {!collapsed && (
        <>
          <div className="relative z-10 px-5 pb-2">
            <p className="text-[9px] font-bold text-slate-700 uppercase tracking-[0.15em]">Recent</p>
          </div>
          <div className="relative z-10 flex-1 overflow-y-auto px-3 pb-3 space-y-0.5">
            {sessions.length === 0 && (
              <p className="text-xs text-slate-700 text-center mt-6">No conversations yet</p>
            )}
            {sessions.map((s) => (
              <button key={s.id} onClick={() => handleSelect(s.id)}
                className={`w-full text-left px-3 py-2.5 rounded-xl group flex items-start gap-2.5
                            transition-all duration-150 ${
                  sessionId === s.id ? "text-indigo-300" : "text-slate-600 hover:text-slate-300"
                }`}
                style={sessionId === s.id
                  ? { background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.15)" }
                  : { border: "1px solid transparent" }}
                onMouseEnter={e => { if (sessionId !== s.id) e.currentTarget.style.background = "rgba(255,255,255,0.03)"; }}
                onMouseLeave={e => { if (sessionId !== s.id) e.currentTarget.style.background = "transparent"; }}>
                <MessageSquare size={11} className="mt-0.5 flex-shrink-0 opacity-40" />
                <div className="flex-1 min-w-0">
                  <p className="text-[11px] font-medium truncate leading-snug">{s.title}</p>
                  <p className="text-[9px] text-slate-700 mt-0.5">
                    {s.message_count} msg · {new Date(s.updated_at).toLocaleDateString()}
                  </p>
                </div>
                <button onClick={(e) => handleDelete(s.id, e)}
                  className="opacity-0 group-hover:opacity-100 p-0.5 rounded-lg transition-all duration-150 flex-shrink-0 mt-0.5 text-slate-600 hover:text-red-400">
                  <Trash2 size={10} />
                </button>
              </button>
            ))}
          </div>
        </>
      )}

      {/* Spacer when collapsed (push bottom items down) */}
      {collapsed && <div className="flex-1" />}

      {/* ── Admin quick panel (only expanded + admin) ──────── */}
      {isAdmin && !collapsed && (
        <div className="relative z-10 mx-3 mb-3 rounded-xl overflow-hidden"
             style={{ background: "rgba(99,102,241,0.07)", border: "1px solid rgba(99,102,241,0.15)" }}>
          <div className="px-3 py-2 flex items-center gap-2"
               style={{ borderBottom: "1px solid rgba(99,102,241,0.1)" }}>
            <ShieldCheck size={11} className="text-indigo-400" />
            <span className="text-[9px] font-bold text-indigo-400 uppercase tracking-[0.12em]">Admin</span>
          </div>
          <div className="px-2 py-1.5 space-y-0.5">
            <NavLink to="/dashboard"
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-indigo-300 transition-colors duration-150">
              <Activity size={11} className="text-indigo-500" />
              Analytics
            </NavLink>
            <NavLink to="/documents"
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-indigo-300 transition-colors duration-150">
              <FileText size={11} className="text-indigo-500" />
              Knowledge base
            </NavLink>
            <NavLink to="/settings"
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs font-medium text-slate-500 hover:text-indigo-300 transition-colors duration-150">
              <Users size={11} className="text-indigo-500" />
              System settings
            </NavLink>
          </div>
        </div>
      )}

      {/* ── Bottom section: Settings + Avatar/logout ──────── */}
      <div className="relative z-10 flex-shrink-0" style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}>

        {/* Settings link */}
        <div className={`${collapsed ? "flex justify-center py-2" : "px-3 pt-2"}`}>
          {collapsed ? (
            <IconTooltip label="Settings">
              <NavLink to="/settings"
                className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200
                            ${location.pathname.startsWith("/settings") ? "nav-active" : "nav-inactive"}`}
                style={location.pathname.startsWith("/settings") ? { background: "rgba(99,102,241,0.18)", borderLeft: "none", outline: "1px solid rgba(99,102,241,0.3)" } : { borderLeft: "none" }}>
                <Settings size={15} className={location.pathname.startsWith("/settings") ? "text-indigo-400" : ""} />
              </NavLink>
            </IconTooltip>
          ) : (
            <NavLink to="/settings"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200
                 ${isActive ? "nav-active" : "nav-inactive"}`
              }>
              {({ isActive }) => (
                <>
                  <Settings size={15} className={isActive ? "text-indigo-400" : ""} />
                  <span className="flex-1">Settings</span>
                  {isActive && <ChevronRight size={12} className="text-indigo-400 opacity-60" />}
                </>
              )}
            </NavLink>
          )}
        </div>

        {/* User row */}
        <div className={`flex items-center py-3 ${collapsed ? "justify-center px-0" : "gap-2.5 px-4"}`}>
          {/* Avatar */}
          {collapsed ? (
            <IconTooltip label={user?.email ?? ""}>
              <NavLink to="/settings"
                className="relative group w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm"
                style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.3))", border: "1px solid rgba(99,102,241,0.3)", color: "#a5b4fc" }}>
                {avatarLetter}
              </NavLink>
            </IconTooltip>
          ) : (
            <>
              <NavLink to="/settings" className="relative flex-shrink-0 group">
                <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 blur-md transition-opacity duration-300"
                     style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }} />
                <div className="relative w-8 h-8 rounded-xl flex items-center justify-center font-bold text-sm"
                     style={{ background: "linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.3))", border: "1px solid rgba(99,102,241,0.3)", color: "#a5b4fc" }}>
                  {avatarLetter}
                </div>
              </NavLink>
              <div className="flex-1 min-w-0">
                <NavLink to="/settings"
                  className="block text-[11px] font-semibold text-slate-400 hover:text-indigo-300
                             truncate transition-colors duration-150 leading-tight">
                  {user?.email}
                </NavLink>
                <p className="text-[9px] leading-tight mt-0.5" style={{ color: "rgba(99,102,241,0.6)" }}>
                  {isAdmin ? "✦ Admin" : "User"}
                </p>
              </div>
              <button onClick={handleLogout} title="Sign out"
                className="p-1.5 rounded-lg transition-all duration-150 flex-shrink-0 text-slate-700 hover:text-red-400"
                style={{ border: "1px solid rgba(255,255,255,0.05)" }}
                onMouseEnter={e => e.currentTarget.style.background = "rgba(239,68,68,0.08)"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                <LogOut size={12} />
              </button>
            </>
          )}
        </div>

        {/* Logout icon only when collapsed */}
        {collapsed && (
          <div className="flex justify-center pb-3">
            <IconTooltip label="Sign out">
              <button onClick={handleLogout}
                className="w-9 h-9 rounded-xl flex items-center justify-center text-slate-700 hover:text-red-400 transition-all duration-150"
                onMouseEnter={e => e.currentTarget.style.background = "rgba(239,68,68,0.08)"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                <LogOut size={14} />
              </button>
            </IconTooltip>
          </div>
        )}
      </div>
    </aside>
  );
}

// ── App shell ─────────────────────────────────────────────────────────────────
function AppShell() {
  const { user } = useAuth();
  const isAdmin  = user?.role === "admin";
  const [collapsed, setCollapsed] = useState(false);

  return (
    <ChatProvider>
      <div className="flex h-screen overflow-hidden" style={{ background: "#08091a" }}>
        <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/"          element={<Navigate to="/chat" replace />} />
            <Route path="/chat"      element={<ChatPage />} />
            <Route path="/dashboard" element={isAdmin ? <AdminDashboard /> : <UserDashboard />} />
            <Route path="/history"   element={<HistoryPage />} />
            <Route path="/documents" element={isAdmin ? <DocumentsPage /> : <Navigate to="/dashboard" replace />} />
            <Route path="/profile"   element={<Navigate to="/settings" replace />} />
            <Route path="/settings"  element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </ChatProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ToastContainer />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*"     element={<ProtectedRoute><AppShell /></ProtectedRoute>} />
      </Routes>
    </AuthProvider>
  );
}

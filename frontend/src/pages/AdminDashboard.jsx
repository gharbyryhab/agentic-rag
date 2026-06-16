import { useCallback, useEffect, useState } from "react";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import {
  Users, Activity, Zap, ThumbsUp, Server,
  CheckCircle, XCircle, RefreshCw, Clock, TrendingUp, ShieldCheck,
} from "lucide-react";
import {
  getDashboard, getDailySessions, getFeedbackTrend, getTopQuestions,
  getAdminUsers, getSystemStatus, getHourlyQueries, getLatencyDaily,
} from "../api";
import { useToast } from "../context/ToastContext";

const RANGES = ["7d", "30d", "90d", "All"];
const RANGE_DAYS = { "7d": 7, "30d": 30, "90d": 90, "All": null };

// ── Shared primitives ─────────────────────────────────────────────────────────

const TOOLTIP = {
  contentStyle: {
    background: "#0f1022",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 12,
    fontSize: 12,
    color: "#e2e8f0",
    boxShadow: "0 8px 30px rgba(0,0,0,0.5)",
  },
  cursor: { fill: "rgba(99,102,241,0.06)" },
};

const STAT_COLORS = {
  indigo:  { grad: "stat-gradient-indigo",  icon: "rgba(99,102,241,0.2)",  iconColor: "#818cf8", border: "rgba(99,102,241,0.15)" },
  violet:  { grad: "stat-gradient-violet",  icon: "rgba(139,92,246,0.2)",  iconColor: "#c4b5fd", border: "rgba(139,92,246,0.15)" },
  emerald: { grad: "stat-gradient-emerald", icon: "rgba(16,185,129,0.2)",  iconColor: "#6ee7b7", border: "rgba(16,185,129,0.15)" },
  amber:   { grad: "stat-gradient-amber",   icon: "rgba(245,158,11,0.2)",  iconColor: "#fcd34d", border: "rgba(245,158,11,0.15)" },
  cyan:    { grad: "stat-gradient-cyan",    icon: "rgba(6,182,212,0.2)",   iconColor: "#67e8f9", border: "rgba(6,182,212,0.15)" },
};

function StatCard({ icon: Icon, label, value, sub, color = "indigo", trend }) {
  const c = STAT_COLORS[color];
  return (
    <div className={`relative overflow-hidden rounded-2xl p-5 flex items-center gap-4 ${c.grad}`}
         style={{ border: `1px solid ${c.border}`, backdropFilter: "blur(12px)" }}>
      <div className="relative flex-shrink-0">
        <div className="w-11 h-11 rounded-xl flex items-center justify-center"
             style={{ background: c.icon }}>
          <Icon size={18} style={{ color: c.iconColor }} />
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-1">
          <p className="text-2xl font-bold text-white tabular-nums leading-tight">{value ?? "—"}</p>
          {trend != null && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-lg flex-shrink-0 mt-1"
                  style={{
                    background: trend >= 0 ? "rgba(16,185,129,0.15)" : "rgba(239,68,68,0.15)",
                    color:      trend >= 0 ? "#6ee7b7" : "#fca5a5",
                  }}>
              {trend >= 0 ? "↑" : "↓"}{Math.abs(trend)}%
            </span>
          )}
        </div>
        <p className="text-xs text-slate-400 mt-0.5">{label}</p>
        {sub && <p className="text-[10px] mt-0.5" style={{ color: c.iconColor }}>{sub}</p>}
      </div>
    </div>
  );
}

function Panel({ title, children, action }) {
  return (
    <div className="rounded-2xl overflow-hidden"
         style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="px-5 py-4 flex items-center justify-between"
           style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <h3 className="text-sm font-semibold text-slate-300">{title}</h3>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const [range, setRange]               = useState("30d");
  const [stats, setStats]               = useState(null);
  const [dailySessions, setDailySessions] = useState([]);
  const [feedbackTrend, setFeedbackTrend] = useState([]);
  const [topQuestions, setTopQuestions] = useState([]);
  const [hourlyQueries, setHourlyQueries] = useState([]);
  const [latencyDaily, setLatencyDaily] = useState([]);
  const [users, setUsers]               = useState([]);
  const [sysStatus, setSysStatus]       = useState(null);
  const [loading, setLoading]           = useState(true);
  const [refreshing, setRefreshing]     = useState(false);
  const { addToast } = useToast();

  const days = RANGE_DAYS[range];

  const loadData = useCallback(async (d, { silent = false } = {}) => {
    if (!silent) setLoading(true);
    setRefreshing(true);
    try {
      const [s, ds, ft, tq, hq, ld, us, sys] = await Promise.all([
        getDashboard(d),
        getDailySessions(d),
        getFeedbackTrend(d),
        getTopQuestions(d, 10),
        getHourlyQueries(d ?? 7),
        getLatencyDaily(d ?? 30),
        getAdminUsers(),
        getSystemStatus(),
      ]);
      setStats(s); setDailySessions(ds); setFeedbackTrend(ft);
      setTopQuestions(tq); setHourlyQueries(hq); setLatencyDaily(ld);
      setUsers(us); setSysStatus(sys);
    } catch (err) {
      addToast(err.response?.data?.detail || "Failed to load dashboard", "error");
    } finally {
      setLoading(false); setRefreshing(false);
    }
  }, [addToast]);

  useEffect(() => { loadData(days); }, [range]);

  const totalFeedback  = (stats?.thumbs_up ?? 0) + (stats?.thumbs_down ?? 0);
  const satisfactionRate = totalFeedback > 0
    ? Math.round((stats.thumbs_up / totalFeedback) * 100) : null;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center animate-glow-pulse"
             style={{ background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)" }}>
          <RefreshCw size={18} className="text-indigo-400 animate-spin" />
        </div>
        <span className="text-sm text-slate-500">Loading admin dashboard…</span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto" style={{ background: "#08091a" }}>
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ShieldCheck size={14} className="text-indigo-400" />
              <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-[0.15em]">Admin</span>
            </div>
            <h1 className="text-xl font-bold text-white">Dashboard</h1>
            <p className="text-sm text-slate-600 mt-0.5">System-wide analytics &amp; controls</p>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Range pills */}
            <div className="flex rounded-xl p-1 gap-0.5"
                 style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
              {RANGES.map((r) => (
                <button key={r} onClick={() => setRange(r)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150"
                  style={range === r
                    ? { background: "linear-gradient(135deg,#6366f1,#7c3aed)", color: "#fff", boxShadow: "0 2px 10px rgba(99,102,241,0.4)" }
                    : { color: "#64748b" }
                  }>
                  {r}
                </button>
              ))}
            </div>
            {/* Refresh */}
            <button onClick={() => loadData(days, { silent: true })} disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium
                         transition-all duration-150 disabled:opacity-50 text-slate-500 hover:text-slate-200"
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}
              onMouseEnter={e => e.currentTarget.style.borderColor = "rgba(99,102,241,0.3)"}
              onMouseLeave={e => e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)"}
            >
              <RefreshCw size={11} className={refreshing ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        </div>

        {/* System status banner */}
        {sysStatus && (
          <div className="rounded-2xl px-5 py-4 flex items-center gap-4"
               style={{
                 background: sysStatus.pipeline_healthy ? "rgba(16,185,129,0.07)" : "rgba(239,68,68,0.07)",
                 border: `1px solid ${sysStatus.pipeline_healthy ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}`,
               }}>
            {sysStatus.pipeline_healthy
              ? <CheckCircle size={16} className="text-emerald-400 flex-shrink-0" />
              : <XCircle    size={16} className="text-red-400 flex-shrink-0" />
            }
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold" style={{ color: sysStatus.pipeline_healthy ? "#6ee7b7" : "#fca5a5" }}>
                Pipeline {sysStatus.pipeline_healthy ? "healthy" : "unavailable"}
              </p>
              <p className="text-xs text-slate-600 mt-0.5">
                Model: <span className="font-mono text-slate-500">{sysStatus.model_name}</span>
                &nbsp;·&nbsp; ChromaDB: <span className="text-slate-500">{sysStatus.chromadb_size} docs</span>
                &nbsp;·&nbsp; Uptime: <span className="text-slate-500">{sysStatus.uptime_s != null ? `${Math.floor(sysStatus.uptime_s / 60)}m ${Math.round(sysStatus.uptime_s % 60)}s` : "—"}</span>
              </p>
            </div>
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${sysStatus.pipeline_healthy ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
          </div>
        )}

        {/* KPI row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={Activity}  label="Total questions"   value={stats?.total_questions}   color="indigo" />
          <StatCard icon={Users}     label="Registered users"  value={users.length}             color="violet" />
          <StatCard icon={ThumbsUp}
            label="Satisfaction"
            value={satisfactionRate != null ? `${satisfactionRate}%` : "—"}
            sub={`${stats?.thumbs_up ?? 0} up · ${stats?.thumbs_down ?? 0} down`}
            color="emerald"
          />
          <StatCard icon={Clock}
            label="Latency P50 / P95"
            value={stats?.latency_p50 != null ? `${stats.latency_p50}s` : "—"}
            sub={stats?.latency_p95 != null ? `P95: ${stats.latency_p95}s` : undefined}
            color="amber"
          />
        </div>

        {/* Charts row 1 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Panel title={`Queries / hour (last ${range})`}>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={hourlyQueries} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                <defs>
                  <linearGradient id="gCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="hour" tick={{ fontSize: 9, fill: "#475569" }} tickFormatter={(h) => h.slice(11)} />
                <YAxis tick={{ fontSize: 9, fill: "#475569" }} allowDecimals={false} />
                <Tooltip {...TOOLTIP} labelFormatter={(l) => `Hour: ${l}`} />
                <Area type="monotone" dataKey="count" stroke="#6366f1" fill="url(#gCount)" strokeWidth={2} dot={false} name="Queries" />
              </AreaChart>
            </ResponsiveContainer>
          </Panel>

          <Panel title="Latency P50 / P95 by day">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={latencyDaily} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#475569" }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 9, fill: "#475569" }} unit="s" />
                <Tooltip {...TOOLTIP} formatter={(v) => [`${v}s`]} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
                <Line type="monotone" dataKey="p50" stroke="#6366f1" strokeWidth={2} dot={false} name="P50" />
                <Line type="monotone" dataKey="p95" stroke="#f59e0b" strokeWidth={2} dot={false} name="P95" strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          </Panel>
        </div>

        {/* Charts row 2 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Panel title="Daily sessions & questions">
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={dailySessions} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#475569" }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 9, fill: "#475569" }} allowDecimals={false} />
                <Tooltip {...TOOLTIP} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#64748b" }} />
                <Bar dataKey="sessions"  fill="#6366f1" radius={[3,3,0,0]} name="Sessions" />
                <Bar dataKey="questions" fill="#8b5cf6" radius={[3,3,0,0]} name="Questions" />
              </BarChart>
            </ResponsiveContainer>
          </Panel>

          <Panel title="Satisfaction rate over time (%)">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={feedbackTrend} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                <defs>
                  <linearGradient id="gSat" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#475569" }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fontSize: 9, fill: "#475569" }} domain={[0,1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
                <Tooltip {...TOOLTIP} formatter={(v) => [`${Math.round(v * 100)}%`, "Rate"]} />
                <Line type="monotone" dataKey="rate" stroke="#10b981" strokeWidth={2} dot={false} name="Satisfaction" />
              </LineChart>
            </ResponsiveContainer>
          </Panel>
        </div>

        {/* Top questions */}
        <Panel title="Top questions by frequency">
          {topQuestions.length === 0 ? (
            <p className="text-sm text-slate-600 text-center py-4">No data yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                    {["#", "Question", "Count", "Avg latency"].map((h, i) => (
                      <th key={h} className={`pb-3 text-[10px] font-bold text-slate-600 uppercase tracking-[0.1em] ${i > 1 ? "text-right" : "text-left"} ${i > 0 ? "pr-0" : "pr-4"}`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {topQuestions.map((q, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                        className="hover:bg-white/[0.02] transition-colors duration-100">
                      <td className="py-3 pr-4 text-xs text-slate-700 tabular-nums w-8">{i + 1}</td>
                      <td className="py-3 pr-4 text-xs text-slate-400 max-w-xs truncate">{q.question}</td>
                      <td className="py-3 pr-4 text-right">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold tabular-nums"
                              style={{ background: "rgba(99,102,241,0.15)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.2)" }}>
                          {q.count}
                        </span>
                      </td>
                      <td className="py-3 text-right text-xs text-slate-600 tabular-nums">
                        {q.avg_latency != null ? `${q.avg_latency}s` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        {/* User activity */}
        <Panel title="User activity" action={
          <span className="text-[10px] text-slate-700 tabular-nums">{users.length} user{users.length !== 1 ? "s" : ""}</span>
        }>
          {users.length === 0 ? (
            <p className="text-sm text-slate-600 text-center py-4">No users yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                    {["User", "Role", "Sessions", "Questions", "Last active"].map((h, i) => (
                      <th key={h} className={`pb-3 text-[10px] font-bold text-slate-600 uppercase tracking-[0.1em] ${i >= 2 && i < 4 ? "text-right" : "text-left"} pr-4`}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    const initial = u.email?.[0]?.toUpperCase() ?? "?";
                    const avatarColors = [
                      ["rgba(99,102,241,0.25)","#818cf8"],
                      ["rgba(139,92,246,0.25)","#c4b5fd"],
                      ["rgba(6,182,212,0.25)","#67e8f9"],
                      ["rgba(16,185,129,0.25)","#6ee7b7"],
                      ["rgba(245,158,11,0.25)","#fcd34d"],
                    ];
                    const [bg, color] = avatarColors[u.id % avatarColors.length] ?? avatarColors[0];
                    return (
                      <tr key={u.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}
                          className="hover:bg-white/[0.02] transition-colors duration-100">
                        <td className="py-2.5 pr-4">
                          <div className="flex items-center gap-2.5">
                            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-bold"
                                 style={{ background: bg, color }}>
                              {initial}
                            </div>
                            <span className="text-xs text-slate-300 font-medium truncate max-w-[160px]">{u.email}</span>
                          </div>
                        </td>
                        <td className="py-2.5 pr-4">
                          <span className={u.role === "admin" ? "badge-indigo" : "badge-slate"}>{u.role}</span>
                        </td>
                        <td className="py-2.5 pr-4 text-right text-xs text-slate-500 tabular-nums">{u.total_sessions}</td>
                        <td className="py-2.5 pr-4 text-right text-xs text-slate-500 tabular-nums">{u.total_questions}</td>
                        <td className="py-2.5 text-xs text-slate-600">
                          {u.last_active ? new Date(u.last_active).toLocaleDateString() : "Never"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <div className="h-4" />
      </div>
    </div>
  );
}

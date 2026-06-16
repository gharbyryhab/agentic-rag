import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart,
} from "recharts";
import { MessageSquare, HelpCircle, Clock, ThumbsUp, RefreshCw, Sparkles, TrendingUp, ArrowRight } from "lucide-react";
import { getMyDashboard } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

const RANGES = ["7d", "30d", "All"];
const RANGE_DAYS = { "7d": 7, "30d": 30, "All": null };

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
};

function StatCard({ icon: Icon, label, value, sub, color = "indigo" }) {
  const c = STAT_COLORS[color];
  return (
    <div className={`relative overflow-hidden rounded-2xl p-5 flex items-center gap-4 ${c.grad}`}
         style={{ border: `1px solid ${c.border}`, backdropFilter: "blur(12px)" }}>
      <div className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
           style={{ background: c.icon }}>
        <Icon size={18} style={{ color: c.iconColor }} />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-bold text-white tabular-nums leading-tight">{value ?? "—"}</p>
        <p className="text-xs text-slate-400 mt-0.5">{label}</p>
        {sub && <p className="text-[10px] mt-0.5" style={{ color: c.iconColor }}>{sub}</p>}
      </div>
    </div>
  );
}

export default function UserDashboard() {
  const { user } = useAuth();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [range, setRange] = useState("30d");
  const [data, setData]   = useState(null);
  const [loading, setLoading] = useState(true);

  const days = RANGE_DAYS[range];

  const loadData = useCallback(async (d) => {
    setLoading(true);
    try {
      setData(await getMyDashboard(d));
    } catch (err) {
      addToast(err.response?.data?.detail || "Failed to load dashboard", "error");
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => { loadData(days); }, [range]);

  const totalFeedback    = (data?.thumbs_up ?? 0) + (data?.thumbs_down ?? 0);
  const satisfactionRate = totalFeedback > 0
    ? Math.round((data.thumbs_up / totalFeedback) * 100) : null;

  const isEmpty = (data?.total_questions ?? 0) === 0;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center animate-glow-pulse"
             style={{ background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)" }}>
          <RefreshCw size={18} className="text-indigo-400 animate-spin" />
        </div>
        <span className="text-sm text-slate-500">Loading your activity…</span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto" style={{ background: "#08091a" }}>
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            {/* Avatar */}
            <div className="relative flex-shrink-0">
              <div className="absolute inset-0 rounded-2xl blur-lg opacity-40"
                   style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }} />
              <div className="relative w-14 h-14 rounded-2xl flex items-center justify-center font-black text-xl"
                   style={{ background: "linear-gradient(135deg,rgba(99,102,241,0.35),rgba(139,92,246,0.35))", border: "1px solid rgba(99,102,241,0.35)", color: "#c4b5fd" }}>
                {user?.email?.[0]?.toUpperCase() ?? "U"}
              </div>
            </div>
            <div>
              <p className="text-[10px] font-bold text-indigo-400 uppercase tracking-[0.15em] flex items-center gap-1.5">
                <Sparkles size={9} /> My Activity
              </p>
              <h1 className="text-xl font-bold text-white mt-0.5">
                {getGreeting()}{user?.email ? `, ${user.email.split("@")[0]}` : ""}!
              </h1>
              <p className="text-xs text-slate-600 mt-0.5">{user?.email}</p>
            </div>
          </div>

          {/* Range pills */}
          <div className="flex rounded-xl p-1 gap-0.5 flex-shrink-0"
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
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard icon={MessageSquare} label="Conversations"  value={data?.total_sessions ?? 0}  color="indigo" />
          <StatCard icon={HelpCircle}    label="Questions asked" value={data?.total_questions ?? 0} color="violet" />
          <StatCard icon={ThumbsUp}
            label="Satisfaction"
            value={satisfactionRate != null ? `${satisfactionRate}%` : "—"}
            sub={`${data?.thumbs_up ?? 0} 👍 · ${data?.thumbs_down ?? 0} 👎`}
            color="emerald"
          />
          <StatCard icon={Clock}
            label="Avg latency"
            value={data?.avg_latency_s != null ? `${data.avg_latency_s}s` : "—"}
            sub={data?.latency_p50 != null ? `P50: ${data.latency_p50}s` : undefined}
            color="amber"
          />
        </div>

        {/* Empty state */}
        {isEmpty ? (
          <div className="rounded-2xl p-14 text-center flex flex-col items-center gap-5 relative overflow-hidden"
               style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
            <div className="absolute inset-0 pointer-events-none"
                 style={{ background: "radial-gradient(ellipse at center top,rgba(99,102,241,0.06) 0%,transparent 65%)" }} />
            <div className="relative">
              <div className="absolute inset-0 rounded-3xl blur-xl opacity-40"
                   style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }} />
              <div className="relative w-16 h-16 rounded-3xl flex items-center justify-center"
                   style={{ background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)" }}>
                <MessageSquare size={26} className="text-indigo-500" />
              </div>
            </div>
            <div>
              <p className="text-white font-bold text-lg">No activity yet</p>
              <p className="text-sm text-slate-600 mt-1.5 max-w-xs">Ask your first DS &amp; ML question to start building your stats</p>
            </div>
            <button onClick={() => navigate("/chat")}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-200"
              style={{ background: "linear-gradient(135deg,#6366f1,#7c3aed)", boxShadow: "0 4px 20px rgba(99,102,241,0.35)" }}
              onMouseEnter={e => e.currentTarget.style.boxShadow = "0 6px 28px rgba(99,102,241,0.5)"}
              onMouseLeave={e => e.currentTarget.style.boxShadow = "0 4px 20px rgba(99,102,241,0.35)"}>
              Start a conversation
              <ArrowRight size={14} />
            </button>
          </div>
        ) : (
          /* Daily chart */
          <div className="rounded-2xl overflow-hidden"
               style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
            <div className="px-5 py-4 flex items-center gap-2"
                 style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <TrendingUp size={13} className="text-indigo-400" />
              <h3 className="text-sm font-semibold text-slate-300">Questions over time</h3>
            </div>
            <div className="p-5">
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={data?.daily ?? []} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gQ" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.35} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#475569" }} tickFormatter={(d) => d.slice(5)} />
                  <YAxis tick={{ fontSize: 9, fill: "#475569" }} allowDecimals={false} />
                  <Tooltip {...TOOLTIP} />
                  <Area type="monotone" dataKey="questions" stroke="#6366f1" fill="url(#gQ)" strokeWidth={2} dot={false} name="Questions" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        <div className="h-4" />
      </div>
    </div>
  );
}

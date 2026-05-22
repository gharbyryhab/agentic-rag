import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import {
  MessageSquare, Clock, ThumbsUp, Database, RefreshCw,
  Zap, TrendingUp, AlertCircle, Upload,
} from "lucide-react";
import { getDashboard, getEvalRuns, getLogs, importEvalRun } from "../api";

const RAGAS_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"];

const METRIC_COLORS = {
  faithfulness: "#4f46e5",
  "answer relevancy": "#7c3aed",
  "context precision": "#059669",
  "context recall": "#d97706",
};

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [evalRuns, setEvalRuns] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [importTag, setImportTag] = useState("");
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, e, l] = await Promise.all([getDashboard(), getEvalRuns(), getLogs(50)]);
      setStats(s);
      setEvalRuns(e);
      setLogs(l.reverse());
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Could not reach backend");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleImport = async () => {
    if (!importTag.trim()) return;
    setImporting(true);
    setImportError(null);
    try {
      await importEvalRun(importTag.trim());
      await load();
      setImportTag("");
    } catch (err) {
      setImportError(err.response?.data?.detail || err.message || "Import failed");
    } finally {
      setImporting(false);
    }
  };

  // Chart data
  const evalChartData = evalRuns.slice(0, 8).reverse().map((r) => ({
    tag: r.tag.slice(0, 18),
    ...Object.fromEntries(
      RAGAS_METRICS.map((m) => [
        m.replace(/_/g, " "),
        r.metrics[m] != null ? +r.metrics[m].toFixed(3) : null,
      ])
    ),
  }));

  const latencyData = logs
    .filter((l) => l.latency_s != null)
    .slice(-30)
    .map((l, i) => ({ i: i + 1, latency: l.latency_s, route: l.route }));

  const satisfaction =
    stats && stats.thumbs_up + stats.thumbs_down > 0
      ? Math.round((stats.thumbs_up / (stats.thumbs_up + stats.thumbs_down)) * 100)
      : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full gap-3 text-slate-400">
        <RefreshCw size={18} className="animate-spin" />
        <span className="text-sm">Loading dashboard…</span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-slate-50">
      <div className="max-w-6xl mx-auto px-8 py-6 space-y-6">

        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Dashboard</h1>
            <p className="text-sm text-slate-500 mt-0.5">Live metrics and evaluation results</p>
          </div>
          <button
            onClick={load}
            className="btn-ghost flex items-center gap-2 text-sm"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-xl px-4 py-3 text-sm text-red-600">
            <AlertCircle size={15} className="flex-shrink-0" />
            {error}
          </div>
        )}

        {/* KPI cards */}
        {stats && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard
              icon={<MessageSquare size={18} />}
              iconBg="bg-indigo-100 text-indigo-600"
              label="Total sessions"
              value={stats.total_sessions}
            />
            <KpiCard
              icon={<Database size={18} />}
              iconBg="bg-violet-100 text-violet-600"
              label="Questions asked"
              value={stats.total_questions}
            />
            <KpiCard
              icon={<Clock size={18} />}
              iconBg="bg-amber-100 text-amber-600"
              label="Avg latency"
              value={stats.avg_latency_s != null ? `${stats.avg_latency_s}s` : "—"}
            />
            <KpiCard
              icon={<ThumbsUp size={18} />}
              iconBg="bg-emerald-100 text-emerald-600"
              label="Satisfaction"
              value={satisfaction != null ? `${satisfaction}%` : "—"}
              sub={stats.thumbs_up + stats.thumbs_down > 0
                ? `${stats.thumbs_up} helpful · ${stats.thumbs_down} not`
                : "No feedback yet"}
            />
          </div>
        )}

        {/* Route distribution + last eval */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {stats && Object.keys(stats.route_distribution).length > 0 && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-1">Route distribution</h2>
              <p className="text-xs text-slate-400 mb-4">How queries are being routed</p>
              <ResponsiveContainer width="100%" height={160}>
                <BarChart
                  data={Object.entries(stats.route_distribution).map(([r, c]) => ({
                    route: r.replace("_", " "),
                    count: c,
                  }))}
                  barSize={32}
                >
                  <XAxis dataKey="route" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ borderRadius: "10px", border: "1px solid #e2e8f0", fontSize: 12 }}
                    cursor={{ fill: "#f1f5f9" }}
                  />
                  <Bar dataKey="count" fill="#4f46e5" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {stats?.last_eval && (
            <div className="card p-5">
              <h2 className="text-sm font-semibold text-slate-700 mb-0.5">Last evaluation</h2>
              <p className="text-xs text-slate-400 mb-4 font-mono">{stats.last_eval.tag}</p>
              <div className="grid grid-cols-2 gap-3">
                {RAGAS_METRICS.map((m) => {
                  const val = stats.last_eval.metrics[m];
                  return (
                    <div key={m} className="bg-slate-50 rounded-xl px-3.5 py-3">
                      <p className="text-[11px] text-slate-500 capitalize font-medium">
                        {m.replace(/_/g, " ")}
                      </p>
                      <p className={`text-2xl font-bold mt-0.5 tabular-nums ${
                        val == null ? "text-slate-300"
                          : val >= 0.7 ? "text-emerald-600"
                          : val >= 0.5 ? "text-amber-500"
                          : "text-red-500"
                      }`}>
                        {val != null ? val.toFixed(2) : "—"}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Ragas metrics over time */}
        {evalChartData.length > 1 && (
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp size={15} className="text-indigo-500" />
              <h2 className="text-sm font-semibold text-slate-700">Ragas metrics over runs</h2>
            </div>
            <p className="text-xs text-slate-400 mb-4">Evaluation quality trend across experiments</p>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={evalChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="tag" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ borderRadius: "10px", border: "1px solid #e2e8f0", fontSize: 12 }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {Object.entries(METRIC_COLORS).map(([key, color]) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={color}
                    dot={false}
                    strokeWidth={2}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Latency timeline */}
        {latencyData.length > 2 && (
          <div className="card p-5">
            <div className="flex items-center gap-2 mb-1">
              <Zap size={15} className="text-amber-500" />
              <h2 className="text-sm font-semibold text-slate-700">Response latency</h2>
            </div>
            <p className="text-xs text-slate-400 mb-4">Last {latencyData.length} requests</p>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={latencyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="i" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                <YAxis unit="s" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                <Tooltip
                  formatter={(v) => [`${v}s`, "latency"]}
                  contentStyle={{ borderRadius: "10px", border: "1px solid #e2e8f0", fontSize: 12 }}
                />
                <Line type="monotone" dataKey="latency" stroke="#f59e0b" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Import eval run */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-1">
            <Upload size={14} className="text-slate-500" />
            <h2 className="text-sm font-semibold text-slate-700">Import evaluation run</h2>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            After running{" "}
            <code className="bg-slate-100 text-slate-700 px-1.5 py-0.5 rounded-md font-mono text-[11px]">
              python -m tools.eval.run_ragas --tag my_tag
            </code>
            , import the results here.
          </p>
          {importError && (
            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-xl px-3 py-2 mb-3">
              <AlertCircle size={13} />
              {importError}
            </div>
          )}
          <div className="flex gap-3">
            <input
              className="input flex-1 text-sm"
              placeholder="Tag name — e.g. fix_complet_v1"
              value={importTag}
              onChange={(e) => setImportTag(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleImport()}
            />
            <button
              onClick={handleImport}
              disabled={importing || !importTag.trim()}
              className="btn-primary text-sm"
            >
              {importing ? "Importing…" : "Import"}
            </button>
          </div>
        </div>

        {/* Eval runs table */}
        {evalRuns.length > 0 && (
          <div className="card overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-700">All evaluation runs</h2>
              <span className="text-xs text-slate-400">{evalRuns.length} run{evalRuns.length !== 1 ? "s" : ""}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-50 text-slate-500">
                    <th className="px-5 py-3 text-left font-semibold">Tag</th>
                    <th className="px-5 py-3 text-left font-semibold">Chunking</th>
                    <th className="px-5 py-3 text-right font-semibold">Faithfulness</th>
                    <th className="px-5 py-3 text-right font-semibold">Ans. Rel.</th>
                    <th className="px-5 py-3 text-right font-semibold">Ctx. Prec.</th>
                    <th className="px-5 py-3 text-right font-semibold">Ctx. Rec.</th>
                    <th className="px-5 py-3 text-left font-semibold">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {evalRuns.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50/80 transition-colors duration-100">
                      <td className="px-5 py-3 font-mono text-slate-700 max-w-[200px] truncate">
                        {r.tag}
                      </td>
                      <td className="px-5 py-3 text-slate-500">{r.chunking_strategy || "—"}</td>
                      {RAGAS_METRICS.map((m) => (
                        <td key={m} className="px-5 py-3 text-right tabular-nums">
                          <MetricCell val={r.metrics[m]} />
                        </td>
                      ))}
                      <td className="px-5 py-3 text-slate-400">
                        {new Date(r.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function KpiCard({ icon, iconBg, label, value, sub }) {
  return (
    <div className="card p-5 flex items-start gap-4">
      <div className={`p-2.5 rounded-xl ${iconBg} flex-shrink-0`}>{icon}</div>
      <div className="min-w-0">
        <p className="text-xs text-slate-500 font-medium">{label}</p>
        <p className="text-2xl font-bold text-slate-900 mt-0.5 tabular-nums leading-tight">{value}</p>
        {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function MetricCell({ val }) {
  if (val == null) return <span className="text-slate-300">—</span>;
  const color =
    val >= 0.7 ? "text-emerald-600" : val >= 0.5 ? "text-amber-500" : "text-red-500";
  return <span className={`font-mono ${color}`}>{val.toFixed(3)}</span>;
}

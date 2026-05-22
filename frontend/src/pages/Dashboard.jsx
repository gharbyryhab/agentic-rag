import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from "recharts";
import { MessageSquare, Clock, ThumbsUp, ThumbsDown, Zap, Database, RefreshCw } from "lucide-react";
import { getDashboard, getEvalRuns, getLogs, importEvalRun } from "../api";

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [evalRuns, setEvalRuns] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [importTag, setImportTag] = useState("");
  const [importing, setImporting] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [s, e, l] = await Promise.all([getDashboard(), getEvalRuns(), getLogs(50)]);
      setStats(s);
      setEvalRuns(e);
      setLogs(l.reverse()); // chronological
    } catch {
      // backend might not be ready
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleImport = async () => {
    if (!importTag.trim()) return;
    setImporting(true);
    try {
      await importEvalRun(importTag.trim());
      await load();
      setImportTag("");
    } catch (e) {
      alert("Import failed: " + (e.response?.data?.detail || e.message));
    } finally {
      setImporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        Loading dashboard…
      </div>
    );
  }

  // Ragas metrics for chart
  const ragas_metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"];
  const evalChartData = evalRuns.slice(0, 8).reverse().map((r) => ({
    tag: r.tag.slice(0, 20),
    ...Object.fromEntries(
      ragas_metrics.map((m) => [m.replace("_", " "), r.metrics[m] != null ? +r.metrics[m].toFixed(3) : null])
    ),
  }));

  // Latency timeline
  const latencyData = logs
    .filter((l) => l.latency_s != null)
    .slice(-30)
    .map((l, i) => ({ i: i + 1, latency: l.latency_s, route: l.route }));

  return (
    <div className="h-full overflow-y-auto px-8 py-6 space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-800">Dashboard</h1>
        <button onClick={load} className="btn-ghost flex items-center gap-2 text-sm">
          <RefreshCw size={15} /> Refresh
        </button>
      </div>

      {/* KPI Cards */}
      {stats && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard icon={<MessageSquare size={18} className="text-blue-500" />} label="Total sessions" value={stats.total_sessions} />
          <KpiCard icon={<Database size={18} className="text-indigo-500" />} label="Questions asked" value={stats.total_questions} />
          <KpiCard icon={<Clock size={18} className="text-amber-500" />} label="Avg latency" value={stats.avg_latency_s != null ? `${stats.avg_latency_s}s` : "—"} />
          <KpiCard
            icon={<ThumbsUp size={18} className="text-green-500" />}
            label="Satisfaction"
            value={
              stats.thumbs_up + stats.thumbs_down > 0
                ? `${Math.round((stats.thumbs_up / (stats.thumbs_up + stats.thumbs_down)) * 100)}%`
                : "—"
            }
            sub={`${stats.thumbs_up} 👍 · ${stats.thumbs_down} 👎`}
          />
        </div>
      )}

      {/* Route distribution + last eval */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Route bar chart */}
        {stats && Object.keys(stats.route_distribution).length > 0 && (
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">Route distribution</h2>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={Object.entries(stats.route_distribution).map(([r, c]) => ({ route: r, count: c }))}>
                <XAxis dataKey="route" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Last eval metrics */}
        {stats?.last_eval && (
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-slate-700 mb-1">Last evaluation</h2>
            <p className="text-xs text-slate-400 mb-4">{stats.last_eval.tag}</p>
            <div className="grid grid-cols-2 gap-3">
              {ragas_metrics.map((m) => {
                const val = stats.last_eval.metrics[m];
                return (
                  <div key={m} className="bg-slate-50 rounded-lg px-3 py-2.5">
                    <p className="text-xs text-slate-500 capitalize">{m.replace(/_/g, " ")}</p>
                    <p className={`text-lg font-bold mt-0.5 ${val == null ? "text-slate-300" : val >= 0.7 ? "text-green-600" : val >= 0.5 ? "text-amber-500" : "text-red-500"}`}>
                      {val != null ? val.toFixed(3) : "—"}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Eval runs history chart */}
      {evalChartData.length > 1 && (
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Ragas metrics over runs</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={evalChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="tag" tick={{ fontSize: 10 }} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="faithfulness" stroke="#2563eb" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="answer relevancy" stroke="#7c3aed" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="context precision" stroke="#059669" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="context recall" stroke="#d97706" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Latency timeline */}
      {latencyData.length > 2 && (
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Response latency (last 30 requests)</h2>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={latencyData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="i" tick={{ fontSize: 10 }} />
              <YAxis unit="s" tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => `${v}s`} />
              <Line type="monotone" dataKey="latency" stroke="#f59e0b" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Import eval run */}
      <div className="card p-5">
        <h2 className="text-sm font-semibold text-slate-700 mb-3">Import Ragas run</h2>
        <p className="text-xs text-slate-400 mb-3">
          After running <code className="bg-slate-100 px-1 rounded">python -m tools.eval.run_ragas --tag my_tag</code>, import the results here.
        </p>
        <div className="flex gap-3">
          <input
            className="input flex-1 text-sm"
            placeholder="e.g. fix_complet_v1 or full tag name"
            value={importTag}
            onChange={(e) => setImportTag(e.target.value)}
          />
          <button onClick={handleImport} disabled={importing || !importTag.trim()} className="btn-primary text-sm">
            {importing ? "Importing…" : "Import"}
          </button>
        </div>
      </div>

      {/* All eval runs table */}
      {evalRuns.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-700">All evaluation runs</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 text-slate-500 uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium">Tag</th>
                  <th className="px-4 py-2.5 text-left font-medium">Chunking</th>
                  <th className="px-4 py-2.5 text-right font-medium">Faithfulness</th>
                  <th className="px-4 py-2.5 text-right font-medium">Ans. Rel.</th>
                  <th className="px-4 py-2.5 text-right font-medium">Ctx. Prec.</th>
                  <th className="px-4 py-2.5 text-right font-medium">Ctx. Rec.</th>
                  <th className="px-4 py-2.5 text-left font-medium">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {evalRuns.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 font-mono text-slate-700 max-w-[180px] truncate">{r.tag}</td>
                    <td className="px-4 py-2.5 text-slate-500">{r.chunking_strategy || "—"}</td>
                    {ragas_metrics.map((m) => (
                      <td key={m} className="px-4 py-2.5 text-right font-mono">
                        <MetricCell val={r.metrics[m]} />
                      </td>
                    ))}
                    <td className="px-4 py-2.5 text-slate-400">
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
  );
}

function KpiCard({ icon, label, value, sub }) {
  return (
    <div className="card p-4 flex items-start gap-3">
      <div className="p-2 bg-slate-50 rounded-lg">{icon}</div>
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-2xl font-bold text-slate-800 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function MetricCell({ val }) {
  if (val == null) return <span className="text-slate-300">—</span>;
  const color = val >= 0.7 ? "text-green-600" : val >= 0.5 ? "text-amber-500" : "text-red-500";
  return <span className={color}>{val.toFixed(3)}</span>;
}

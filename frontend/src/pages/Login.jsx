import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Brain, Eye, EyeOff, Loader2, ArrowRight,
  Sparkles, ShieldCheck, Zap, BookOpen,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

const FEATURES = [
  { icon: Brain,       color: "#818cf8", label: "Gemma-4 LLM",      desc: "State-of-the-art reasoning" },
  { icon: BookOpen,    color: "#6ee7b7", label: "RAG Pipeline",      desc: "Grounded on your corpus"   },
  { icon: Zap,         color: "#fcd34d", label: "Streaming answers", desc: "Real-time token streaming" },
  { icon: ShieldCheck, color: "#f9a8d4", label: "Role-based access", desc: "Admin & user separation"   },
];

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode]       = useState("login");
  const [email, setEmail]     = useState("");
  const [password, setPass]   = useState("");
  const [showPw, setShowPw]   = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      navigate("/chat", { replace: true });
    } catch (err) {
      const d = err.response?.data?.detail || err.message || "Authentication failed";
      setError(Array.isArray(d) ? d[0]?.msg || "Invalid input" : d);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-stretch overflow-hidden" style={{ background: "#08091a" }}>

      {/* ── Left branding panel ─────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-[45%] flex-col justify-between p-12 relative overflow-hidden"
           style={{ background: "linear-gradient(160deg,#0d0e28 0%,#090a1c 100%)", borderRight: "1px solid rgba(255,255,255,0.06)" }}>

        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-[-15%] left-[-10%] w-[500px] h-[500px] rounded-full animate-orb"
               style={{ background: "radial-gradient(circle,rgba(99,102,241,0.15) 0%,transparent 65%)", filter: "blur(50px)" }} />
          <div className="absolute bottom-[-10%] right-[-5%] w-[400px] h-[400px] rounded-full animate-orb2"
               style={{ background: "radial-gradient(circle,rgba(139,92,246,0.12) 0%,transparent 65%)", filter: "blur(60px)" }} />
          <div className="absolute inset-0 opacity-[0.025]"
               style={{ backgroundImage: "linear-gradient(rgba(255,255,255,1) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,1) 1px,transparent 1px)", backgroundSize: "50px 50px" }} />
        </div>

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="relative">
            <div className="absolute inset-0 rounded-xl blur-lg opacity-60"
                 style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }} />
            <div className="relative w-10 h-10 rounded-xl flex items-center justify-center"
                 style={{ background: "linear-gradient(135deg,#6366f1,#7c3aed)", boxShadow: "0 0 24px rgba(99,102,241,0.5)" }}>
              <Brain size={18} className="text-white" />
            </div>
          </div>
          <div>
            <p className="text-white font-bold text-base tracking-tight">Agentic RAG</p>
            <p className="text-slate-600 text-[11px]">DS / ML Knowledge Base</p>
          </div>
        </div>

        {/* Hero */}
        <div className="relative z-10 space-y-8">
          <div>
            <h2 className="text-[2.6rem] font-black text-white leading-[1.1] tracking-tight mb-4">
              Your intelligent<br />
              <span className="text-gradient">ML assistant</span>
            </h2>
            <p className="text-slate-500 text-base leading-relaxed max-w-xs">
              Ask complex questions about data science and machine learning. Get accurate, cited answers instantly.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {FEATURES.map(({ icon: Icon, color, label, desc }) => (
              <div key={label} className="rounded-2xl p-3.5 space-y-2 transition-all duration-200 group"
                   style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
                   onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.05)"; e.currentTarget.style.borderColor = `${color}30`; }}
                   onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)"; }}>
                <div className="w-8 h-8 rounded-xl flex items-center justify-center"
                     style={{ background: `${color}18`, border: `1px solid ${color}25` }}>
                  <Icon size={14} style={{ color }} />
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-300">{label}</p>
                  <p className="text-[10px] text-slate-600 mt-0.5 leading-snug">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="flex -space-x-2">
            {["#6366f1","#8b5cf6","#06b6d4"].map((c, i) => (
              <div key={i} className="w-7 h-7 rounded-full border-2 flex items-center justify-center text-[9px] font-bold text-white"
                   style={{ background: c, borderColor: "#090a1c" }}>
                {["R","A","M"][i]}
              </div>
            ))}
          </div>
          <p className="text-[11px] text-slate-600">Used by your team</p>
        </div>
      </div>

      {/* ── Right form panel ──────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 relative">
        <div className="lg:hidden absolute inset-0 pointer-events-none overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1/2"
               style={{ background: "radial-gradient(ellipse at top,rgba(99,102,241,0.1) 0%,transparent 60%)" }} />
        </div>

        <div className="w-full max-w-[360px] relative z-10">

          {/* Mobile logo */}
          <div className="lg:hidden flex flex-col items-center mb-10">
            <div className="relative mb-4">
              <div className="absolute inset-0 rounded-2xl blur-xl opacity-60"
                   style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }} />
              <div className="relative w-16 h-16 rounded-2xl flex items-center justify-center"
                   style={{ background: "linear-gradient(135deg,#6366f1,#7c3aed)", boxShadow: "0 0 40px rgba(99,102,241,0.5)" }}>
                <Brain size={26} className="text-white" />
              </div>
            </div>
            <h1 className="text-gradient text-2xl font-black">Agentic RAG</h1>
            <p className="text-slate-500 text-sm mt-1 flex items-center gap-1">
              <Sparkles size={11} className="text-indigo-400" /> DS / ML Knowledge Base
            </p>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-black text-white tracking-tight">
              {mode === "login" ? "Welcome back" : "Create account"}
            </h2>
            <p className="text-slate-500 text-sm mt-1">
              {mode === "login" ? "Sign in to your workspace" : "Get started in seconds"}
            </p>
          </div>

          {/* Form card */}
          <div className="rounded-3xl p-7 animate-slide-up"
               style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.09)", boxShadow: "0 24px 80px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.07)" }}>

            {/* Tabs */}
            <div className="flex rounded-xl p-1 mb-6 gap-1"
                 style={{ background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.06)" }}>
              {[["login","Sign in"],["register","Register"]].map(([m, label]) => (
                <button key={m} onClick={() => { setMode(m); setError(null); }}
                  className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all duration-200"
                  style={mode === m
                    ? { background: "linear-gradient(135deg,#6366f1,#7c3aed)", color: "#fff", boxShadow: "0 4px 15px rgba(99,102,241,0.4)" }
                    : { color: "#64748b" }}>
                  {label}
                </button>
              ))}
            </div>

            {error && (
              <div className="mb-5 px-4 py-3 rounded-xl text-sm flex items-start gap-2.5"
                   style={{ background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.2)", color: "#fca5a5" }}>
                <span className="flex-shrink-0 mt-0.5">⚠</span>
                {error}
              </div>
            )}

            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="block text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-[0.12em]">Email address</label>
                <input type="email" required autoFocus value={email}
                  onChange={e => setEmail(e.target.value)} placeholder="you@example.com" className="input" />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-slate-500 mb-2 uppercase tracking-[0.12em]">Password</label>
                <div className="relative">
                  <input type={showPw ? "text" : "password"} required minLength={6}
                    value={password} onChange={e => setPass(e.target.value)}
                    placeholder="••••••••" className="input pr-11" />
                  <button type="button" onClick={() => setShowPw(v => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-300 transition-colors">
                    {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
                {mode === "register" && <p className="text-[10px] text-slate-700 mt-1.5">Minimum 6 characters</p>}
              </div>

              <button type="submit" disabled={loading}
                className="btn-primary w-full flex items-center justify-center gap-2 py-3 mt-2">
                {loading
                  ? <><Loader2 size={15} className="animate-spin" /> Please wait…</>
                  : <>{mode === "login" ? "Sign in" : "Create account"} <ArrowRight size={15} /></>}
              </button>
            </form>

            <div className="flex items-center gap-3 my-5">
              <div className="flex-1 h-px" style={{ background: "rgba(255,255,255,0.07)" }} />
              <span className="text-[10px] text-slate-700">secure &amp; private</span>
              <div className="flex-1 h-px" style={{ background: "rgba(255,255,255,0.07)" }} />
            </div>

            <div className="flex items-center justify-center gap-5">
              {[["JWT Auth","#818cf8"],["bcrypt","#6ee7b7"],["HTTPS","#fcd34d"]].map(([label, color]) => (
                <div key={label} className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />
                  <span className="text-[10px] text-slate-600">{label}</span>
                </div>
              ))}
            </div>
          </div>

          <p className="text-center text-[11px] text-slate-700 mt-6">
            Powered by{" "}
            <span className="text-indigo-400 font-medium">Gemma-4</span>
            {" · "}
            <span className="text-violet-400 font-medium">BGE Embeddings</span>
            {" · "}
            <span className="text-cyan-400 font-medium">ChromaDB</span>
          </p>
        </div>
      </div>
    </div>
  );
}

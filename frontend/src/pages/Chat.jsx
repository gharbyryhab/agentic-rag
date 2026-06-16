import { useState, useRef, useEffect } from "react";
import {
  Send, BookOpen, Globe, ChevronDown, ChevronUp,
  Sparkles, ThumbsUp, ThumbsDown, Zap, AlertCircle,
  Clipboard, Check, RotateCw, Brain, TrendingUp,
  FlaskConical, Network, BarChart2, Layers, MessageCircle,
} from "lucide-react";
import { submitFeedback } from "../api";
import { useChatContext } from "../context/ChatContext";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import MarkdownMessage from "../components/MarkdownMessage";

const ROUTE_BADGE = {
  simple:          "badge-emerald",
  agent:           "badge-violet",
  memory:          "badge-sky",
  out_of_domain:   "badge-slate",
  simple_fallback: "badge-amber",
  agent_fallback:  "badge-amber",
};

const SUGGESTIONS = [
  { icon: TrendingUp,    color: "#818cf8", label: "Gradient descent",      prompt: "What is gradient descent and how does it work?" },
  { icon: Layers,        color: "#c4b5fd", label: "SVM vs Random Forest",  prompt: "Compare SVM vs Random Forest for classification" },
  { icon: Brain,         color: "#67e8f9", label: "Overfitting",            prompt: "Explain overfitting and regularization techniques" },
  { icon: Network,       color: "#6ee7b7", label: "Neural networks",        prompt: "How do neural networks learn through backpropagation?" },
  { icon: FlaskConical,  color: "#fcd34d", label: "Bias-variance",          prompt: "What is the bias-variance tradeoff in machine learning?" },
  { icon: BarChart2,     color: "#f9a8d4", label: "Evaluation metrics",     prompt: "What metrics should I use for imbalanced classification?" },
];

const CARD = { background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 16 };

function relTime(date) {
  const s = Math.round((Date.now() - new Date(date)) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export default function ChatPage() {
  const { sessionId, messages, sessionTitle, pushMessage, confirmSession, setFeedback } = useChatContext();
  const { addToast } = useToast();
  const { token, user } = useAuth();
  const [input, setInput]                       = useState("");
  const [loading, setLoading]                   = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const bottomRef   = useRef(null);
  const textareaRef = useRef(null);
  const inputWrapRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, streamingContent]);

  const streamChat = async (question, onDone) => {
    const response = await fetch("/api/v1/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ question, session_id: sessionId }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "", accumulated = "";
    outer: while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        let evt; try { evt = JSON.parse(line.slice(5).trim()); } catch { continue; }
        if (evt.type === "ping")  continue;
        if (evt.type === "error") throw new Error(evt.detail);
        if (evt.type === "token") { accumulated += evt.value; setStreamingContent(accumulated); }
        if (evt.type === "done")  { onDone(evt, accumulated); break outer; }
      }
    }
  };

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;
    pushMessage({ role: "user", content: q, id: `user-${Date.now()}`, ts: new Date().toISOString() });
    setInput(""); setLoading(true); setStreamingContent("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    try {
      await streamChat(q, (evt, accumulated) => {
        confirmSession(evt.session_id, q.slice(0, 60));
        pushMessage({ role: "assistant", content: accumulated, id: evt.message_id,
          route: evt.route, latency_s: evt.latency_s, sources: evt.sources, feedback: null,
          ts: new Date().toISOString() });
      });
    } catch (err) {
      pushMessage({ role: "error", content: `Error: ${err.message || "Backend unreachable"}`, id: `err-${Date.now()}` });
      addToast("Request failed", "error");
    } finally { setStreamingContent(""); setLoading(false); }
  };

  const handleFeedback = async (msgId, rating, comment = null) => {
    try { await submitFeedback(msgId, rating, comment); setFeedback(msgId, rating); addToast("Feedback saved", "success"); }
    catch { addToast("Could not save feedback", "error"); }
  };

  const handleRegenerate = async (question) => {
    if (loading) return;
    setLoading(true); setStreamingContent("");
    try {
      await streamChat(question, (evt, accumulated) => {
        pushMessage({ role: "assistant", content: accumulated, id: evt.message_id,
          route: evt.route, latency_s: evt.latency_s, sources: evt.sources, feedback: null, regenerated: true,
          ts: new Date().toISOString() });
      });
    } catch (err) {
      pushMessage({ role: "error", content: `Error: ${err.message || "Backend unreachable"}`, id: `err-${Date.now()}` });
      addToast("Regeneration failed", "error");
    } finally { setStreamingContent(""); setLoading(false); }
  };

  const focusInput = (q) => { setInput(q); setTimeout(() => textareaRef.current?.focus(), 50); };

  const userCount = messages.filter(m => m.role === "user").length;
  const isEmpty   = messages.length === 0;
  const userInitial = user?.email?.[0]?.toUpperCase() ?? "U";

  return (
    <div className="flex flex-col h-full" style={{ background: "#08091a" }}>

      {/* ── Header (visible once chatting) ───────────────────── */}
      {!isEmpty && (
        <header className="flex-shrink-0 px-6 py-3 flex items-center justify-between"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", background: "rgba(8,9,26,0.9)", backdropFilter: "blur(16px)" }}>
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                 style={{ background: "linear-gradient(135deg,rgba(99,102,241,0.3),rgba(139,92,246,0.3))", border: "1px solid rgba(99,102,241,0.25)" }}>
              <MessageCircle size={12} className="text-indigo-400" />
            </div>
            <div className="min-w-0">
              <h1 className="font-semibold text-slate-200 text-sm truncate">
                {sessionTitle || (sessionId ? `Session ${sessionId.slice(0,8)}…` : "New conversation")}
              </h1>
              <p className="text-[10px] text-slate-600">{userCount} question{userCount !== 1 ? "s" : ""}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] font-medium text-slate-600">Live</span>
          </div>
        </header>
      )}

      {/* ── Main area ────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          /* ── EMPTY / NEW CONVERSATION ── */
          <div className="relative flex flex-col items-center justify-center min-h-full px-6 py-10 overflow-hidden">

            {/* Orb background */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
              <div className="absolute top-[-10%] left-[5%] w-[600px] h-[600px] rounded-full animate-orb"
                   style={{ background: "radial-gradient(circle,rgba(99,102,241,0.1) 0%,transparent 65%)", filter: "blur(40px)" }} />
              <div className="absolute bottom-[-10%] right-[5%] w-[500px] h-[500px] rounded-full animate-orb2"
                   style={{ background: "radial-gradient(circle,rgba(139,92,246,0.1) 0%,transparent 65%)", filter: "blur(50px)" }} />
              <div className="absolute top-[35%] right-[25%] w-[300px] h-[300px] rounded-full"
                   style={{ background: "radial-gradient(circle,rgba(6,182,212,0.05) 0%,transparent 70%)", filter: "blur(60px)" }} />
              <div className="absolute inset-0 opacity-[0.022]"
                   style={{ backgroundImage: "linear-gradient(rgba(255,255,255,1) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,1) 1px,transparent 1px)", backgroundSize: "60px 60px" }} />
            </div>

            <div className="relative z-10 flex flex-col items-center text-center max-w-2xl w-full animate-slide-up">

              {/* Logo */}
              <div className="relative mb-8">
                <div className="absolute inset-0 rounded-3xl blur-2xl opacity-50"
                     style={{ background: "linear-gradient(135deg,#6366f1,#8b5cf6)" }} />
                <div className="relative w-20 h-20 rounded-3xl flex items-center justify-center"
                     style={{ background: "linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%)", boxShadow: "0 0 60px rgba(99,102,241,0.4), inset 0 1px 0 rgba(255,255,255,0.15)" }}>
                  <Brain size={34} className="text-white" />
                </div>
                <div className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full flex items-center justify-center"
                     style={{ background: "#08091a", border: "2px solid #6366f1" }}>
                  <div className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse" />
                </div>
              </div>

              <h1 className="text-4xl font-black tracking-tight leading-[1.1] mb-3">
                <span className="text-gradient">Ask anything</span>
                <br />
                <span className="text-white">about DS &amp; ML</span>
              </h1>
              <p className="text-slate-500 text-base leading-relaxed mb-8 max-w-sm">
                Backed by a curated machine learning corpus. Cited answers, streamed in real time.
              </p>

              {/* Caps */}
              <div className="flex flex-wrap gap-2 justify-center mb-9">
                {[
                  ["Concepts & Theory","#818cf8"],["Code & Math","#6ee7b7"],
                  ["Comparisons","#fcd34d"],["Paper summaries","#f9a8d4"],
                ].map(([label, color]) => (
                  <span key={label} className="text-xs font-medium px-3 py-1 rounded-full"
                        style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color }}>
                    {label}
                  </span>
                ))}
              </div>

              {/* Suggestion grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 w-full">
                {SUGGESTIONS.map(({ icon: Icon, color, label, prompt }) => (
                  <button key={label} onClick={() => focusInput(prompt)}
                    className="group text-left rounded-2xl p-4 transition-all duration-200"
                    style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
                    onMouseEnter={e => { e.currentTarget.style.background = `${color}0d`; e.currentTarget.style.borderColor = `${color}35`; e.currentTarget.style.transform = "translateY(-2px)"; }}
                    onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.03)"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)"; e.currentTarget.style.transform = "translateY(0)"; }}>
                    <div className="flex items-start gap-3 mb-3">
                      <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
                           style={{ background: `${color}15`, border: `1px solid ${color}25` }}>
                        <Icon size={14} style={{ color }} />
                      </div>
                      <div className="min-w-0 pt-0.5">
                        <p className="text-xs font-semibold text-slate-300 mb-0.5">{label}</p>
                        <p className="text-[11px] text-slate-600 leading-snug line-clamp-2">{prompt}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 text-[10px] font-semibold opacity-0 group-hover:opacity-100 transition-opacity duration-200 pl-11"
                         style={{ color }}>
                      Try this →
                    </div>
                  </button>
                ))}
              </div>

              <p className="mt-10 text-[11px] text-slate-700 flex items-center gap-2.5">
                <span className="w-8 h-px inline-block" style={{ background: "rgba(255,255,255,0.08)" }} />
                Enter to send &nbsp;·&nbsp; Shift+Enter for new line
                <span className="w-8 h-px inline-block" style={{ background: "rgba(255,255,255,0.08)" }} />
              </p>
            </div>
          </div>
        ) : (
          /* ── MESSAGES ── */
          <div className="px-6 py-6 space-y-6 max-w-4xl mx-auto w-full">
            {messages.map((msg, index) => {
              const lastUserQ = msg.role === "assistant"
                ? messages.slice(0, index).reverse().find(m => m.role === "user")?.content
                : null;
              return (
                <MessageBubble key={msg.id} msg={msg} userInitial={userInitial}
                  onFeedback={handleFeedback}
                  onRegenerate={lastUserQ ? () => handleRegenerate(lastUserQ) : null} />
              );
            })}

            {/* Streaming */}
            {streamingContent && (
              <div className="animate-msg-in flex gap-3 items-start">
                <AssistantAvatar />
                <div className="flex-1 max-w-3xl space-y-1.5">
                  <div className="px-4 py-3.5" style={CARD}>
                    <p className="text-sm leading-relaxed text-slate-300 whitespace-pre-wrap">
                      {streamingContent}
                      <span className="inline-block w-0.5 h-[1.1em] bg-indigo-400 ml-0.5 animate-pulse align-text-bottom rounded-full" />
                    </p>
                  </div>
                  <p className="text-[10px] text-slate-700 pl-1 flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-emerald-400 animate-pulse" />
                    Generating…
                  </p>
                </div>
              </div>
            )}

            {/* Typing dots */}
            {loading && !streamingContent && (
              <div className="animate-msg-in flex gap-3 items-start">
                <AssistantAvatar />
                <div className="px-5 py-4 flex items-center gap-1.5" style={CARD}>
                  {[1,2,3].map(i => (
                    <span key={i} className={`w-2 h-2 rounded-full animate-typing-dot-${i}`}
                          style={{ background: "rgba(99,102,241,0.5)" }} />
                  ))}
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* ── Input ──────────────────────────────────────────── */}
      <footer className="flex-shrink-0 px-6 pb-5 pt-3"
              style={{ borderTop: isEmpty ? "none" : "1px solid rgba(255,255,255,0.05)" }}>
        {sessionId && !isEmpty && (
          <p className="text-[10px] text-slate-700 mb-2 text-center">
            Conversation memory active — context from previous messages included
          </p>
        )}
        <div className="max-w-3xl mx-auto">
          <div ref={inputWrapRef}
               className="relative flex items-end gap-0 rounded-2xl transition-all duration-200"
               style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)" }}>
            <textarea ref={textareaRef} rows={1}
              placeholder="Ask a question about data science & ML…"
              value={input}
              onChange={e => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${e.target.scrollHeight}px`;
              }}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
              onFocus={() => { if (inputWrapRef.current) { inputWrapRef.current.style.borderColor = "rgba(99,102,241,0.5)"; inputWrapRef.current.style.boxShadow = "0 0 0 3px rgba(99,102,241,0.1)"; } }}
              onBlur={() => { if (inputWrapRef.current) { inputWrapRef.current.style.borderColor = "rgba(255,255,255,0.1)"; inputWrapRef.current.style.boxShadow = "none"; } }}
              className="flex-1 resize-none bg-transparent text-sm text-slate-200 placeholder-slate-600
                         min-h-[52px] max-h-48 leading-relaxed py-4 pl-4 pr-2 focus:outline-none"
            />
            <div className="flex items-center gap-1.5 pr-2.5 pb-2.5 flex-shrink-0">
              {/* Char count when long */}
              {input.length > 200 && (
                <span className="text-[10px] tabular-nums"
                      style={{ color: input.length > 500 ? "#f87171" : "#475569" }}>
                  {input.length}
                </span>
              )}
              <button onClick={handleSend} disabled={!input.trim() || loading}
                className="flex items-center gap-1.5 h-9 px-4 rounded-xl text-sm font-semibold
                           transition-all duration-200 disabled:opacity-30 disabled:cursor-not-allowed text-white"
                style={{
                  background: input.trim() && !loading
                    ? "linear-gradient(135deg,#6366f1,#7c3aed)"
                    : "rgba(255,255,255,0.06)",
                  boxShadow: input.trim() && !loading ? "0 4px 18px rgba(99,102,241,0.45)" : "none",
                }}>
                {loading ? <RotateCw size={14} className="animate-spin" /> : <Send size={14} />}
                <span className="hidden sm:inline">{loading ? "…" : "Send"}</span>
              </button>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ── AssistantAvatar ─────────────────────────────────────────────────────── */
function AssistantAvatar() {
  return (
    <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5"
         style={{ background: "linear-gradient(135deg,rgba(99,102,241,0.35),rgba(139,92,246,0.35))", border: "1px solid rgba(99,102,241,0.3)", boxShadow: "0 0 14px rgba(99,102,241,0.2)" }}>
      <Sparkles size={13} className="text-indigo-300" />
    </div>
  );
}

/* ── UserAvatar ──────────────────────────────────────────────────────────── */
function UserAvatar({ initial }) {
  return (
    <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 font-bold text-sm"
         style={{ background: "linear-gradient(135deg,rgba(16,185,129,0.25),rgba(5,150,105,0.25))", border: "1px solid rgba(16,185,129,0.25)", color: "#6ee7b7" }}>
      {initial}
    </div>
  );
}

/* ── MessageBubble ───────────────────────────────────────────────────────── */
function MessageBubble({ msg, userInitial, onFeedback, onRegenerate }) {
  const [sourcesOpen, setSourcesOpen]       = useState(false);
  const [copyDone, setCopyDone]             = useState(false);
  const [showCommentBox, setShowCommentBox] = useState(false);
  const [comment, setComment]               = useState("");
  const popoverRef = useRef(null);

  useEffect(() => {
    if (!showCommentBox) return;
    const handler = e => { if (popoverRef.current && !popoverRef.current.contains(e.target)) { setShowCommentBox(false); setComment(""); } };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showCommentBox]);

  const handleCopy = () => { navigator.clipboard.writeText(msg.content); setCopyDone(true); setTimeout(() => setCopyDone(false), 2000); };

  /* User */
  if (msg.role === "user") {
    return (
      <div className="animate-msg-in flex justify-end items-end gap-2.5">
        <div className="flex flex-col items-end gap-1 max-w-xl">
          <div className="rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed text-white"
               style={{ background: "linear-gradient(135deg,#4f46e5,#7c3aed)", boxShadow: "0 4px 20px rgba(99,102,241,0.25)" }}>
            {msg.content}
          </div>
          {msg.ts && (
            <p className="text-[9px] text-slate-700 pr-1">{relTime(msg.ts)}</p>
          )}
        </div>
        <UserAvatar initial={userInitial} />
      </div>
    );
  }

  /* Error */
  if (msg.role === "error") {
    return (
      <div className="animate-msg-in flex gap-3 items-start">
        <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5"
             style={{ background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.2)" }}>
          <AlertCircle size={14} className="text-red-400" />
        </div>
        <div className="px-4 py-3 text-sm max-w-xl rounded-2xl"
             style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#fca5a5" }}>
          {msg.content}
        </div>
      </div>
    );
  }

  /* Assistant */
  const badgeClass = ROUTE_BADGE[msg.route] || "badge-slate";
  const hasSources = msg.sources?.length > 0;

  return (
    <div className="animate-msg-in flex gap-3 items-start">
      <AssistantAvatar />
      <div className="flex-1 max-w-3xl space-y-2">

        {/* Answer */}
        <div className="px-4 py-3.5" style={CARD}>
          <MarkdownMessage content={msg.content} />
        </div>

        {/* Meta */}
        <div className="flex items-center gap-2 text-xs text-slate-600 px-0.5 flex-wrap">
          {msg.route && <span className={badgeClass}>{msg.route.replace("_"," ")}</span>}
          {msg.regenerated && (
            <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full"
                  style={{ background: "rgba(139,92,246,0.12)", color: "#c4b5fd", border: "1px solid rgba(139,92,246,0.2)" }}>
              <RotateCw size={9} /> Regenerated
            </span>
          )}
          {msg.latency_s != null && (
            <span className="flex items-center gap-1 text-slate-700">
              <Zap size={10} className="text-amber-500" />{msg.latency_s}s
            </span>
          )}
          {msg.ts && <span className="text-slate-700 text-[10px]">{relTime(msg.ts)}</span>}
          {hasSources && (
            <button onClick={() => setSourcesOpen(o => !o)}
              className="flex items-center gap-1.5 hover:text-indigo-400 transition-colors duration-150">
              <BookOpen size={11} />
              {msg.sources.length} source{msg.sources.length !== 1 ? "s" : ""}
              {sourcesOpen ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
            </button>
          )}

          <div className="ml-auto flex items-center gap-0.5">
            {/* Copy */}
            <ActionBtn onClick={handleCopy} title="Copy" active={copyDone} activeColor="#6ee7b7"
              activeIcon={<><Check size={11} /><span className="text-[10px]">Copied</span></>}
              icon={<Clipboard size={11} />} />

            {/* Regenerate */}
            {onRegenerate && (
              <ActionBtn onClick={onRegenerate} title="Regenerate" icon={<RotateCw size={11} />} hoverColor="#a5b4fc" />
            )}

            {/* Thumbs up */}
            <ActionBtn onClick={() => onFeedback(msg.id, 1)} title="Helpful"
              active={msg.feedback === 1} activeColor="#6ee7b7"
              icon={<ThumbsUp size={11} />} activeIcon={<ThumbsUp size={11} />} />

            {/* Thumbs down */}
            <div ref={popoverRef} className="relative">
              <ActionBtn onClick={() => setShowCommentBox(true)} title="Not helpful"
                active={msg.feedback === -1} activeColor="#f87171"
                icon={<ThumbsDown size={11} />} activeIcon={<ThumbsDown size={11} />} />

              {showCommentBox && (
                <div className="absolute right-0 top-full mt-2 z-20 w-72 p-4 space-y-3 animate-fade-in rounded-2xl"
                     style={{ background: "#0f1022", border: "1px solid rgba(255,255,255,0.1)", boxShadow: "0 20px 50px rgba(0,0,0,0.7)" }}>
                  <p className="text-xs font-semibold text-slate-400">What was wrong? (optional)</p>
                  <textarea autoFocus rows={3} value={comment} onChange={e => setComment(e.target.value)}
                    onKeyDown={e => { if (e.key === "Escape") { setShowCommentBox(false); setComment(""); } }}
                    placeholder="Incorrect, irrelevant, too long…"
                    className="w-full text-xs resize-none focus:outline-none rounded-xl px-3 py-2.5"
                    style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.08)", color: "#cbd5e1", caretColor: "#6366f1" }}
                    onFocus={e => e.target.style.borderColor = "rgba(239,68,68,0.4)"}
                    onBlur={e  => e.target.style.borderColor = "rgba(255,255,255,0.08)"} />
                  <div className="flex items-center justify-end gap-2">
                    <button onClick={() => { setShowCommentBox(false); setComment(""); onFeedback(msg.id, -1, null); }}
                      className="text-xs text-slate-600 hover:text-slate-300 px-3 py-1.5 rounded-lg transition-all"
                      onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.05)"}
                      onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                      Skip
                    </button>
                    <button onClick={() => { const c = comment.trim()||null; setShowCommentBox(false); setComment(""); onFeedback(msg.id,-1,c); }}
                      className="text-xs font-semibold px-3 py-1.5 rounded-lg text-white transition-all"
                      style={{ background: "rgba(239,68,68,0.2)", border: "1px solid rgba(239,68,68,0.3)" }}
                      onMouseEnter={e => e.currentTarget.style.background = "rgba(239,68,68,0.32)"}
                      onMouseLeave={e => e.currentTarget.style.background = "rgba(239,68,68,0.2)"}>
                      Submit
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Sources */}
        {sourcesOpen && hasSources && (
          <div className="space-y-1.5 pt-0.5 pl-0.5 animate-fade-in">
            {msg.sources.map((s, i) => <SourceCard key={i} source={s} />)}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── ActionBtn ───────────────────────────────────────────────────────────── */
function ActionBtn({ onClick, title, icon, activeIcon, active, activeColor, hoverColor }) {
  return (
    <button onClick={onClick} title={title}
      className="p-1.5 rounded-lg transition-all duration-150 flex items-center gap-1"
      style={{ color: active ? activeColor : "#475569", background: active ? `${activeColor}18` : "transparent" }}
      onMouseEnter={e => { if (!active) { e.currentTarget.style.color = hoverColor || "#94a3b8"; e.currentTarget.style.background = "rgba(255,255,255,0.05)"; } }}
      onMouseLeave={e => { if (!active) { e.currentTarget.style.color = "#475569"; e.currentTarget.style.background = "transparent"; } }}>
      {active && activeIcon ? activeIcon : icon}
    </button>
  );
}

/* ── SourceCard ──────────────────────────────────────────────────────────── */
function SourceCard({ source }) {
  const isWeb = source.source?.startsWith("http") || source.book_title === "Web" || source.source === "search_web";
  const score = source.score > 0 ? source.score : null;

  return (
    <div className="rounded-xl px-4 py-3 text-xs space-y-2"
         style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="flex items-center gap-2">
        <div className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0"
             style={{ background: isWeb ? "rgba(99,102,241,0.15)" : "rgba(255,255,255,0.06)" }}>
          {isWeb
            ? <Globe    size={11} className="text-indigo-400" />
            : <BookOpen size={11} className="text-slate-500" />
          }
        </div>
        <span className="font-semibold text-slate-400 truncate flex-1">{source.book_title || source.source || "Source"}</span>
        {source.page && <span className="text-slate-700 flex-shrink-0">p.{source.page}</span>}
        {score && (
          <span className="flex-shrink-0 text-[10px] font-mono text-slate-700 tabular-nums">
            {(score * 100).toFixed(0)}%
          </span>
        )}
      </div>
      {/* Score bar */}
      {score && (
        <div className="h-0.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
          <div className="h-full rounded-full transition-all duration-500"
               style={{ width: `${(score * 100).toFixed(0)}%`, background: "linear-gradient(90deg,#6366f1,#8b5cf6)" }} />
        </div>
      )}
      {source.snippet && (
        <p className="text-slate-600 leading-relaxed line-clamp-2">{source.snippet}</p>
      )}
    </div>
  );
}

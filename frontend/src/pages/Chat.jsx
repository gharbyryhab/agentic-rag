import { useState, useRef, useEffect } from "react";
import {
  Send, BookOpen, Globe, ChevronDown, ChevronUp,
  Sparkles, ThumbsUp, ThumbsDown, Zap, AlertCircle,
} from "lucide-react";
import { sendMessage, submitFeedback } from "../api";
import { useChatContext } from "../context/ChatContext";

// Route → badge class mapping
const ROUTE_BADGE = {
  simple:        "badge-emerald",
  agent:         "badge-violet",
  memory:        "badge-sky",
  out_of_domain: "badge-slate",
  simple_fallback: "badge-amber",
  agent_fallback:  "badge-amber",
};

const SUGGESTIONS = [
  "What is gradient descent?",
  "Compare SVM vs Random Forest",
  "Explain overfitting and regularization",
];

export default function ChatPage() {
  const { sessionId, messages, sessionTitle, pushMessage, confirmSession, setFeedback } =
    useChatContext();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;

    pushMessage({ role: "user", content: q, id: `user-${Date.now()}` });
    setInput("");
    setLoading(true);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      const res = await sendMessage(q, sessionId);
      confirmSession(res.session_id, q.slice(0, 60));
      pushMessage({
        role: "assistant",
        content: res.answer,
        id: res.message_id,
        route: res.route,
        latency_s: res.latency_s,
        sources: res.sources,
        feedback: null,
      });
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || "Backend unreachable";
      pushMessage({
        role: "error",
        content: `Error: ${detail}`,
        id: `err-${Date.now()}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (msgId, rating) => {
    try {
      await submitFeedback(msgId, rating);
      setFeedback(msgId, rating);
    } catch {
      // Feedback is best-effort; don't interrupt UX
    }
  };

  const userCount = messages.filter((m) => m.role === "user").length;

  return (
    <div className="flex flex-col h-full bg-white">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="flex-shrink-0 border-b border-slate-100 px-6 py-3.5 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-semibold text-slate-800 text-sm leading-tight">
              {sessionTitle || (sessionId ? `Session ${sessionId.slice(0, 8)}…` : "New conversation")}
            </h1>
            {sessionId && (
              <p className="text-[11px] text-slate-400 mt-0.5">
                {userCount} question{userCount !== 1 ? "s" : ""}
              </p>
            )}
          </div>
        </div>
      </header>

      {/* ── Messages ────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {/* Empty state */}
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-5 select-none">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600
                            flex items-center justify-center shadow-lg shadow-indigo-200/60">
              <Sparkles size={22} className="text-white" />
            </div>
            <div className="text-center">
              <p className="text-slate-800 font-semibold text-lg">Ask anything about DS & ML</p>
              <p className="text-slate-400 text-sm mt-1.5">
                AI assistant backed by a curated machine learning book corpus
              </p>
            </div>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setInput(s)}
                  className="text-xs bg-white border border-slate-200 rounded-full px-4 py-2
                             hover:border-indigo-300 hover:text-indigo-600 hover:bg-indigo-50/50
                             transition-all duration-150 shadow-sm"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message list */}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} onFeedback={handleFeedback} />
        ))}

        {/* Typing indicator */}
        {loading && (
          <div className="animate-msg-in flex gap-3 items-start">
            <Avatar />
            <div className="card px-4 py-3.5 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-typing-dot-1" />
              <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-typing-dot-2" />
              <span className="w-1.5 h-1.5 rounded-full bg-slate-300 animate-typing-dot-3" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Input area ──────────────────────────────────────────────────── */}
      <footer className="flex-shrink-0 border-t border-slate-100 px-6 py-4 bg-white">
        {sessionId && (
          <p className="text-[10px] text-slate-400 mb-2.5 text-center">
            Conversation memory active — context from previous messages is included
          </p>
        )}
        <div className="flex gap-3 max-w-4xl mx-auto items-end">
          <textarea
            ref={textareaRef}
            className="input flex-1 resize-none text-sm min-h-[44px] max-h-40 leading-relaxed py-3"
            rows={1}
            placeholder="Ask a question… (Enter to send, Shift+Enter for new line)"
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = `${e.target.scrollHeight}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="btn-primary flex items-center gap-2 h-[44px] px-5 flex-shrink-0"
          >
            <Send size={14} />
            Send
          </button>
        </div>
      </footer>
    </div>
  );
}

// ── Avatar ───────────────────────────────────────────────────────────────────

function Avatar({ size = "md" }) {
  const cls = size === "sm"
    ? "w-7 h-7 rounded-lg"
    : "w-8 h-8 rounded-xl";
  return (
    <div className={`${cls} bg-gradient-to-br from-indigo-500 to-violet-600
                     flex items-center justify-center flex-shrink-0 shadow-sm mt-0.5`}>
      <Sparkles size={size === "sm" ? 11 : 13} className="text-white" />
    </div>
  );
}

// ── MessageBubble ─────────────────────────────────────────────────────────────

function MessageBubble({ msg, onFeedback }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="animate-msg-in flex justify-end">
        <div className="bg-gradient-to-br from-indigo-600 to-indigo-700 text-white
                        rounded-2xl rounded-tr-sm px-4 py-3 max-w-xl text-sm leading-relaxed shadow-sm">
          {msg.content}
        </div>
      </div>
    );
  }

  if (msg.role === "error") {
    return (
      <div className="animate-msg-in flex gap-3 items-start">
        <div className="w-8 h-8 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0 mt-0.5">
          <AlertCircle size={14} className="text-red-500" />
        </div>
        <div className="card border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 max-w-xl">
          {msg.content}
        </div>
      </div>
    );
  }

  const badgeClass = ROUTE_BADGE[msg.route] || "badge-slate";
  const hasSources = msg.sources?.length > 0;

  return (
    <div className="animate-msg-in flex gap-3 items-start">
      <Avatar />

      <div className="flex-1 max-w-3xl space-y-2">
        {/* Answer card */}
        <div className="card px-4 py-3.5">
          <p className="text-sm leading-relaxed whitespace-pre-wrap text-slate-800">
            {msg.content}
          </p>
        </div>

        {/* Meta bar */}
        <div className="flex items-center gap-2 text-xs text-slate-400 px-0.5 flex-wrap">
          {msg.route && (
            <span className={badgeClass}>{msg.route.replace("_", " ")}</span>
          )}
          {msg.latency_s != null && (
            <span className="flex items-center gap-1 text-slate-400">
              <Zap size={10} />
              {msg.latency_s}s
            </span>
          )}
          {hasSources && (
            <button
              onClick={() => setSourcesOpen((o) => !o)}
              className="flex items-center gap-1.5 text-slate-400 hover:text-indigo-600
                         transition-colors duration-150 ml-0.5"
            >
              <BookOpen size={11} />
              {msg.sources.length} source{msg.sources.length !== 1 ? "s" : ""}
              {sourcesOpen ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
            </button>
          )}

          {/* Feedback buttons */}
          <div className="ml-auto flex gap-1">
            <button
              onClick={() => onFeedback(msg.id, 1)}
              title="Helpful"
              className={`p-1.5 rounded-lg transition-all duration-150 ${
                msg.feedback === 1
                  ? "bg-emerald-50 text-emerald-600"
                  : "text-slate-300 hover:text-emerald-500 hover:bg-emerald-50"
              }`}
            >
              <ThumbsUp size={12} />
            </button>
            <button
              onClick={() => onFeedback(msg.id, -1)}
              title="Not helpful"
              className={`p-1.5 rounded-lg transition-all duration-150 ${
                msg.feedback === -1
                  ? "bg-red-50 text-red-500"
                  : "text-slate-300 hover:text-red-400 hover:bg-red-50"
              }`}
            >
              <ThumbsDown size={12} />
            </button>
          </div>
        </div>

        {/* Sources accordion */}
        {sourcesOpen && hasSources && (
          <div className="space-y-1.5 pt-0.5 pl-0.5 animate-fade-in">
            {msg.sources.map((s, i) => (
              <SourceCard key={i} source={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── SourceCard ────────────────────────────────────────────────────────────────

function SourceCard({ source }) {
  const isWeb =
    source.source?.startsWith("http") ||
    source.source?.includes("tool:") ||
    source.source?.includes("<tool:");

  return (
    <div className="bg-slate-50/80 border border-slate-100 rounded-xl px-3.5 py-2.5 text-xs space-y-1.5">
      <div className="flex items-center gap-2 font-medium text-slate-700">
        {isWeb ? (
          <Globe size={11} className="text-indigo-400 flex-shrink-0" />
        ) : (
          <BookOpen size={11} className="text-slate-400 flex-shrink-0" />
        )}
        <span className="truncate">{source.book_title || source.source || "Source"}</span>
        {source.page && (
          <span className="text-slate-400 flex-shrink-0 font-normal">· p.{source.page}</span>
        )}
        {source.score > 0 && (
          <span className="ml-auto text-slate-400 flex-shrink-0 tabular-nums font-normal">
            {(source.score * 100).toFixed(0)}%
          </span>
        )}
      </div>
      {source.snippet && (
        <p className="text-slate-500 leading-relaxed line-clamp-3">{source.snippet}</p>
      )}
    </div>
  );
}

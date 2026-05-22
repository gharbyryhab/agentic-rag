import { useState, useRef, useEffect } from "react";
import {
  Send, BookOpen, Globe, ChevronDown, ChevronUp,
  Loader2, ThumbsUp, ThumbsDown,
} from "lucide-react";
import { sendMessage, submitFeedback } from "../api";
import { useChatContext } from "../context/ChatContext";

export default function ChatPage() {
  const { sessionId, messages, sessionTitle, pushMessage, confirmSession, setFeedback } = useChatContext();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  // Scroll vers le bas à chaque nouveau message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || loading) return;

    // Afficher le message utilisateur immédiatement
    pushMessage({ role: "user", content: q, id: `user-${Date.now()}` });
    setInput("");
    setLoading(true);

    try {
      const res = await sendMessage(q, sessionId);
      // Confirmer le sessionId si c'était une nouvelle session
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
    } catch {
      pushMessage({
        role: "error",
        content: "Erreur : le backend ne répond pas. Vérifie qu'il est bien lancé.",
        id: `err-${Date.now()}`,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (msgId, rating) => {
    await submitFeedback(msgId, rating);
    setFeedback(msgId, rating);
  };

  return (
    <div className="flex flex-col h-full bg-slate-50">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-3.5 flex items-center justify-between">
        <div>
          <h1 className="font-semibold text-slate-800 text-sm">
            {sessionTitle || (sessionId ? `Session ${sessionId.slice(0, 8)}…` : "Nouvelle discussion")}
          </h1>
          {sessionId && (
            <p className="text-[10px] text-slate-400 mt-0.5">
              {messages.filter((m) => m.role === "user").length} question(s) · session {sessionId.slice(0, 8)}
            </p>
          )}
        </div>
      </div>

      {/* Zone messages */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-3 select-none">
            <BookOpen size={44} className="text-slate-200" />
            <p className="text-sm">Pose une question sur le Machine Learning, les stats ou l'IA</p>
            <div className="flex flex-wrap gap-2 justify-center mt-2">
              {[
                "C'est quoi le gradient descent ?",
                "Différence SVM vs Random Forest ?",
                "Qu'est-ce que l'overfitting ?",
              ].map((s) => (
                <button
                  key={s}
                  onClick={() => setInput(s)}
                  className="text-xs bg-white border border-slate-200 rounded-full px-3 py-1.5 hover:border-blue-300 hover:text-blue-600 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} onFeedback={handleFeedback} />
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
              <Loader2 size={15} className="text-blue-600 animate-spin" />
            </div>
            <div className="card px-4 py-3 text-sm text-slate-400 italic">
              Gemma-4 réfléchit…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Zone de saisie */}
      <div className="bg-white border-t border-slate-200 px-6 py-4">
        {sessionId && (
          <p className="text-[10px] text-slate-400 mb-2 text-center">
            Tu continues la discussion — les messages précédents sont en mémoire.
          </p>
        )}
        <div className="flex gap-3 max-w-4xl mx-auto">
          <textarea
            className="input flex-1 resize-none text-sm min-h-[44px] max-h-36"
            rows={1}
            placeholder="Pose ta question… (Entrée pour envoyer, Maj+Entrée pour sauter une ligne)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
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
            className="btn-primary flex items-center gap-2 self-end"
          >
            <Send size={15} />
            Envoyer
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Composants internes ──────────────────────────────────────────────────────

function MessageBubble({ msg, onFeedback }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 max-w-xl text-sm leading-relaxed shadow-sm">
          {msg.content}
        </div>
      </div>
    );
  }

  if (msg.role === "error") {
    return (
      <div className="card border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
        {msg.content}
      </div>
    );
  }

  const hasSources = msg.sources && msg.sources.length > 0;
  const routeClass =
    msg.route === "agent"
      ? "bg-purple-100 text-purple-700"
      : "bg-emerald-100 text-emerald-700";

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 text-white text-xs font-bold shadow-sm">
        AI
      </div>

      <div className="flex-1 max-w-3xl space-y-2">
        {/* Bulle réponse */}
        <div className="card px-4 py-3">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
        </div>

        {/* Barre meta */}
        <div className="flex items-center gap-3 text-xs text-slate-400 px-1 flex-wrap">
          {msg.route && (
            <span className={`px-2 py-0.5 rounded-full font-medium ${routeClass}`}>
              {msg.route}
            </span>
          )}
          {msg.latency_s != null && <span>{msg.latency_s}s</span>}
          {hasSources && (
            <button
              onClick={() => setSourcesOpen((o) => !o)}
              className="flex items-center gap-1 hover:text-slate-600 transition-colors"
            >
              {sourcesOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {msg.sources.length} source{msg.sources.length > 1 ? "s" : ""}
            </button>
          )}

          {/* Feedback */}
          <div className="ml-auto flex gap-1.5">
            <button
              onClick={() => onFeedback(msg.id, 1)}
              title="Utile"
              className={`p-1.5 rounded-lg transition-colors ${
                msg.feedback === 1
                  ? "bg-emerald-50 text-emerald-600"
                  : "text-slate-300 hover:text-emerald-500 hover:bg-emerald-50"
              }`}
            >
              <ThumbsUp size={13} />
            </button>
            <button
              onClick={() => onFeedback(msg.id, -1)}
              title="Pas utile"
              className={`p-1.5 rounded-lg transition-colors ${
                msg.feedback === -1
                  ? "bg-red-50 text-red-500"
                  : "text-slate-300 hover:text-red-400 hover:bg-red-50"
              }`}
            >
              <ThumbsDown size={13} />
            </button>
          </div>
        </div>

        {/* Sources accordéon */}
        {sourcesOpen && hasSources && (
          <div className="space-y-1.5 pl-1">
            {msg.sources.map((s, i) => (
              <SourceCard key={i} source={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SourceCard({ source }) {
  const isWeb =
    source.source?.startsWith("http") ||
    source.source?.includes("search_web");

  return (
    <div className="card px-3 py-2.5 text-xs space-y-1">
      <div className="flex items-center gap-2 font-medium text-slate-700">
        {isWeb ? (
          <Globe size={11} className="text-blue-400" />
        ) : (
          <BookOpen size={11} className="text-slate-400" />
        )}
        <span className="truncate">{source.book_title || source.source || "Source"}</span>
        {source.page && <span className="text-slate-400 flex-shrink-0">· p.{source.page}</span>}
        {source.score > 0 && (
          <span className="ml-auto text-slate-400 flex-shrink-0">
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

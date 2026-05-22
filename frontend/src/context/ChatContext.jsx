import { createContext, useContext, useState, useCallback } from "react";
import { getSession } from "../api";

const ChatContext = createContext(null);

export function ChatProvider({ children }) {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [sessionTitle, setSessionTitle] = useState(null);

  /** Démarrer une nouvelle conversation vierge */
  const newChat = useCallback(() => {
    setSessionId(null);
    setMessages([]);
    setSessionTitle(null);
  }, []);

  /** Charger une session existante depuis l'API */
  const loadSession = useCallback(async (id) => {
    const data = await getSession(id);
    setSessionId(data.id);
    setSessionTitle(data.title);
    setMessages(
      data.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        route: m.route,
        latency_s: m.latency_s,
        sources: m.sources || [],
        feedback: m.feedback_rating,
      }))
    );
  }, []);

  /** Ajouter un message (user ou assistant) après un envoi */
  const pushMessage = useCallback((msg) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  /** Mettre à jour le sessionId après le premier message */
  const confirmSession = useCallback((id, title) => {
    setSessionId(id);
    if (title) setSessionTitle(title);
  }, []);

  /** Mettre à jour le feedback d'un message */
  const setFeedback = useCallback((msgId, rating) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === msgId ? { ...m, feedback: rating } : m))
    );
  }, []);

  return (
    <ChatContext.Provider
      value={{ sessionId, messages, sessionTitle, newChat, loadSession, pushMessage, confirmSession, setFeedback }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export const useChatContext = () => useContext(ChatContext);

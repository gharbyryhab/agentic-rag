import { createContext, useCallback, useContext, useRef, useState } from "react";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const counter = useRef(0);

  // Start the exit animation then remove from DOM after it finishes.
  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, exiting: true } : t)));
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 220); // matches animate-toast-out duration
  }, []);

  const addToast = useCallback(
    (message, type = "info") => {
      const id = ++counter.current;
      setToasts((prev) => {
        const next = [...prev, { id, message, type, exiting: false }];
        // Enforce maximum of 4; drop the oldest when exceeded.
        return next.length > 4 ? next.slice(next.length - 4) : next;
      });
      // Begin exit animation 2.78s after arrival (total lifetime ≈ 3s).
      setTimeout(() => removeToast(id), 2780);
    },
    [removeToast]
  );

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}

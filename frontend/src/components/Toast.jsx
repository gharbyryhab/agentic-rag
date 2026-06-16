import { CheckCircle, AlertCircle, Info, X } from "lucide-react";
import { useToast } from "../context/ToastContext";

// ── Per-type visual config ────────────────────────────────────────────────────

const TYPE_CONFIG = {
  success: {
    Icon: CheckCircle,
    container: "bg-emerald-50 border-emerald-200",
    text: "text-emerald-800",
    icon: "text-emerald-500",
    dismiss: "text-emerald-400 hover:text-emerald-700 hover:bg-emerald-100",
  },
  error: {
    Icon: AlertCircle,
    container: "bg-red-50 border-red-200",
    text: "text-red-700",
    icon: "text-red-400",
    dismiss: "text-red-300 hover:text-red-600 hover:bg-red-100",
  },
  info: {
    Icon: Info,
    container: "bg-indigo-50 border-indigo-200",
    text: "text-indigo-800",
    icon: "text-indigo-400",
    dismiss: "text-indigo-300 hover:text-indigo-600 hover:bg-indigo-100",
  },
};

// ── Single toast ──────────────────────────────────────────────────────────────

function Toast({ toast, onDismiss }) {
  const cfg = TYPE_CONFIG[toast.type] ?? TYPE_CONFIG.info;
  const { Icon } = cfg;

  return (
    <div
      className={`
        flex items-start gap-3 px-4 py-3 rounded-xl border shadow-lg
        min-w-[260px] max-w-[360px]
        ${cfg.container}
        ${toast.exiting ? "animate-toast-out" : "animate-toast-in"}
      `}
    >
      <Icon size={16} className={`flex-shrink-0 mt-0.5 ${cfg.icon}`} />
      <p className={`flex-1 text-sm font-medium leading-snug ${cfg.text}`}>
        {toast.message}
      </p>
      <button
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss"
        className={`flex-shrink-0 p-0.5 rounded-md transition-colors duration-150 ${cfg.dismiss}`}
      >
        <X size={13} />
      </button>
    </div>
  );
}

// ── Container (fixed bottom-right) ───────────────────────────────────────────

export function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      aria-label="Notifications"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((toast) => (
        <div key={toast.id} className="pointer-events-auto">
          <Toast toast={toast} onDismiss={removeToast} />
        </div>
      ))}
    </div>
  );
}

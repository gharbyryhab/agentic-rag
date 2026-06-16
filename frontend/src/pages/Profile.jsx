import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  User, Mail, Lock, Trash2, LogOut, CheckCircle,
  AlertCircle, Loader2, Eye, EyeOff, MessageSquare, HelpCircle,
} from "lucide-react";
import { getProfile, updateEmail, updatePassword, deleteAccount } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

// ── Small reusable section card ───────────────────────────────────────────────
function Section({ icon: Icon, title, children }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
          <Icon size={15} className="text-indigo-600" />
        </div>
        <h2 className="font-semibold text-slate-800 text-sm">{title}</h2>
      </div>
      <div className="px-6 py-5">{children}</div>
    </div>
  );
}

// ── Inline feedback message ───────────────────────────────────────────────────
function Feedback({ type, message }) {
  if (!message) return null;
  const isError = type === "error";
  return (
    <div className={`flex items-center gap-2 text-sm rounded-xl px-4 py-3 mt-3 ${
      isError
        ? "bg-red-50 text-red-600 border border-red-200"
        : "bg-emerald-50 text-emerald-700 border border-emerald-200"
    }`}>
      {isError ? <AlertCircle size={14} /> : <CheckCircle size={14} />}
      {message}
    </div>
  );
}

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const { addToast } = useToast();
  const navigate = useNavigate();

  // Profile data
  const [profile, setProfile] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(true);

  // Email form
  const [newEmail, setNewEmail]       = useState("");
  const [emailStatus, setEmailStatus] = useState({ type: null, msg: null });
  const [savingEmail, setSavingEmail] = useState(false);

  // Password form
  const [currentPw, setCurrentPw]   = useState("");
  const [newPw, setNewPw]           = useState("");
  const [confirmPw, setConfirmPw]   = useState("");
  const [showPws, setShowPws]       = useState({ current: false, new: false, confirm: false });
  const [pwStatus, setPwStatus]     = useState({ type: null, msg: null });
  const [savingPw, setSavingPw]     = useState(false);

  // Delete modal
  const [showDelete, setShowDelete] = useState(false);
  const [deleting, setDeleting]     = useState(false);

  useEffect(() => {
    getProfile()
      .then((p) => { setProfile(p); setNewEmail(p.email); })
      .catch(() => addToast("Could not load profile", "error"))
      .finally(() => setLoadingProfile(false));
  }, []);

  // ── Email update ──────────────────────────────────────────────────────────
  const handleEmailSave = async (e) => {
    e.preventDefault();
    setEmailStatus({ type: null, msg: null });
    if (newEmail === profile?.email) {
      setEmailStatus({ type: "error", msg: "That's already your current email." });
      return;
    }
    setSavingEmail(true);
    try {
      const updated = await updateEmail(newEmail);
      setProfile(updated);
      setEmailStatus({ type: "success", msg: "Email updated successfully." });
      addToast("Email updated", "success");
    } catch (err) {
      const detail = err.response?.data?.detail || "Failed to update email.";
      setEmailStatus({ type: "error", msg: detail });
    } finally {
      setSavingEmail(false);
    }
  };

  // ── Password update ───────────────────────────────────────────────────────
  const handlePasswordSave = async (e) => {
    e.preventDefault();
    setPwStatus({ type: null, msg: null });
    if (newPw !== confirmPw) {
      setPwStatus({ type: "error", msg: "New passwords do not match." });
      return;
    }
    if (newPw.length < 8) {
      setPwStatus({ type: "error", msg: "Password must be at least 8 characters." });
      return;
    }
    setSavingPw(true);
    try {
      await updatePassword(currentPw, newPw);
      setPwStatus({ type: "success", msg: "Password updated successfully." });
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      addToast("Password updated", "success");
    } catch (err) {
      const detail = err.response?.data?.detail || "Failed to update password.";
      setPwStatus({ type: "error", msg: detail });
    } finally {
      setSavingPw(false);
    }
  };

  // ── Sign out ──────────────────────────────────────────────────────────────
  const handleSignOut = () => {
    logout();
    navigate("/login", { replace: true });
  };

  // ── Delete account ────────────────────────────────────────────────────────
  const handleDeleteAccount = async () => {
    setDeleting(true);
    try {
      await deleteAccount();
      logout();
      navigate("/login", { replace: true });
    } catch {
      addToast("Failed to delete account", "error");
      setDeleting(false);
      setShowDelete(false);
    }
  };

  const togglePw = (field) => setShowPws((p) => ({ ...p, [field]: !p[field] }));

  if (loadingProfile) {
    return (
      <div className="flex items-center justify-center h-full gap-3 text-slate-400">
        <Loader2 size={18} className="animate-spin" />
        <span className="text-sm">Loading profile…</span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-slate-50">
      <div className="max-w-2xl mx-auto px-6 py-8 space-y-5">

        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Profile</h1>
            <p className="text-sm text-slate-500 mt-0.5">Manage your account settings</p>
          </div>
          <button
            onClick={handleSignOut}
            className="flex items-center gap-2 text-sm font-medium text-slate-500
                       hover:text-red-500 px-3 py-2 rounded-lg hover:bg-red-50
                       border border-slate-200 hover:border-red-200 transition-all duration-150"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>

        {/* Account overview */}
        {profile && (
          <Section icon={User} title="Account overview">
            <div className="flex items-center gap-4">
              {/* Avatar */}
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600
                              flex items-center justify-center flex-shrink-0 shadow-md shadow-indigo-200">
                <span className="text-white font-bold text-xl">
                  {profile.email[0].toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-slate-800 truncate">{profile.email}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  Member since {new Date(profile.created_at).toLocaleDateString("en-US", {
                    year: "numeric", month: "long", day: "numeric",
                  })}
                </p>
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3 mt-5">
              <div className="bg-slate-50 rounded-xl px-4 py-3 flex items-center gap-3">
                <MessageSquare size={16} className="text-indigo-400 flex-shrink-0" />
                <div>
                  <p className="text-2xl font-bold text-slate-800 tabular-nums">
                    {profile.total_sessions}
                  </p>
                  <p className="text-xs text-slate-500">Conversations</p>
                </div>
              </div>
              <div className="bg-slate-50 rounded-xl px-4 py-3 flex items-center gap-3">
                <HelpCircle size={16} className="text-violet-400 flex-shrink-0" />
                <div>
                  <p className="text-2xl font-bold text-slate-800 tabular-nums">
                    {profile.total_questions}
                  </p>
                  <p className="text-xs text-slate-500">Questions asked</p>
                </div>
              </div>
            </div>
          </Section>
        )}

        {/* Update email */}
        <Section icon={Mail} title="Email address">
          <form onSubmit={handleEmailSave} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1.5">
                New email address
              </label>
              <input
                type="email"
                required
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="w-full border border-slate-200 rounded-xl px-4 py-2.5 text-sm
                           text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400
                           focus:border-transparent transition-all"
              />
            </div>
            <Feedback {...emailStatus} />
            <button
              type="submit"
              disabled={savingEmail}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500
                         disabled:opacity-60 text-white text-sm font-medium
                         px-5 py-2.5 rounded-xl transition-all duration-150"
            >
              {savingEmail && <Loader2 size={13} className="animate-spin" />}
              {savingEmail ? "Saving…" : "Update email"}
            </button>
          </form>
        </Section>

        {/* Update password */}
        <Section icon={Lock} title="Change password">
          <form onSubmit={handlePasswordSave} className="space-y-3">
            {/* Current password */}
            {[
              { label: "Current password", value: currentPw, setter: setCurrentPw, field: "current" },
              { label: "New password",      value: newPw,     setter: setNewPw,     field: "new"     },
              { label: "Confirm new password", value: confirmPw, setter: setConfirmPw, field: "confirm" },
            ].map(({ label, value, setter, field }) => (
              <div key={field}>
                <label className="block text-xs font-medium text-slate-500 mb-1.5">{label}</label>
                <div className="relative">
                  <input
                    type={showPws[field] ? "text" : "password"}
                    required
                    minLength={field === "current" ? 1 : 8}
                    value={value}
                    onChange={(e) => setter(e.target.value)}
                    className="w-full border border-slate-200 rounded-xl px-4 py-2.5 pr-10 text-sm
                               text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400
                               focus:border-transparent transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => togglePw(field)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400
                               hover:text-slate-600 transition-colors"
                  >
                    {showPws[field] ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>
            ))}
            <Feedback {...pwStatus} />
            <button
              type="submit"
              disabled={savingPw}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500
                         disabled:opacity-60 text-white text-sm font-medium
                         px-5 py-2.5 rounded-xl transition-all duration-150 mt-1"
            >
              {savingPw && <Loader2 size={13} className="animate-spin" />}
              {savingPw ? "Saving…" : "Change password"}
            </button>
          </form>
        </Section>

        {/* Danger zone */}
        <Section icon={Trash2} title="Danger zone">
          <p className="text-sm text-slate-500 mb-4">
            Permanently delete your account and all your conversations. This action cannot be undone.
          </p>
          <button
            onClick={() => setShowDelete(true)}
            className="flex items-center gap-2 bg-red-50 hover:bg-red-100 text-red-600
                       text-sm font-medium px-5 py-2.5 rounded-xl border border-red-200
                       hover:border-red-300 transition-all duration-150"
          >
            <Trash2 size={14} />
            Delete my account
          </button>
        </Section>
      </div>

      {/* Delete confirmation modal */}
      {showDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Overlay */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={() => !deleting && setShowDelete(false)}
          />
          {/* Modal */}
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6 z-10">
            <div className="w-12 h-12 rounded-2xl bg-red-100 flex items-center justify-center mx-auto mb-4">
              <Trash2 size={20} className="text-red-500" />
            </div>
            <h3 className="text-center font-bold text-slate-900 text-lg mb-2">Delete account?</h3>
            <p className="text-center text-sm text-slate-500 mb-6">
              All your conversations, messages and feedback will be permanently deleted.
              This cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDelete(false)}
                disabled={deleting}
                className="flex-1 py-2.5 rounded-xl border border-slate-200 text-sm
                           font-medium text-slate-600 hover:bg-slate-50 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deleting}
                className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-500
                           disabled:opacity-60 text-white text-sm font-medium
                           flex items-center justify-center gap-2 transition-all"
              >
                {deleting && <Loader2 size={13} className="animate-spin" />}
                {deleting ? "Deleting…" : "Yes, delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

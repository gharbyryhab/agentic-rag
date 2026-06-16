import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  User, Mail, Lock, Trash2, LogOut, CheckCircle, AlertCircle,
  Loader2, Eye, EyeOff, MessageSquare, HelpCircle,
  Brain, Sliders, BookOpen, Settings2, ShieldCheck, Sparkles, ChevronDown, ChevronUp,
} from "lucide-react";
import {
  getProfile, updateEmail, updatePassword, deleteAccount,
  getAdminSettings, patchAdminSettings,
} from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

// ── Shared components ─────────────────────────────────────────────────────────

function Section({ icon: Icon, title, badge, children, accent = "indigo" }) {
  const colors = {
    indigo: { bg: "rgba(99,102,241,0.12)", color: "#818cf8", border: "rgba(99,102,241,0.2)" },
    red:    { bg: "rgba(239,68,68,0.1)",   color: "#f87171", border: "rgba(239,68,68,0.15)" },
  };
  const c = colors[accent] ?? colors.indigo;
  return (
    <div className="rounded-2xl overflow-hidden"
         style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="px-6 py-4 flex items-center gap-3"
           style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
             style={{ background: c.bg, border: `1px solid ${c.border}` }}>
          <Icon size={14} style={{ color: c.color }} />
        </div>
        <h2 className="font-semibold text-slate-200 text-sm flex-1">{title}</h2>
        {badge}
      </div>
      <div className="px-6 py-5">{children}</div>
    </div>
  );
}

function Feedback({ type, message }) {
  if (!message) return null;
  const isErr = type === "error";
  return (
    <div className={`flex items-center gap-2 text-sm rounded-xl px-4 py-3 mt-3`}
         style={{
           background: isErr ? "rgba(239,68,68,0.1)" : "rgba(16,185,129,0.1)",
           border: `1px solid ${isErr ? "rgba(239,68,68,0.2)" : "rgba(16,185,129,0.2)"}`,
           color: isErr ? "#fca5a5" : "#6ee7b7",
         }}>
      {isErr ? <AlertCircle size={14} /> : <CheckCircle size={14} />}
      {message}
    </div>
  );
}

function RangeSlider({ label, value, min, max, step = 0.1, onChange, format = (v) => v }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="text-xs font-medium text-slate-500">{label}</label>
        <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-lg"
              style={{ background: "rgba(99,102,241,0.15)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.2)" }}>
          {format(value)}
        </span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
        style={{ background: `linear-gradient(to right, #6366f1 0%, #6366f1 ${((value - min) / (max - min)) * 100}%, rgba(255,255,255,0.1) ${((value - min) / (max - min)) * 100}%, rgba(255,255,255,0.1) 100%)` }}
      />
      <div className="flex justify-between mt-1">
        <span className="text-[10px] text-slate-700">{min}</span>
        <span className="text-[10px] text-slate-700">{max}</span>
      </div>
    </div>
  );
}

const MODEL_OPTIONS = [
  { value: "gemma-4-27b-it",          label: "Gemma 4 27B IT" },
  { value: "gemma-4-9b-it",           label: "Gemma 4 9B IT" },
  { value: "gemini-1.5-flash",        label: "Gemini 1.5 Flash" },
  { value: "gemini-1.5-pro",          label: "Gemini 1.5 Pro" },
  { value: "gemini-2.0-flash",        label: "Gemini 2.0 Flash" },
  { value: "llama-3.3-70b-versatile", label: "Llama 3.3 70B (Groq)" },
  { value: "llama-3.1-8b-instant",    label: "Llama 3.1 8B (Groq)" },
];

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const { addToast }     = useToast();
  const navigate         = useNavigate();
  const isAdmin          = user?.role === "admin";

  // Profile state
  const [profile, setProfile]         = useState(null);
  const [loadingProfile, setLoadingP] = useState(true);
  const [newEmail, setNewEmail]       = useState("");
  const [emailStatus, setEmailStatus] = useState({ type: null, msg: null });
  const [savingEmail, setSavingEmail] = useState(false);
  const [currentPw, setCurrentPw]     = useState("");
  const [newPw, setNewPw]             = useState("");
  const [confirmPw, setConfirmPw]     = useState("");
  const [showPws, setShowPws]         = useState({ current: false, new: false, confirm: false });
  const [pwStatus, setPwStatus]       = useState({ type: null, msg: null });
  const [savingPw, setSavingPw]       = useState(false);
  const [showDelete, setShowDelete]   = useState(false);
  const [deleting, setDeleting]       = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [adminOpen, setAdminOpen]     = useState(true);

  // Admin settings state
  const [loadingSettings, setLoadingS] = useState(isAdmin);
  const [modelName, setModelName]      = useState("gemma-4-27b-it");
  const [temperature, setTemp]         = useState(0.7);
  const [topK, setTopK]                = useState(5);
  const [maxSources, setMaxSources]    = useState(5);
  const [savingSettings, setSavingS]   = useState(false);
  const [settingsStatus, setSettingsS] = useState({ type: null, msg: null });

  // Load data
  useEffect(() => {
    getProfile()
      .then((p) => { setProfile(p); setNewEmail(p.email); })
      .catch(() => addToast("Could not load profile", "error"))
      .finally(() => setLoadingP(false));
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    getAdminSettings()
      .then((s) => { setModelName(s.model_name); setTemp(s.temperature); setTopK(s.top_k); setMaxSources(s.max_sources); })
      .catch(() => addToast("Could not load admin settings", "error"))
      .finally(() => setLoadingS(false));
  }, [isAdmin]);

  // Handlers
  const handleEmailSave = async (e) => {
    e.preventDefault();
    setEmailStatus({ type: null, msg: null });
    if (newEmail === profile?.email) { setEmailStatus({ type: "error", msg: "That's already your current email." }); return; }
    setSavingEmail(true);
    try {
      const updated = await updateEmail(newEmail);
      setProfile(updated);
      setEmailStatus({ type: "success", msg: "Email updated successfully." });
      addToast("Email updated", "success");
    } catch (err) {
      setEmailStatus({ type: "error", msg: err.response?.data?.detail || "Failed to update email." });
    } finally { setSavingEmail(false); }
  };

  const handlePasswordSave = async (e) => {
    e.preventDefault();
    setPwStatus({ type: null, msg: null });
    if (newPw !== confirmPw)  { setPwStatus({ type: "error", msg: "New passwords do not match." }); return; }
    if (newPw.length < 8)     { setPwStatus({ type: "error", msg: "Password must be at least 8 characters." }); return; }
    setSavingPw(true);
    try {
      await updatePassword(currentPw, newPw);
      setPwStatus({ type: "success", msg: "Password updated successfully." });
      setCurrentPw(""); setNewPw(""); setConfirmPw("");
      addToast("Password updated", "success");
    } catch (err) {
      setPwStatus({ type: "error", msg: err.response?.data?.detail || "Failed to update password." });
    } finally { setSavingPw(false); }
  };

  const handleDeleteAccount = async () => {
    setDeleting(true);
    try { await deleteAccount(); logout(); navigate("/login", { replace: true }); }
    catch { addToast("Failed to delete account", "error"); setDeleting(false); setShowDelete(false); setDeleteConfirm(""); }
  };

  const handleSignOut = () => { logout(); navigate("/login", { replace: true }); };
  const togglePw = (f) => setShowPws((p) => ({ ...p, [f]: !p[f] }));

  const handleSettingsSave = async (e) => {
    e.preventDefault();
    setSavingS(true); setSettingsS({ type: null, msg: null });
    try {
      await patchAdminSettings({ model_name: modelName, temperature, top_k: topK, max_sources: maxSources });
      setSettingsS({ type: "success", msg: "Settings saved and hot-reloaded." });
      addToast("Settings saved", "success");
    } catch (err) {
      setSettingsS({ type: "error", msg: err.response?.data?.detail || "Failed to save settings." });
    } finally { setSavingS(false); }
  };

  if (loadingProfile || loadingSettings) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center animate-glow-pulse"
             style={{ background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)" }}>
          <Loader2 size={18} className="text-indigo-400 animate-spin" />
        </div>
        <span className="text-sm text-slate-500">Loading settings…</span>
      </div>
    );
  }

  const pwFields = [
    { label: "Current password",    value: currentPw, setter: setCurrentPw, field: "current" },
    { label: "New password",         value: newPw,     setter: setNewPw,     field: "new"     },
    { label: "Confirm new password", value: confirmPw, setter: setConfirmPw, field: "confirm" },
  ];

  return (
    <div className="h-full overflow-y-auto" style={{ background: "#08091a" }}>
      <div className="max-w-2xl mx-auto px-6 py-8 space-y-5">

        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-2">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Sparkles size={12} className="text-indigo-400" />
              <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-[0.15em]">Account</span>
            </div>
            <h1 className="text-xl font-bold text-white">Settings</h1>
            <p className="text-sm text-slate-600 mt-0.5">Manage your profile &amp; preferences</p>
          </div>
          <button onClick={handleSignOut}
            className="flex items-center gap-2 text-sm font-medium transition-all duration-150 px-3 py-2 rounded-xl
                       text-slate-600 hover:text-red-400"
            style={{ border: "1px solid rgba(255,255,255,0.07)" }}
            onMouseEnter={e => { e.currentTarget.style.background = "rgba(239,68,68,0.08)"; e.currentTarget.style.borderColor = "rgba(239,68,68,0.2)"; }}
            onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)"; }}
          >
            <LogOut size={13} />
            Sign out
          </button>
        </div>

        {/* Account overview */}
        {profile && (
          <Section icon={User} title="Account overview">
            <div className="flex items-center gap-4">
              {/* Avatar */}
              <div className="relative flex-shrink-0">
                <div className="absolute inset-0 rounded-2xl blur-xl opacity-60 animate-glow-pulse"
                     style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)" }} />
                <div className="relative w-16 h-16 rounded-2xl flex items-center justify-center font-black text-2xl"
                     style={{ background: "linear-gradient(135deg, rgba(79,70,229,0.5), rgba(124,58,237,0.5))", border: "1.5px solid rgba(99,102,241,0.5)", color: "#e0e7ff", boxShadow: "0 0 30px rgba(99,102,241,0.3), inset 0 1px 0 rgba(255,255,255,0.1)" }}>
                  {profile.email[0].toUpperCase()}
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-semibold text-white truncate">{profile.email}</p>
                  <span className={profile.role === "admin" ? "badge-indigo" : "badge-slate"}>
                    {profile.role === "admin" ? "✦ Admin" : "User"}
                  </span>
                </div>
                <p className="text-xs text-slate-600 mt-0.5">
                  Member since {new Date(profile.created_at).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" })}
                </p>
              </div>
            </div>

            {/* Stats mini row */}
            <div className="grid grid-cols-2 gap-3 mt-5">
              {[
                { icon: MessageSquare, label: "Conversations",  value: profile.total_sessions,  color: "#818cf8", bg: "rgba(99,102,241,0.1)" },
                { icon: HelpCircle,    label: "Questions asked", value: profile.total_questions, color: "#c4b5fd", bg: "rgba(139,92,246,0.1)" },
              ].map(({ icon: Icon, label, value, color, bg }) => (
                <div key={label} className="rounded-xl px-4 py-3 flex items-center gap-3"
                     style={{ background: bg, border: "1px solid rgba(255,255,255,0.06)" }}>
                  <Icon size={15} style={{ color }} className="flex-shrink-0" />
                  <div>
                    <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
                    <p className="text-xs text-slate-600">{label}</p>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Email */}
        <Section icon={Mail} title="Email address">
          <form onSubmit={handleEmailSave} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">New email</label>
              <input type="email" required value={newEmail} onChange={(e) => setNewEmail(e.target.value)}
                className="input" placeholder="you@example.com" />
            </div>
            <Feedback type={emailStatus.type} message={emailStatus.msg} />
            <button type="submit" disabled={savingEmail} className="btn-primary flex items-center gap-2">
              {savingEmail && <Loader2 size={13} className="animate-spin" />}
              {savingEmail ? "Saving…" : "Update email"}
            </button>
          </form>
        </Section>

        {/* Password */}
        <Section icon={Lock} title="Change password">
          <form onSubmit={handlePasswordSave} className="space-y-3">
            {pwFields.map(({ label, value, setter, field }) => (
              <div key={field}>
                <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wider">{label}</label>
                <div className="relative">
                  <input type={showPws[field] ? "text" : "password"}
                    required minLength={field === "current" ? 1 : 8}
                    value={value} onChange={(e) => setter(e.target.value)}
                    placeholder="••••••••" className="input pr-11" />
                  <button type="button" onClick={() => togglePw(field)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-300 transition-colors">
                    {showPws[field] ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>
            ))}
            <Feedback type={pwStatus.type} message={pwStatus.msg} />
            <button type="submit" disabled={savingPw} className="btn-primary flex items-center gap-2 mt-1">
              {savingPw && <Loader2 size={13} className="animate-spin" />}
              {savingPw ? "Saving…" : "Change password"}
            </button>
          </form>
        </Section>

        {/* Admin section */}
        {isAdmin && (
          <>
            <button type="button" onClick={() => setAdminOpen(o => !o)}
              className="w-full flex items-center gap-2 pt-2 group">
              <div className="flex-1 h-px" style={{ background: "rgba(99,102,241,0.2)" }} />
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full transition-all duration-150"
                   style={{ background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)" }}
                   onMouseEnter={e => e.currentTarget.style.background = "rgba(99,102,241,0.18)"}
                   onMouseLeave={e => e.currentTarget.style.background = "rgba(99,102,241,0.1)"}>
                <ShieldCheck size={11} className="text-indigo-400" />
                <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-[0.12em]">Admin Configuration</span>
                {adminOpen ? <ChevronUp size={10} className="text-indigo-500" /> : <ChevronDown size={10} className="text-indigo-500" />}
              </div>
              <div className="flex-1 h-px" style={{ background: "rgba(99,102,241,0.2)" }} />
            </button>

            {adminOpen && <form onSubmit={handleSettingsSave} className="space-y-5">

              <Section icon={Brain} title="Language model"
                badge={<span className="badge-indigo">Admin</span>}>
                <div>
                  <label className="block text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wider">Active model</label>
                  <select value={modelName} onChange={(e) => setModelName(e.target.value)}
                    className="input appearance-none cursor-pointer"
                    style={{ color: "#e2e8f0" }}>
                    {MODEL_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value} style={{ background: "#0f1022" }}>{o.label}</option>
                    ))}
                    {!MODEL_OPTIONS.find((o) => o.value === modelName) && (
                      <option value={modelName} style={{ background: "#0f1022" }}>{modelName}</option>
                    )}
                  </select>
                  <p className="text-[11px] text-slate-700 mt-1.5">
                    Make sure the model is available on your configured provider.
                  </p>
                </div>
              </Section>

              <Section icon={Sliders} title="Generation parameters"
                badge={<span className="badge-indigo">Admin</span>}>
                <div className="space-y-5">
                  <RangeSlider label="Temperature" value={temperature} min={0} max={2} step={0.05}
                    onChange={setTemp} format={(v) => v.toFixed(2)} />
                  <p className="text-[11px] text-slate-700 -mt-3">Higher = more creative. Lower = more deterministic.</p>
                </div>
              </Section>

              <Section icon={BookOpen} title="Retrieval parameters"
                badge={<span className="badge-indigo">Admin</span>}>
                <div className="space-y-5">
                  <RangeSlider label="Top-K (chunks retrieved)" value={topK} min={1} max={20} step={1} onChange={setTopK} format={(v) => v} />
                  <RangeSlider label="Max sources shown" value={maxSources} min={1} max={10} step={1} onChange={setMaxSources} format={(v) => v} />
                </div>
              </Section>

              <Feedback type={settingsStatus.type} message={settingsStatus.msg} />

              <button type="submit" disabled={savingSettings} className="btn-primary flex items-center gap-2">
                {savingSettings && <Loader2 size={13} className="animate-spin" />}
                <Settings2 size={13} />
                {savingSettings ? "Saving…" : "Save & hot-reload"}
              </button>
            </form>}
          </>
        )}

        {/* Danger zone */}
        <Section icon={Trash2} title="Danger zone" accent="red">
          <p className="text-sm text-slate-500 mb-4">
            Permanently delete your account and all your conversations. This cannot be undone.
          </p>
          <button onClick={() => setShowDelete(true)} className="btn-danger flex items-center gap-2">
            <Trash2 size={13} />
            Delete my account
          </button>
        </Section>

        <div className="h-4" />
      </div>

      {/* Delete modal */}
      {showDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 backdrop-blur-sm" style={{ background: "rgba(0,0,0,0.75)" }}
            onClick={() => !deleting && (setShowDelete(false), setDeleteConfirm(""))} />
          <div className="relative w-full max-w-sm mx-4 p-6 z-10 rounded-2xl animate-slide-up space-y-4"
               style={{ background: "#0f1022", border: "1px solid rgba(239,68,68,0.2)", boxShadow: "0 25px 80px rgba(0,0,0,0.8), 0 0 0 1px rgba(239,68,68,0.1)" }}>
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto"
                 style={{ background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.25)" }}>
              <Trash2 size={20} className="text-red-400" />
            </div>
            <div className="text-center">
              <h3 className="font-bold text-white text-lg">Delete account?</h3>
              <p className="text-sm text-slate-500 mt-1.5">
                All conversations, messages, and feedback will be permanently erased.
              </p>
            </div>
            <div>
              <label className="block text-[10px] font-bold text-slate-600 uppercase tracking-wider mb-2">
                Type <span className="text-red-400 font-mono">DELETE</span> to confirm
              </label>
              <input type="text" value={deleteConfirm}
                onChange={e => setDeleteConfirm(e.target.value)}
                placeholder="DELETE"
                className="w-full px-3 py-2.5 rounded-xl text-sm text-slate-200 transition-all duration-150"
                style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", caretColor: "#f87171" }}
                onFocus={e => e.target.style.borderColor = "rgba(239,68,68,0.45)"}
                onBlur={e  => e.target.style.borderColor = "rgba(239,68,68,0.2)"} />
            </div>
            <div className="flex gap-3">
              <button onClick={() => { setShowDelete(false); setDeleteConfirm(""); }} disabled={deleting}
                className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all text-slate-400 hover:text-slate-200"
                style={{ border: "1px solid rgba(255,255,255,0.1)" }}>
                Cancel
              </button>
              <button onClick={handleDeleteAccount}
                disabled={deleting || deleteConfirm !== "DELETE"}
                className="flex-1 py-2.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ background: "rgba(239,68,68,0.18)", border: "1px solid rgba(239,68,68,0.35)", color: "#fca5a5" }}
                onMouseEnter={e => { if (!e.currentTarget.disabled) e.currentTarget.style.background = "rgba(239,68,68,0.3)"; }}
                onMouseLeave={e => e.currentTarget.style.background = "rgba(239,68,68,0.18)"}
              >
                {deleting && <Loader2 size={13} className="animate-spin" />}
                {deleting ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

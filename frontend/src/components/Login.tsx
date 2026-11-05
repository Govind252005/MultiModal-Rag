import { useState, useEffect, useRef } from "react";
import type { FormEvent } from "react";
import {
  Mail,
  Lock,
  Loader2,
  LogIn,
  UserPlus,
  Eye,
  EyeOff,
  Brain,
  FileText,
  Mic,
  Shield,
  Zap,
  CheckCircle2,
  ImageIcon,
} from "lucide-react";
import * as api from "../api";
import type { AuthUser } from "../types";

/* ─── animated dot-network canvas ─── */
function ParticleCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    let raf: number;

    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    type Dot = { x: number; y: number; r: number; vx: number; vy: number; a: number };
    const dots: Dot[] = Array.from({ length: 55 }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.6 + 0.4,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      a: Math.random() * 0.5 + 0.15,
    }));

    const tick = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const d of dots) {
        d.x += d.vx;
        d.y += d.vy;
        if (d.x < 0 || d.x > canvas.width) d.vx *= -1;
        if (d.y < 0 || d.y > canvas.height) d.vy *= -1;
        ctx.beginPath();
        ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(125,211,252,${d.a})`;
        ctx.fill();
      }
      for (let i = 0; i < dots.length; i++) {
        for (let j = i + 1; j < dots.length; j++) {
          const dx = dots[i].x - dots[j].x;
          const dy = dots[i].y - dots[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 130) {
            ctx.beginPath();
            ctx.moveTo(dots[i].x, dots[i].y);
            ctx.lineTo(dots[j].x, dots[j].y);
            ctx.strokeStyle = `rgba(125,211,252,${0.18 * (1 - dist / 130)})`;
            ctx.lineWidth = 0.7;
            ctx.stroke();
          }
        }
      }
      raf = requestAnimationFrame(tick);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      className="absolute inset-0 w-full h-full"
      style={{ opacity: 0.6 }}
    />
  );
}

/* ─── feature card shown on left hero panel ─── */
function FeatureCard({
  icon: Icon,
  color,
  title,
  desc,
}: {
  icon: React.ElementType;
  color: string;
  title: string;
  desc: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm px-4 py-3 hover:bg-white/10 transition-all duration-300">
      <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${color}`}>
        <Icon className="h-4 w-4 text-white" />
      </div>
      <div>
        <p className="text-sm font-semibold text-white">{title}</p>
        <p className="text-xs text-slate-400 leading-relaxed">{desc}</p>
      </div>
    </div>
  );
}

/* ─── input field with icon ─── */
function InputField({
  label,
  icon: Icon,
  type,
  value,
  onChange,
  placeholder,
  autoComplete,
  rightEl,
}: {
  label: string;
  icon: React.ElementType;
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  autoComplete: string;
  rightEl?: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-slate-400 tracking-wide uppercase">
        {label}
      </label>
      <div className="group relative flex items-center rounded-xl border border-slate-700 bg-slate-800/70 px-4 transition-all duration-200 focus-within:border-cyan-500 focus-within:ring-2 focus-within:ring-cyan-500/20">
        <Icon className="h-4 w-4 shrink-0 text-slate-500 transition-colors group-focus-within:text-cyan-400" />
        <input
          type={type}
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          className="ml-3 w-full bg-transparent py-3.5 text-sm text-slate-100 outline-none placeholder:text-slate-600"
        />
        {rightEl}
      </div>
    </div>
  );
}

/* ─── main login component ─── */
export default function Login({ onAuthed }: { onAuthed: (user: AuthUser) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // tiny delay to trigger the CSS entrance animation
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const res =
        mode === "login"
          ? await api.login(email.trim(), password)
          : await api.register(email.trim(), password);
      api.setToken(res.token);
      if (mode === "register") {
        setSuccess("Account created! Signing you in…");
        await new Promise((r) => setTimeout(r, 700));
      }
      onAuthed(res.user);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function switchMode() {
    setMode((m) => (m === "login" ? "register" : "login"));
    setError(null);
    setSuccess(null);
  }

  return (
    <div className="min-h-screen w-full overflow-hidden bg-slate-950">
      <div className="grid min-h-screen lg:grid-cols-[55%_45%]">

        {/* ═══════════ LEFT HERO PANEL ═══════════ */}
        <div className="relative hidden lg:flex flex-col justify-between overflow-hidden p-14">

          {/* deep gradient base */}
          <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-[#040d1e] to-[#060f28]" />

          {/* glowing orbs */}
          <div className="absolute -top-32 -left-20 h-96 w-96 rounded-full bg-cyan-600/20 blur-[100px] animate-pulse" />
          <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-blue-600/20 blur-[80px] animate-pulse" style={{ animationDelay: "1.5s" }} />
          <div className="absolute top-1/2 left-1/3 h-64 w-64 -translate-y-1/2 rounded-full bg-sky-500/10 blur-[60px]" />

          {/* particle canvas */}
          <ParticleCanvas />

          {/* content */}
          <div className="relative z-10">
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-300">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
              Fully offline · Your data stays local
            </div>
          </div>

          <div className="relative z-10 space-y-6">
            {/* headline */}
            <div>
              <h1 className="text-5xl font-extrabold leading-tight tracking-tight text-white">
                Your private
                <br />
                <span className="bg-gradient-to-r from-cyan-400 via-sky-300 to-blue-400 bg-clip-text text-transparent">
                  AI Research
                </span>
                <br />
                assistant.
              </h1>
              <p className="mt-4 max-w-sm text-sm leading-7 text-slate-400">
                Upload PDFs, images, audio. Ask questions. Get grounded, cited answers — all running on your own machine.
              </p>
            </div>

            {/* feature cards */}
            <div className="grid gap-2.5 max-w-sm">
              <FeatureCard
                icon={FileText}
                color="bg-gradient-to-br from-cyan-500 to-sky-600"
                title="Documents & PDFs"
                desc="Page-level citations, semantic chunking"
              />
              <FeatureCard
                icon={ImageIcon}
                color="bg-gradient-to-br from-violet-500 to-purple-600"
                title="Images & Screenshots"
                desc="Enterprise OCR + CLIP visual retrieval"
              />
              <FeatureCard
                icon={Mic}
                color="bg-gradient-to-br from-emerald-500 to-teal-600"
                title="Audio & Recordings"
                desc="Whisper transcription with timecodes"
              />
              <FeatureCard
                icon={Brain}
                color="bg-gradient-to-br from-orange-500 to-rose-500"
                title="Local LLM (Ollama)"
                desc="Qwen3 · 100% offline · no API keys"
              />
            </div>
          </div>

          {/* bottom trust strip */}
          <div className="relative z-10 flex items-center gap-6 text-xs text-slate-500">
            <span className="flex items-center gap-1.5"><Shield className="h-3.5 w-3.5 text-emerald-400" /> Private by default</span>
            <span className="flex items-center gap-1.5"><Zap className="h-3.5 w-3.5 text-amber-400" /> GPU accelerated</span>
            <span className="flex items-center gap-1.5"><CheckCircle2 className="h-3.5 w-3.5 text-cyan-400" /> Open source</span>
          </div>
        </div>

        {/* ═══════════ RIGHT FORM PANEL ═══════════ */}
        <div className="flex items-center justify-center bg-[#080f1e] px-6 py-12">
          <div
            className="w-full max-w-sm transition-all duration-700"
            style={{
              opacity: mounted ? 1 : 0,
              transform: mounted ? "translateY(0)" : "translateY(24px)",
            }}
          >

            {/* logo + app name */}
            <div className="mb-10 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg shadow-cyan-500/30">
                <Brain className="h-8 w-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-white tracking-tight">
                Multimodal RAG
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                {mode === "login" ? "Welcome back — sign in to continue" : "Create your private workspace"}
              </p>
            </div>

            {/* mode tabs */}
            <div className="mb-6 flex rounded-xl border border-slate-800 bg-slate-900 p-1">
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => { setMode(m); setError(null); setSuccess(null); }}
                  className={`flex-1 rounded-lg py-2 text-sm font-medium transition-all duration-200 ${
                    mode === m
                      ? "bg-gradient-to-r from-cyan-600 to-blue-600 text-white shadow-md"
                      : "text-slate-500 hover:text-slate-300"
                  }`}
                >
                  {m === "login" ? "Sign In" : "Create Account"}
                </button>
              ))}
            </div>

            {/* form card */}
            <form
              onSubmit={submit}
              className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-2xl backdrop-blur-sm"
            >
              <InputField
                label="Email address"
                icon={Mail}
                type="email"
                value={email}
                onChange={setEmail}
                placeholder="you@example.com"
                autoComplete="email"
              />

              <InputField
                label="Password"
                icon={Lock}
                type={showPw ? "text" : "password"}
                value={password}
                onChange={setPassword}
                placeholder={mode === "register" ? "Min. 6 characters" : "Your password"}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                rightEl={
                  <button
                    type="button"
                    tabIndex={-1}
                    onClick={() => setShowPw((v) => !v)}
                    className="ml-2 shrink-0 text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                }
              />

              {/* error */}
              {error && (
                <div className="flex items-start gap-2 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2.5">
                  <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-red-400 mt-1.5" />
                  <p className="text-xs text-red-300 leading-relaxed">{error}</p>
                </div>
              )}

              {/* success */}
              {success && (
                <div className="flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-3 py-2.5">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                  <p className="text-xs text-emerald-300">{success}</p>
                </div>
              )}

              {/* submit button */}
              <button
                type="submit"
                disabled={busy}
                className="relative w-full overflow-hidden rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 py-3.5 text-sm font-semibold text-white shadow-lg shadow-cyan-700/30 transition-all duration-200 hover:from-cyan-500 hover:to-blue-500 hover:shadow-cyan-600/40 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                <span className="flex items-center justify-center gap-2">
                  {busy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : mode === "login" ? (
                    <LogIn className="h-4 w-4" />
                  ) : (
                    <UserPlus className="h-4 w-4" />
                  )}
                  {busy ? "Please wait…" : mode === "login" ? "Sign In" : "Create Account"}
                </span>
              </button>
            </form>

            {/* switch mode link */}
            <p className="mt-5 text-center text-xs text-slate-600">
              {mode === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
              <button
                type="button"
                onClick={switchMode}
                className="font-semibold text-cyan-500 hover:text-cyan-400 transition-colors hover:underline"
              >
                {mode === "login" ? "Create one free" : "Sign in"}
              </button>
            </p>

            {/* bottom note */}
            <p className="mt-6 text-center text-xs text-slate-700 leading-relaxed">
              All data is stored locally on your machine.
              <br />No cloud. No tracking. No telemetry.
            </p>
          </div>
        </div>

      </div>
    </div>
  );
}

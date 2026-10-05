import { useCallback, useEffect, useState } from "react";
import { PanelRight, Loader2 } from "lucide-react";

import * as api from "./api";
import type {
  ChatMessage,
  Citation,
  HealthResponse,
  LibraryFile,
  SessionSummary,
  Scope,
  AuthUser,
  ProviderName,
  ActiveProviderResponse,
} from "./types";


import Login from "./components/Login";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import LlmBanner from "./components/LlmBanner";
import ChatPanel from "./components/ChatPanel";
import Composer from "./components/Composer";
import SourcesPanel from "./components/SourcesPanel";
import LibraryPanel from "./components/LibraryPanel";
import Toast from "./components/Toast";

function uid() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}
const DEFAULT_SCOPE: Scope = { modality: "all", files: [] };

export default function App() {
  // Theme -------------------------------------------------------------------
  const [theme, setTheme] = useState<"light" | "dark">(() =>
    document.documentElement.classList.contains("dark") ? "dark" : "light",
  );
  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", next === "dark");
      try {
        localStorage.setItem("theme", next);
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  // Auth --------------------------------------------------------------------
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  // App state ---------------------------------------------------------------
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [files, setFiles] = useState<LibraryFile[]>([]);
  const [filesLoading] = useState(false);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [flashIndex, setFlashIndex] = useState<number | null>(null);
  const [scope, setScope] = useState<Scope>(DEFAULT_SCOPE);
  const [topK, setTopK] = useState(5);
  const [provider, setProvider] = useState<ProviderName>("ollama");
  const [activeProviderInfo, setActiveProviderInfo] = useState<ActiveProviderResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("sidebar-collapsed") === "1";
    } catch {
      return false;
    }
  });
  const [modelsCollapsed, setModelsCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("models-collapsed") === "1";
    } catch {
      return false;
    }
  });
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Loaders -----------------------------------------------------------------
  const loadHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      setHealth(await api.health());
    } catch {
      setHealth(null);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await api.listSessions());
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  // Validate an existing token on first load.
  useEffect(() => {
    loadHealth();
    (async () => {
      if (api.hasToken()) {
        try {
          setUser(await api.me());
        } catch {
          setUser(null);
        }
      }
      setAuthChecking(false);
    })();
  }, [loadHealth]);

  // When logged in, load the user's chats. Also react to token expiry.
  useEffect(() => {
    if (user) loadSessions();
  }, [user, loadSessions]);

  // Spec §51A.11: the backend is authoritative for "which provider is
  // currently active" — read it back on login instead of always assuming
  // Ollama, so a provider switch from a previous session/device is
  // reflected here too.
  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const active = await api.getActiveProvider();
        setProvider(active.provider);
        setActiveProviderInfo(active);
      } catch {
        /* fall back to the local default already in state */
      }
    })();
  }, [user]);


  useEffect(() => {
    const onExpired = () => {
      setUser(null);
      resetLocal();
    };
    window.addEventListener("auth-expired", onExpired);
    return () => window.removeEventListener("auth-expired", onExpired);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("sidebar-collapsed", sidebarCollapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [sidebarCollapsed]);

  useEffect(() => {
    try {
      localStorage.setItem("models-collapsed", modelsCollapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [modelsCollapsed]);

  function resetLocal() {
    setCurrentId(null);
    setMessages([]);
    setFiles([]);
    setCitations([]);
    setSessions([]);
    setScope(DEFAULT_SCOPE);
  }
  function requestLogout() {
    setShowLogoutConfirm(true);
  }

  function confirmLogout() {
    setShowLogoutConfirm(false);
    api.logout().catch(() => {
      /* best-effort revocation — always proceed to clear local state */
    });
    setUser(null);
    resetLocal();
  }

  // Ensure a session exists (lazy) ------------------------------------------
  const ensureSession = useCallback(async (): Promise<string> => {
    if (currentId) return currentId;
    const s = await api.createSession("New chat");
    setCurrentId(s.id);
    loadSessions();
    return s.id;
  }, [currentId, loadSessions]);

  // Message helpers ---------------------------------------------------------
  function addMessage(msg: ChatMessage) {
    setMessages((p) => [...p, msg]);
    return msg.id;
  }
  function updateMessage(
    id: string,
    patch: Partial<ChatMessage> | ((prev: ChatMessage) => Partial<ChatMessage>),
  ) {
    setMessages((p) =>
      p.map((m) => (m.id === id ? { ...m, ...(typeof patch === "function" ? patch(m) : patch) } : m)),
    );
  }
  function handleCitationClick(index: number) {
    setSourcesOpen(true);
    setFlashIndex(null);
    requestAnimationFrame(() => setFlashIndex(index));
  }

  // Sessions ----------------------------------------------------------------
  function newChat() {
    setCurrentId(null);
    setMessages([]);
    setFiles([]);
    setCitations([]);
    setScope(DEFAULT_SCOPE);
    setSidebarOpen(false);
  }
  const selectSession = useCallback(async (id: string) => {
    setSidebarOpen(false);
    try {
      const s = await api.getSession(id);
      setCurrentId(id);
      setFiles(s.files || []);
      setScope(DEFAULT_SCOPE);
      setMessages(
        (s.messages || []).map((m) => ({
          id: uid(),
          role: m.role,
          text: m.text,
          citations: m.citations,
          usedLlm: m.usedLlm,
          contextLabel: m.contextLabel,
          contextValue: m.contextValue,
        })),
      );
      const last = [...(s.messages || [])]
        .reverse()
        .find((m) => m.citations?.length);
      setCitations(last?.citations || []);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);
  async function deleteSession(id: string) {
    try {
      await api.deleteSession(id);
      await loadSessions();
      if (id === currentId) newChat();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  // Library -----------------------------------------------------------------
  const ingestFiles = useCallback(
    async (list: File[]) => {
      const sid = await ensureSession();
      const res = await api.ingest(sid, list);
      setFiles(res.files);
      loadSessions();
      loadHealth();
      const failed = res.ingested.filter((r) => r.error);
      if (failed.length)
        setError(
          `Some files failed: ${failed.map((f) => `${f.file} (${f.error})`).join(", ")}`,
        );
    },
    [ensureSession, loadSessions, loadHealth],
  );
  const deleteFile = useCallback(
    async (name: string) => {
      if (!currentId) return;
      const res = await api.deleteFile(currentId, name);
      setFiles(res.files);
      setScope((s) => ({ ...s, files: s.files.filter((f) => f !== name) }));
      loadHealth();
    },
    [currentId, loadHealth],
  );

  // Queries -----------------------------------------------------------------
  // Explicit activation (spec §51A.6/§51A.13): selecting a provider in the
  // UI calls the backend's activation endpoint and only updates local state
  // once the backend confirms it — never assume the switch worked and never
  // leave the UI and backend disagreeing about which provider is active.
  async function selectProvider(p: ProviderName, model?: string) {
    const previous = provider;
    try {
      const active = await api.activateProvider(p, model);
      setProvider(active.provider);
      setActiveProviderInfo(active);
    } catch (err) {
      setError((err as Error).message);
      setProvider(previous);
    }
  }


  async function handleTextQuery(text: string) {
    const sid = await ensureSession();
    addMessage({ id: uid(), role: "user", text });
    const aId = addMessage({
      id: uid(),
      role: "assistant",
      text: "",
      loading: true,
    });
    setBusy(true);

    let streamedAny = false;
    let finalCitations: Citation[] = [];

    try {
      await api.queryStream(sid, text, topK, scope.modality, scope.files, provider, {
        onCitations: (c) => {
          finalCitations = c;
        },
        onDelta: (delta) => {
          streamedAny = true;
          updateMessage(aId, (prev) => ({
            text: (prev.text || "") + delta,
            loading: false,
          }));
        },
        onDone: (info) => {
          updateMessage(aId, {
            citations: finalCitations,
            usedLlm: info.used_llm,
            loading: false,
          });
          setCitations(finalCitations);
          loadSessions();
        },
        onError: (err) => {
          throw err;
        },
      });
    } catch (err) {
      if (streamedAny) {
        // Streaming started but broke mid-way — leave whatever text arrived
        // rather than discarding it, and surface the error separately.
        updateMessage(aId, { loading: false });
        setError((err as Error).message);
      } else {
        // Streaming endpoint never produced anything (older backend, network
        // hiccup, etc.) — fall back to the blocking endpoint so the person
        // still gets an answer instead of just an error.
        try {
          const res = await api.query(sid, text, topK, scope.modality, scope.files, provider);
          updateMessage(aId, {
            text: res.answer,
            citations: res.citations,
            usedLlm: res.used_llm,
            faithfulnessWarning: res.faithfulness_warning,
            loading: false,
          });
          setCitations(res.citations);
          loadSessions();
        } catch (fallbackErr) {
          updateMessage(aId, {
            text: "Sorry, that query failed. Check the backend and try again.",
            loading: false,
          });
          setError((fallbackErr as Error).message);
        }
      }
    } finally {
      setBusy(false);
    }
  }
  async function handleImageQuery(file: File) {
    const sid = await ensureSession();
    const imageUrl = URL.createObjectURL(file);
    addMessage({
      id: uid(),
      role: "user",
      text: `[Image query: ${file.name}]`,
      imageUrl,
    });
    const aId = addMessage({
      id: uid(),
      role: "assistant",
      text: "",
      loading: true,
    });
    setBusy(true);
    try {
      const res = await api.queryImage(sid, file, topK, scope.files, provider);
      updateMessage(aId, {
        text: res.answer,
        citations: res.citations,
        usedLlm: res.used_llm,
        faithfulnessWarning: res.faithfulness_warning,
        loading: false,
        contextLabel: "Detected in image",
        contextValue: res.query_caption || res.query_ocr || "(none)",
      });
      setCitations(res.citations);
      loadSessions();
    } catch (err) {
      updateMessage(aId, {
        text: "Sorry, the image query failed.",
        loading: false,
      });
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function handleAudioQuery(file: File) {
    const sid = await ensureSession();
    addMessage({
      id: uid(),
      role: "user",
      text: `[Audio query: ${file.name}]`,
    });
    const aId = addMessage({
      id: uid(),
      role: "assistant",
      text: "",
      loading: true,
    });
    setBusy(true);
    try {
      const res = await api.queryAudio(sid, file, topK, scope.files, provider);
      updateMessage(aId, {
        text: res.answer,
        citations: res.citations,
        usedLlm: res.used_llm,
        faithfulnessWarning: res.faithfulness_warning,
        loading: false,
        contextLabel: "Transcript",
        contextValue: res.transcript || "(no speech)",
      });
      setCitations(res.citations);
      loadSessions();
    } catch (err) {
      updateMessage(aId, {
        text: "Sorry, the audio query failed.",
        loading: false,
      });
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const transcribeBlob = useCallback(
    async (blob: Blob): Promise<string> => {
      const sid = await ensureSession();
      const { text } = await api.transcribe(sid, blob);
      return text;
    },
    [ensureSession],
  );

  // Render ------------------------------------------------------------------
  if (authChecking) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <Loader2 className="h-6 w-6 animate-spin text-accent-500" />
      </div>
    );
  }
  if (!user) return <Login onAuthed={setUser} />;

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      <Sidebar
        sessions={sessions}
        currentId={currentId}
        onNew={newChat}
        onSelect={selectSession}
        onDelete={deleteSession}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        provider={provider}
        onSelectProvider={selectProvider}
        onError={setError}
        collapsed={sidebarCollapsed}
        modelsCollapsed={modelsCollapsed}
        onToggleCollapse={() => {
          if (window.innerWidth < 768) {
            setSidebarOpen((prev) => !prev);
            return;
          }
          setSidebarCollapsed((prev) => !prev);
        }}
        onToggleModels={() => setModelsCollapsed((prev) => !prev)}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header
          healthData={health}
          activeProvider={activeProviderInfo}
          loading={healthLoading}
          onRefresh={loadHealth}
          onOpenLibrary={() => setLibraryOpen(true)}
          onOpenSidebar={() => setSidebarOpen(true)}
          theme={theme}
          onToggleTheme={toggleTheme}
          user={user}
          onRequestLogout={requestLogout}
        />

        {health && !health.llm_available && <LlmBanner />}

        <div className="flex min-h-0 flex-1">
          <div className="flex min-w-0 flex-1 flex-col">
            <ChatPanel
              messages={messages}
              onCitationClick={handleCitationClick}
            />
            <Composer
              onSubmitText={handleTextQuery}
              onImageQuery={handleImageQuery}
              onAudioQuery={handleAudioQuery}
              transcribeBlob={transcribeBlob}
              onError={setError}
              busy={busy}
              scope={scope}
              setScope={setScope}
              files={files}
              topK={topK}
              setTopK={setTopK}
            />
          </div>

          <SourcesPanel
            citations={citations}
            flashIndex={flashIndex}
            onError={setError}
            open={sourcesOpen}
            onClose={() => setSourcesOpen(false)}
          />
        </div>
      </div>

      {citations.length > 0 && (
        <button
          onClick={() => setSourcesOpen(true)}
          className="fixed bottom-24 right-4 z-20 flex items-center gap-1.5 rounded-full bg-accent-600 px-4 py-2.5 text-sm font-medium text-white shadow-lg lg:hidden"
        >
          <PanelRight className="h-4 w-4" /> Sources ({citations.length})
        </button>
      )}

      <LibraryPanel
        open={libraryOpen}
        onClose={() => setLibraryOpen(false)}
        files={files}
        filesLoading={filesLoading}
        onIngest={ingestFiles}
        onDeleteFile={deleteFile}
        onError={setError}
      />
      {showLogoutConfirm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50 px-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-slate-800 dark:bg-slate-900">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              Log out?
            </h3>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              Do you really want to log out?
            </p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="rounded-2xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                No
              </button>
              <button
                onClick={confirmLogout}
                className="rounded-2xl bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Yes
              </button>
            </div>
          </div>
        </div>
      )}
      <Toast message={error} onClose={() => setError(null)} />
    </div>
  );
}

import { useCallback, useEffect, useState, useRef, useMemo } from "react";
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
  AppView,
} from "./types";

import { AppShell } from "./components/layout/AppShell";
import { LandingPage } from "./pages/LandingPage";
import { AuthPage } from "./pages/AuthPage";
import { DashboardView } from "./pages/DashboardView";

import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import LlmBanner from "./components/LlmBanner";
import ChatPanel from "./components/ChatPanel";
import Composer from "./components/Composer";
import SourcesPanel from "./components/SourcesPanel";
import LibraryPanel from "./components/LibraryPanel";
import DocumentViewer from "./components/DocumentViewer";
import Toast from "./components/Toast";
import { DocumentManagement } from "./components/DocumentManagement";
import { CollectionManagement } from "./components/CollectionManagement";
import { ModelSettingsView } from "./components/ModelSettingsView";
import { EnterpriseAdminView } from "./components/EnterpriseAdminView";

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
  const [view, setView] = useState<AppView>(() => {
    try {
      if (window.location.pathname === '/landing') return 'landing';
      if (!api.hasToken()) return 'landing';
    } catch {
      /* ignore */
    }
    return 'dashboard';
  });
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
  const [explicitQuery, setExplicitQuery] = useState<string>('');
  const [explicitAnswer, setExplicitAnswer] = useState<string>('');
  const [flashIndex, setFlashIndex] = useState<number | null>(null);
  const [scope, setScope] = useState<Scope>(DEFAULT_SCOPE);
  const [topK, setTopK] = useState(5);
  const [provider, setProvider] = useState<ProviderName>("ollama");
  const [activeProviderInfo, setActiveProviderInfo] = useState<ActiveProviderResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const abortCtrlRef = useRef<AbortController | null>(null);

  function stopGeneration() {
    if (abortCtrlRef.current) {
      abortCtrlRef.current.abort();
      abortCtrlRef.current = null;
    }
    setBusy(false);
  }

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
  const [viewerOpen, setViewerOpen] = useState(false);
  const [activeDocument, setActiveDocument] = useState<string>('');
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [splitRatio, setSplitRatio] = useState<number>(50);
  const [error, setError] = useState<string | null>(null);

  const lastUserQuery = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'user') return messages[i].text;
    }
    return '';
  }, [messages]);

  const lastAssistantAnswer = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return messages[i].text;
    }
    return '';
  }, [messages]);

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

  // Load the most recent session's document library so the Dashboard displays genuine files
  useEffect(() => {
    if (user && sessions.length > 0 && !currentId) {
      api.getSession(sessions[0].id).then((s) => {
        if (s.files && s.files.length > 0) setFiles(s.files);
      }).catch(() => {});
    }
  }, [user, sessions, currentId]);

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
  function handleCitationClick(
    index: number,
    msgCitations?: Citation[],
    msgText?: string,
    userPrompt?: string,
  ) {
    const list = msgCitations && msgCitations.length > 0 ? msgCitations : citations;
    const cit = list.find((c) => c.index === index) || list[index - 1] || list[0];
    if (cit) {
      setActiveCitation(cit);
      setActiveDocument(cit.file);
      if (msgCitations && msgCitations.length > 0) {
        setCitations(msgCitations);
      }
      if (userPrompt) setExplicitQuery(userPrompt);
      if (msgText) setExplicitAnswer(msgText);
      setViewerOpen(true);
    }
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
    setViewerOpen(false);
    setActiveCitation(null);
    setActiveDocument('');
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

    const abortCtrl = new AbortController();
    abortCtrlRef.current = abortCtrl;

    let streamedAny = false;
    let finalCitations: Citation[] = [];

    try {
      await api.queryStream(
        sid,
        text,
        topK,
        scope.modality,
        scope.files,
        provider,
        {
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
            const updatedCitations = (info.citations && info.citations.length > 0) ? info.citations : finalCitations;
            updateMessage(aId, (prev) => ({
              text: info.answer || prev.text,
              citations: updatedCitations,
              usedLlm: info.used_llm,
              metrics: info.metrics || prev.metrics,
              loading: false,
            }));
            setCitations(updatedCitations);
            loadSessions();
          },
          onError: (err) => {
            throw err;
          },
        },
        abortCtrl.signal,
        scope.collection_id
      );
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        updateMessage(aId, { loading: false });
        return;
      }
      if (streamedAny) {
        updateMessage(aId, { loading: false });
        setError((err as Error).message);
      } else {
        try {
          const res = await api.query(sid, text, topK, scope.modality, scope.files, provider, scope.collection_id);
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
      abortCtrlRef.current = null;
      setBusy(false);
    }
  }

  async function handleImageQuery(file: File, query?: string) {
    const sid = await ensureSession();
    const imageUrl = URL.createObjectURL(file);
    const userPrompt = query?.trim() ? query.trim() : `[Image query: ${file.name}]`;
    addMessage({
      id: uid(),
      role: "user",
      text: userPrompt,
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
      const res = await api.queryImage(sid, file, topK, scope.files, provider, query?.trim());
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

  async function handleAudioQuery(file: File, query?: string) {
    const sid = await ensureSession();
    const userPrompt = query?.trim() ? query.trim() : `[Audio query: ${file.name}]`;
    addMessage({
      id: uid(),
      role: "user",
      text: userPrompt,
    });
    const aId = addMessage({
      id: uid(),
      role: "assistant",
      text: "",
      loading: true,
    });
    setBusy(true);
    try {
      const res = await api.queryAudio(sid, file, topK, scope.files, provider, query?.trim());
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

  function handleRegenerate() {
    const userMsgs = messages.filter((m) => m.role === 'user');
    if (userMsgs.length > 0) {
      const lastUserMsg = userMsgs[userMsgs.length - 1];
      handleTextQuery(lastUserMsg.text);
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
      <div className="flex h-screen items-center justify-center bg-surface-50 dark:bg-surface-950">
        <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
      </div>
    );
  }

  if (view === 'landing') {
    return <LandingPage onNavigate={setView} user={user} />;
  }

  if (!user) {
    if (view === 'register' || view === 'login') {
      return (
        <AuthPage
          initialMode={view === 'register' ? 'register' : 'login'}
          onSuccess={(u) => {
            setUser(u);
            setView('dashboard');
          }}
          onNavigate={setView}
        />
      );
    }
    return <LandingPage onNavigate={setView} user={user} />;
  }

  return (
    <AppShell
      currentView={view}
      onNavigate={setView}
      user={user}
      onLogout={requestLogout}
      activeProvider={activeProviderInfo}
      health={health}
      theme={theme}
      onToggleTheme={toggleTheme}
    >
      {view === 'dashboard' && (
        <DashboardView
          user={user}
          health={health}
          sessions={sessions}
          files={files}
          activeProvider={activeProviderInfo}
          onStartChat={() => {
            newChat();
            setView('chat');
          }}
          onSelectSession={(id) => {
            selectSession(id);
            setView('chat');
          }}
          onOpenUpload={() => setLibraryOpen(true)}
          onNavigate={setView}
        />
      )}

      {view === 'chat' && (
        <div className="flex h-full min-h-0 flex-1 overflow-hidden">
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
            collapsed={viewerOpen ? true : sidebarCollapsed}
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

          <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
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
              onNavigate={setView}
            />

            {health && !health.llm_available && <LlmBanner />}

            <div className="flex min-h-0 flex-1 relative overflow-hidden">
              {/* Left Chat Pane */}
              <div
                className={`flex min-w-0 flex-col transition-all duration-150 ${
                  viewerOpen && activeDocument ? 'hidden lg:flex' : 'flex-1'
                }`}
                style={viewerOpen && activeDocument && typeof window !== 'undefined' && window.innerWidth >= 1024 ? { width: `${splitRatio}%` } : undefined}
              >
                <ChatPanel
                  messages={messages}
                  onCitationClick={handleCitationClick}
                  onPromptClick={(p) => handleTextQuery(p)}
                  onRegenerate={handleRegenerate}
                />
                <Composer
                  onSubmitText={handleTextQuery}
                  onImageQuery={handleImageQuery}
                  onAudioQuery={handleAudioQuery}
                  onStopGeneration={stopGeneration}
                  transcribeBlob={transcribeBlob}
                  onError={setError}
                  busy={busy}
                  scope={scope}
                  setScope={setScope}
                  files={files}
                  topK={topK}
                  setTopK={setTopK}
                  activeProvider={activeProviderInfo}
                />
              </div>

              {/* Resizable Divider between Chat and Document Viewer */}
              {viewerOpen && activeDocument && (
                <div
                  className="hidden lg:block w-1.5 bg-surface-200 hover:bg-brand-500 cursor-col-resize transition-colors dark:bg-surface-800"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    const onMouseMove = (moveEvent: MouseEvent) => {
                      const containerWidth = window.innerWidth;
                      const newRatio = Math.min(65, Math.max(35, (moveEvent.clientX / containerWidth) * 100));
                      setSplitRatio(newRatio);
                    };
                    const onMouseUp = () => {
                      window.removeEventListener('mousemove', onMouseMove);
                      window.removeEventListener('mouseup', onMouseUp);
                    };
                    window.addEventListener('mousemove', onMouseMove);
                    window.addEventListener('mouseup', onMouseUp);
                  }}
                  title="Drag to resize split view"
                />
              )}

              {/* Right Document Viewer Pane */}
              {viewerOpen && activeDocument ? (
                <div
                  className="flex-1 flex min-w-0 h-full overflow-hidden"
                  style={typeof window !== 'undefined' && window.innerWidth >= 1024 ? { width: `${100 - splitRatio}%` } : undefined}
                >
                  <DocumentViewer
                    sessionId={currentId || (sessions[0]?.id) || ''}
                    activeDocument={activeDocument}
                    activeCitation={activeCitation}
                    allCitations={citations}
                    onSelectCitation={(cit) => {
                      setActiveCitation(cit);
                      setActiveDocument(cit.file);
                    }}
                    onClose={() => setViewerOpen(false)}
                    isSplitView={true}
                    activeQuery={explicitQuery || lastUserQuery}
                    activeAnswer={explicitAnswer || lastAssistantAnswer}
                  />
                </div>
              ) : (
                <SourcesPanel
                  citations={citations}
                  flashIndex={flashIndex}
                  onError={setError}
                  open={sourcesOpen}
                  onClose={() => setSourcesOpen(false)}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {view === 'settings' && (
        <ModelSettingsView
          onProviderChanged={(newProvider) => {
            setProvider(newProvider);
            loadHealth();
          }}
        />
      )}

      {view === 'documents' && (
        <DocumentManagement
          onOpenViewer={(_sessionId, filename) => {
            setActiveDocument(filename);
            setActiveCitation(null);
            setViewerOpen(true);
            setView('chat');
          }}
          onChatWithFiles={(targetFiles) => {
            newChat();
            setScope({ modality: 'all', files: targetFiles });
            setView('chat');
          }}
        />
      )}

      {view === 'collections' && (
        <CollectionManagement
          onChatWithCollection={(collection) => {
            newChat();
            setScope({
              modality: 'all',
              files: collection.files || [],
              collection_id: collection.id,
              collection_name: collection.name,
            });
            setView('chat');
          }}
          onOpenViewer={(_sessionId, filename) => {
            setActiveDocument(filename);
            setActiveCitation(null);
            setViewerOpen(true);
            setView('chat');
          }}
        />
      )}

      {view === 'search' && (
        <div className="flex-1 overflow-y-auto p-6 max-w-5xl mx-auto space-y-6">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-surface-100">
              Cross-Modal Semantic Search
            </h2>
            <p className="text-sm text-surface-500 mt-1">
              Search passages, image captions, and multilingual transcripts across all enterprise collections.
            </p>
          </div>
          <DocumentManagement
            onOpenViewer={(_sessionId, filename) => {
              setActiveDocument(filename);
              setActiveCitation(null);
              setViewerOpen(true);
              setView('chat');
            }}
          />
        </div>
      )}

      {view === 'admin' && <EnterpriseAdminView />}

      {citations.length > 0 && view === 'chat' && (
        <button
          onClick={() => setSourcesOpen(true)}
          className="fixed bottom-24 right-4 z-20 flex items-center gap-1.5 rounded-full bg-brand-600 px-4 py-2.5 text-sm font-medium text-white shadow-lg lg:hidden"
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
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-surface-950/50 px-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-surface-200 bg-white p-6 shadow-elevated dark:border-surface-800 dark:bg-surface-900">
            <h3 className="text-base font-semibold text-surface-900 dark:text-surface-100">
              Sign Out
            </h3>
            <p className="mt-2 text-xs text-surface-500 dark:text-surface-400">
              Are you sure you want to sign out of this workspace?
            </p>
            <div className="mt-5 flex justify-end gap-2.5">
              <button
                onClick={() => setShowLogoutConfirm(false)}
                className="rounded-lg border border-surface-200 px-3.5 py-1.5 text-xs font-medium text-surface-700 hover:bg-surface-50 dark:border-surface-700 dark:text-surface-300 dark:hover:bg-surface-800"
              >
                Cancel
              </button>
              <button
                onClick={confirmLogout}
                className="rounded-lg bg-rose-600 px-3.5 py-1.5 text-xs font-medium text-white hover:bg-rose-700"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

      <Toast message={error} onClose={() => setError(null)} />
    </AppShell>
  );
}

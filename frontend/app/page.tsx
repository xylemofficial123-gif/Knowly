"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import OracleResponse from "@/components/OracleResponse";
import CitationCard from "@/components/CitationCard";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const FALLBACK_PROJECTS = ["AI Labs", "Sprout", "Orchard"] as const;

type ProjectCardState = {
  answer: string;
  citations: any[];
  query: string;
  loading: boolean;
  error: string;
};

const ONBOARDING_TASKS = [
  "Read overview",
  "Understand architecture",
  "Review recent decisions",
  "Run project locally",
] as const;

const ROLE_SETUP_CARDS = [
  { label: "Testing", query: "Role: Testing. List only tool/setup names needed for onboarding QA/Testing." },
  { label: "Dev", query: "Role: Dev. List only tool/setup names needed for developer onboarding." },
  { label: "HR", query: "Role: HR. List only tool/setup names needed for HR onboarding." },
  { label: "PM", query: "Role: PM. List only tool/setup names needed for PM onboarding." },
] as const;

function extractSetupItems(answer: string): string[] {
  if (!answer) return [];

  // Try strict JSON first.
  const fenced = answer.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidate = (fenced ? fenced[1] : answer).trim();
  try {
    const parsed = JSON.parse(candidate);
    if (Array.isArray(parsed?.setup_items)) {
      return Array.from(
        new Set(
          parsed.setup_items
            .map((x: any) => String(x).trim())
            .filter((x: string) => x.length > 1)
        )
      );
    }
  } catch {}

  // Fallback: extract bullet-like or numbered lines and keep short tool-like items.
  const lines = answer
    .split("\n")
    .map((l) => l.replace(/^\s*[-*•\d.)]+\s*/, "").trim())
    .filter((l) => l.length > 1 && l.length <= 80)
    .filter((l) => !/overview|summary|status|people|context|open items/i.test(l));

  return Array.from(new Set(lines)).slice(0, 20);
}

export default function Home() {
  const { user } = useUser();
  const { getToken } = useAuth();
  const userEmail = user?.emailAddresses?.[0]?.emailAddress ?? "";
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [quickOnboardingMode, setQuickOnboardingMode] = useState(false);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [roleSetupItems, setRoleSetupItems] = useState<string[]>([]);
  const [roleCardResult, setRoleCardResult] = useState<{ answer: string; citations: any[]; loading: boolean; error: string }>({
    answer: "",
    citations: [],
    loading: false,
    error: "",
  });
  // Projects shown on Quick Onboarding are pulled from /api/groups so admins
  // can manage them via the Groups tab. Falls back to a small hardcoded list
  // only for unauthenticated SSR / when the fetch fails.
  const [projects, setProjects] = useState<string[]>([...FALLBACK_PROJECTS]);
  const [projectTaskState, setProjectTaskState] = useState<Record<string, Record<string, boolean>>>(() =>
    Object.fromEntries(
      FALLBACK_PROJECTS.map((project) => [
        project,
        Object.fromEntries(ONBOARDING_TASKS.map((task) => [task, false])),
      ])
    )
  );
  const [projectCards, setProjectCards] = useState<Record<string, ProjectCardState>>(
    () =>
      Object.fromEntries(
        FALLBACK_PROJECTS.map((project) => [
          project,
          { answer: "", citations: [], query: "", loading: false, error: "" },
        ])
      )
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Hydrate client-only state after mount to avoid SSR/CSR mismatch.
  useEffect(() => {
    try {
      const storedMessages = JSON.parse(sessionStorage.getItem("xylem_chat_messages") || "[]");
      const storedSession = sessionStorage.getItem("xylem_chat_session") || "";
      setMessages(Array.isArray(storedMessages) ? storedMessages : []);
      setSessionId(storedSession);
    } catch {
      setMessages([]);
      setSessionId("");
    } finally {
      setHydrated(true);
    }
  }, []);

  // Persist chat state across navigation (after hydration only)
  useEffect(() => {
    if (!hydrated) return;
    sessionStorage.setItem("xylem_chat_messages", JSON.stringify(messages));
  }, [messages, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    sessionStorage.setItem("xylem_chat_session", sessionId);
  }, [sessionId, hydrated]);

  const [decisionCount, setDecisionCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = await getToken();
        if (!token) return;
        const res = await fetch(`${API_URL}/api/admin/decisions?status=all&limit=200`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        const count = Array.isArray(data?.decisions) ? data.decisions.length : null;
        if (!cancelled && count !== null) setDecisionCount(count);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [getToken]);

  // Pull project list from /api/groups?mine=true so a new joiner only sees
  // projects they've actually been added to. Admins see all projects (the
  // backend handles that exception). Empty list → render the empty state.
  const [projectsLoaded, setProjectsLoaded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = await getToken();
        if (!token) {
          if (!cancelled) setProjectsLoaded(true);
          return;
        }
        const res = await fetch(`${API_URL}/api/groups?mine=true`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          if (!cancelled) setProjectsLoaded(true);
          return;
        }
        const data = await res.json();
        const names: string[] = Array.isArray(data?.groups)
          ? data.groups.map((g: any) => g?.name).filter(Boolean)
          : [];
        if (cancelled) return;
        setProjects(names);
        setProjectCards((prev) => {
          const next: Record<string, ProjectCardState> = { ...prev };
          for (const n of names) {
            if (!next[n]) next[n] = { answer: "", citations: [], query: "", loading: false, error: "" };
          }
          return next;
        });
        setProjectTaskState((prev) => {
          const next: Record<string, Record<string, boolean>> = { ...prev };
          for (const n of names) {
            if (!next[n]) {
              next[n] = Object.fromEntries(ONBOARDING_TASKS.map((task) => [task, false]));
            }
          }
          return next;
        });
        setProjectsLoaded(true);
      } catch {
        if (!cancelled) setProjectsLoaded(true);
      }
    })();
    return () => { cancelled = true; };
  }, [getToken]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const askOracle = useCallback(async (q: string, historyOverride?: any[]) => {
    const token = await getToken();
    const res = await fetch(`${API_URL}/api/oracle/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        question: q,
        user_email: userEmail,
        session_id: sessionId,
        history: (historyOverride || messages).map((m) => ({ role: m.role, content: m.content })),
      }),
    });

    if (!res.ok) throw new Error("API Request Failed");
    const data = await res.json();
    if (data.session_id) setSessionId(data.session_id);
    return data;
  }, [getToken, messages, sessionId, userEmail]);

  const runProjectQuery = useCallback(async (project: string, customQuery?: string) => {
    const scopedQuery = customQuery?.trim()
      ? `For ${project} project only: ${customQuery.trim()}`
      : `Catch me up on the history of the ${project} project.`;

    setProjectCards((prev) => ({
      ...prev,
      [project]: { ...prev[project], loading: true, error: "" },
    }));

    try {
      const data = await askOracle(scopedQuery, []);
      setProjectCards((prev) => ({
        ...prev,
        [project]: {
          ...prev[project],
          answer: data.answer || "",
          citations: data.citations || [],
          loading: false,
          error: "",
        },
      }));
    } catch (e: any) {
      setProjectCards((prev) => ({
        ...prev,
        [project]: {
          ...prev[project],
          loading: false,
          error: e?.message || "Failed to load onboarding context.",
        },
      }));
    }
  }, [askOracle]);

  const openProjectCard = useCallback((project: string) => {
    if (selectedProject === project) {
      setSelectedProject(null);
      return;
    }
    setSelectedProject(project);
    const card = projectCards[project];
    if (!card?.answer && !card?.loading) {
      runProjectQuery(project);
    }
  }, [selectedProject, projectCards, runProjectQuery]);

  const runRoleSetupQuery = useCallback(async (roleLabel: string, q: string) => {
    setSelectedRole(roleLabel);
    setRoleSetupItems([]);
    setRoleCardResult({ answer: "", citations: [], loading: true, error: "" });
    try {
      const strictPrompt = `${q}
Return ONLY JSON in this exact format:
{"setup_items":["item 1","item 2"]}
Rules:
- setup_items must contain only software/services/accounts/repos/environments a user needs to set up
- no explanations
- no people names
- no headings
- no extra keys`;
      const data = await askOracle(strictPrompt, []);
      const setupItems = extractSetupItems(data.answer || "");
      setRoleCardResult({
        answer: data.answer || "",
        citations: data.citations || [],
        loading: false,
        error: "",
      });
      setRoleSetupItems(setupItems);
    } catch (e: any) {
      setRoleCardResult({
        answer: "",
        citations: [],
        loading: false,
        error: e?.message || "Failed to load role setup.",
      });
    }
  }, [askOracle]);

  const handleAsk = useCallback(async (explicitQuery?: string, cachedData?: any) => {
    const q = explicitQuery || question;
    if (!q.trim() || loading) return;

    // If we have cached data, display it instantly and skip the API call
    if (cachedData) {
      setMessages([{ role: "user", content: q }, { role: "assistant", content: cachedData.answer, result: cachedData }]);
      if (cachedData.session_id) setSessionId(cachedData.session_id);
      setQuestion("");
      return;
    }

    const userMessage = { role: "user", content: q };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);

    try {
      const data = await askOracle(q, messages);

      setMessages((prev) => [...prev, { role: "assistant", content: data.answer, result: data }]);

      // Save full result to recent queries locally
      const recent = JSON.parse(localStorage.getItem("xylem_recent_queries") || "[]");
      const updated = [{ text: q, time: "Just now", result: data }, ...recent].slice(0, 10);
      localStorage.setItem("xylem_recent_queries", JSON.stringify(updated));
      window.dispatchEvent(new Event("storage"));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [question, loading, messages, askOracle]);

  useEffect(() => {
    if (!hydrated) return;
    if (sessionStorage.getItem("xylem_open_quick_onboarding") === "1") {
      sessionStorage.removeItem("xylem_open_quick_onboarding");
      setQuickOnboardingMode(true);
    }
  }, [hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    const handleCustomQuery = (e: any) => {
      if (e.detail) {
        setQuickOnboardingMode(false);
        if (typeof e.detail === "string") {
          handleAsk(e.detail);
        } else {
          handleAsk(e.detail.text, e.detail.result);
        }
      }
    };
    const handleQuickOnboarding = () => {
      setQuickOnboardingMode(true);
      setSelectedProject(null);
      setSelectedRole(null);
      setError("");
    };
    const handleNewQuery = () => {
      setQuickOnboardingMode(false);
      sessionStorage.removeItem("xylem_chat_messages");
      sessionStorage.removeItem("xylem_chat_session");
      setMessages([]);
      setQuestion("");
      setError("");
      setSessionId("");
    };
    window.addEventListener("xylem_query", handleCustomQuery);
    window.addEventListener("xylem_quick_onboarding", handleQuickOnboarding);
    window.addEventListener("xylem_new_query", handleNewQuery);
    return () => {
      window.removeEventListener("xylem_query", handleCustomQuery);
      window.removeEventListener("xylem_quick_onboarding", handleQuickOnboarding);
      window.removeEventListener("xylem_new_query", handleNewQuery);
    };
  }, [handleAsk, hydrated]);

  return (
    <div className="flex-1 flex flex-col h-screen min-w-0">
      {/* Top Header Stats Bar */}
      <header className="h-20 border-b border-gray-100 bg-white/80 backdrop-blur-md px-10 flex items-center justify-between sticky top-0 z-40 shrink-0">
        <h2 className="text-xl font-bold tracking-tight text-foreground">Query memory</h2>
        <div className="flex items-center gap-3">
          {decisionCount !== null && (
            <div className="bg-accent-soft px-4 py-2.5 rounded-2xl flex items-center gap-2 border border-accent/5">
              <span className="text-accent font-bold text-xs">{decisionCount}</span>
              <span className="text-accent/60 text-[10px] font-bold uppercase tracking-widest translate-y-[0.5px]">decisions indexed</span>
            </div>
          )}
        </div>
      </header>

      {/* Main View Area */}
      <main className="flex-1 overflow-y-auto custom-scrollbar relative px-10 pt-16 pb-32">
        <div className="max-w-4xl mx-auto w-full">
          {quickOnboardingMode ? (
            <section className="space-y-6 animate-in">
              <div className="text-left">
                <h1 className="text-4xl font-black text-foreground tracking-tight mb-3">New joiner</h1>
                <p className="text-gray-500 text-sm font-medium">
                  Pick a project for an instant briefing — decisions, owners, and rationale.
                </p>
              </div>

              {projectsLoaded && projects.length === 0 ? (
                <div className="rounded-3xl border border-dashed border-green-200 bg-green-50/40 p-10 text-center">
                  <div className="text-3xl mb-3">🌱</div>
                  <p className="font-bold text-green-900 mb-1">Not assigned to a project yet</p>
                  <p className="text-sm text-green-700/80 max-w-md mx-auto leading-relaxed">
                    Ask an admin to add you to a team in the Groups tab. Once you're a member,
                    you'll see briefings, decisions, and role setup for that project here.
                  </p>
                </div>
              ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {projects.map((project) => (
                  <button
                    key={project}
                    onClick={() => openProjectCard(project)}
                    className={`aspect-square rounded-[2rem] border p-6 text-left transition-all ${
                      selectedProject === project
                        ? "border-green-300 bg-green-50 shadow-xl shadow-green-100/60"
                        : "border-green-100 bg-white hover:bg-green-50/60"
                    }`}
                  >
                    <p className="text-[10px] font-bold uppercase tracking-widest text-green-700 mb-3">Project</p>
                    <p className="text-2xl font-black text-foreground leading-tight">{project}</p>
                  </button>
                ))}
              </div>
              )}

              <section className="bg-white border border-green-100 rounded-[2rem] p-6">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xl font-black text-foreground">Onboarding progress</h3>
                  <span className="text-sm font-bold text-green-700">
                    {selectedProject ? `${Math.round((Object.values(projectTaskState[selectedProject] || {}).filter(Boolean).length / ONBOARDING_TASKS.length) * 100)}%` : "0%"}
                  </span>
                </div>
                {selectedProject ? (
                  <>
                    <div className="w-full h-3 rounded-full bg-green-50 border border-green-100 mb-4 overflow-hidden">
                      <div
                        className="h-full bg-green-500 transition-all"
                        style={{
                          width: `${Math.round((Object.values(projectTaskState[selectedProject] || {}).filter(Boolean).length / ONBOARDING_TASKS.length) * 100)}%`,
                        }}
                      />
                    </div>
                    <p className="text-xs font-semibold text-gray-500 mb-3">
                      Checklist for <span className="text-foreground">{selectedProject}</span>
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {ONBOARDING_TASKS.map((task) => {
                        const checked = Boolean(projectTaskState[selectedProject]?.[task]);
                        return (
                          <label key={task} className="flex items-center gap-2 px-3 py-2 rounded-xl border border-gray-100 bg-gray-50/60 text-sm font-medium text-gray-700">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() =>
                                setProjectTaskState((prev) => ({
                                  ...prev,
                                  [selectedProject]: {
                                    ...prev[selectedProject],
                                    [task]: !checked,
                                  },
                                }))
                              }
                              className="accent-green-600"
                            />
                            {task}
                          </label>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-gray-500 font-medium">Select a project to start tracking onboarding progress.</p>
                )}
              </section>

              <section className="space-y-4">
                <h3 className="text-xl font-black text-foreground">Role setup</h3>
                <p className="text-sm text-gray-500 font-medium">
                  Pick your role to see required tools, setup, and what the team is using.
                </p>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {ROLE_SETUP_CARDS.map((role) => (
                    <button
                      key={role.label}
                      onClick={() => runRoleSetupQuery(role.label, role.query)}
                      className={`h-14 rounded-xl border text-sm font-black transition-all ${
                        selectedRole === role.label
                          ? "bg-green-50 border-green-300 text-green-800"
                          : "bg-white border-gray-200 text-foreground hover:bg-gray-50"
                      }`}
                    >
                      {role.label}
                    </button>
                  ))}
                </div>
                {selectedRole && (
                  <div className="bg-white border border-gray-100 rounded-2xl p-4">
                    <p className="text-[11px] font-bold uppercase tracking-widest text-green-700 mb-3">
                      {selectedRole} setup
                    </p>
                    {roleCardResult.loading ? (
                      <div className="text-sm font-semibold text-gray-500">Loading setup guide...</div>
                    ) : roleCardResult.error ? (
                      <div className="text-sm font-semibold text-red-600">⚠️ {roleCardResult.error}</div>
                    ) : roleSetupItems.length > 0 ? (
                      <div className="space-y-3">
                        <div className="flex flex-wrap gap-2">
                          {roleSetupItems.map((item) => (
                            <span
                              key={item}
                              className="inline-flex items-center px-3 py-1.5 rounded-lg border border-green-100 bg-green-50 text-xs font-semibold text-green-900"
                            >
                              {item}
                            </span>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500">No setup items found for this role.</p>
                    )}
                  </div>
                )}
              </section>

              {selectedProject && (() => {
                const card = projectCards[selectedProject];
                return (
                  <div className="bg-white border border-green-100 rounded-[2rem] p-6 shadow-lg shadow-green-100/40">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-xl font-black text-foreground">{selectedProject}</h2>
                    </div>

                    <div className="flex items-center gap-2 mb-5">
                      <input
                        value={card.query}
                        onChange={(e) =>
                          setProjectCards((prev) => ({
                            ...prev,
                            [selectedProject]: { ...prev[selectedProject], query: e.target.value },
                          }))
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            runProjectQuery(selectedProject, card.query);
                          }
                        }}
                        placeholder={`Ask about ${selectedProject} only...`}
                        className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-foreground placeholder:text-gray-300 focus:outline-none focus:ring-2 focus:ring-green-100"
                      />
                      <button
                        onClick={() => runProjectQuery(selectedProject, card.query)}
                        disabled={card.loading}
                        className="h-11 px-4 bg-accent text-white rounded-xl text-sm font-bold disabled:opacity-40"
                      >
                        Ask
                      </button>
                    </div>

                    {card.loading ? (
                      <div className="p-5 rounded-2xl border border-dashed border-gray-200 text-[11px] font-black uppercase tracking-[0.2em] text-accent animate-pulse">
                        Loading {selectedProject} context...
                      </div>
                    ) : card.error ? (
                      <div className="p-4 rounded-2xl border border-red-100 bg-red-50 text-red-600 text-sm font-medium">
                        ⚠️ {card.error}
                      </div>
                    ) : card.answer ? (
                      <div className="space-y-4">
                        <OracleResponse answer={card.answer} citations={card.citations || []} />
                        {(card.citations || []).length > 0 && (
                          <div className="flex flex-wrap gap-2">
                            {(card.citations || []).slice(0, 8).map((cite: any, ci: number) => (
                              <a
                                key={`${selectedProject}-${ci}`}
                                href={cite.url || "#"}
                                target={cite.url ? "_blank" : undefined}
                                rel={cite.url ? "noopener noreferrer" : undefined}
                                className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg border border-green-100 bg-green-50 text-[11px] font-semibold text-green-900"
                                title={cite.display || "Source"}
                              >
                                <span className="w-4 h-4 rounded-full bg-green-600 text-white text-[10px] flex items-center justify-center">
                                  {ci + 1}
                                </span>
                                <span className="max-w-[180px] truncate">{cite.display || cite.source || "Source"}</span>
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="p-5 rounded-2xl border border-dashed border-gray-200 text-sm text-gray-400 font-medium">
                        Select Ask to load onboarding summary.
                      </div>
                    )}
                  </div>
                );
              })()}
            </section>
          ) : messages.length === 0 ? (
            <section className="flex flex-col items-center pt-10 text-center animate-in">
              <img
                src="/xylem-mascot.png"
                alt=""
                className="w-32 h-32 object-contain mb-6"
              />
              <h1 className="text-6xl font-black text-foreground mb-6 tracking-tight">
                Ask Xylem anything
              </h1>
              <p className="text-gray-400 text-lg font-medium max-w-xl leading-relaxed mb-16 px-4">
                Query the why behind every decision, meeting, and pivot across your company's entire history.
              </p>

              {/* Dynamic Category Suggestion Grid */}
              <div className="grid grid-cols-2 gap-5 w-full max-w-3xl">
                {[
                  { label: "Pricing", query: "What are the key decisions in pricing?" },
                  { label: "Ownership", query: "What are the key decisions in ownership?" },
                  { label: "Leadership", query: "What are the key decisions in leadership?" },
                  { label: "Engineering", query: "What are the key decisions in engineering?" },
                ].map((item) => (
                  <button
                    key={item.label}
                    onClick={() => handleAsk(item.query)}
                    className="p-8 text-left bg-white border border-gray-100 rounded-[2rem] hover:border-accent/30 hover:shadow-2xl hover:shadow-gray-100 transition-all duration-300 group"
                  >
                    <p className="text-[11px] font-bold text-gray-300 uppercase tracking-widest mb-3 group-hover:text-accent">
                      {item.label}
                    </p>
                    <p className="text-lg font-bold text-foreground leading-snug group-hover:text-accent-dark">
                      {`Query the history of ${item.label.toLowerCase()} and its impact...`}
                    </p>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <div className="space-y-12">
              {messages.map((msg, i) => (
                <div key={i} className="animate-in">
                  {msg.role === "user" ? (
                    <div className="flex justify-end pr-2">
                      <div className="bg-foreground text-white px-8 py-5 rounded-[2.5rem] rounded-tr-none max-w-[80%] shadow-2xl shadow-gray-100 text-[17px] font-medium leading-relaxed">
                        {msg.content}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      <div className="flex items-center gap-3 ml-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-accent animate-pulse shadow-[0_0_10px_rgba(22,163,74,0.5)]"></span>
                        <span className="text-[11px] font-black text-gray-400 uppercase tracking-widest tracking-[0.2em]">Xylem Intelligence</span>
                      </div>
                      <OracleResponse answer={msg.content} citations={msg.result?.citations || []} />
                      {msg.result?.citations?.length > 0 && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 ml-2 mt-4">
                          {msg.result.citations.map((cite: any, ci: number) => (
                            <CitationCard key={ci} citation={cite} index={ci + 1} />
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div className="flex items-center gap-5 p-10 bg-white border border-dashed border-gray-200 rounded-[2rem] animate-pulse ml-2">
                  <div className="flex gap-2">
                    {[1, 2, 3].map((d) => (
                      <span key={d} className="w-2.5 h-2.5 rounded-full bg-accent"></span>
                    ))}
                  </div>
                  <span className="text-[11px] font-black uppercase tracking-[0.2em] text-accent">Extracting Knowledge Assets...</span>
                </div>
              )}
              {error && (
                <div className="p-6 bg-red-50 text-red-600 rounded-3xl border border-red-100 text-sm font-medium animate-in">
                  ⚠️ {error}
                </div>
              )}
              <div ref={messagesEndRef} className="h-32" />
            </div>
          )}
        </div>
      </main>

      {/* Floating Bottom Input Bar */}
      {!quickOnboardingMode && (
      <div className="max-w-4xl mx-auto w-full px-10 pb-12 sticky bottom-0 left-0 right-0 pointer-events-none">
        <div className="w-full bg-white/95 backdrop-blur-sm rounded-[2.5rem] border border-gray-100 shadow-[0_40px_80px_-20px_rgba(0,0,0,0.15)] p-2 pointer-events-auto group focus-within:ring-4 focus-within:ring-accent-soft transition-all duration-500">
          <div className="flex items-end gap-3 px-6 pt-4 pb-4">
            <button className="h-12 w-12 flex items-center justify-center text-gray-300 hover:bg-gray-50 rounded-2xl transition-all">
              📎
            </button>
            <textarea
              className="flex-1 bg-transparent py-4 text-[17px] font-medium text-foreground placeholder:text-gray-300 resize-none focus:outline-none min-h-[60px] max-h-40"
              placeholder="Ask about decisions, history, or rationale..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), handleAsk())}
              rows={1}
            />
            <button
              onClick={() => handleAsk()}
              disabled={loading || !question.trim()}
              className="h-14 w-14 bg-accent text-white rounded-2xl flex items-center justify-center text-2xl shadow-xl shadow-accent/20 transition-all hover:scale-105 active:scale-95 disabled:opacity-20 disabled:shadow-none"
            >
              ➔
            </button>
          </div>

          {/* Active Sources Bar */}
          <div className="flex items-center gap-6 px-8 pb-4 pt-2 border-t border-gray-50/50 mt-1">
            {[
              { name: "Slack", color: "bg-teal-500" },
              { name: "Drive", color: "bg-orange-400" },
              { name: "ClickUp", color: "bg-purple-400" },
              { name: "Transcripts", color: "bg-green-400" }
            ].map((s) => (
              <div key={s.name} className="flex items-center gap-2 group cursor-pointer">
                <div className={`w-2 h-2 rounded-full ${s.color} transition-all group-hover:scale-150`}></div>
                <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest group-hover:text-foreground">{s.name}</span>
              </div>
            ))}
            <div className="ml-auto text-[10px] font-bold text-gray-200 uppercase tracking-tighter">Enter ↵ to send · Shift+Enter new line</div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}

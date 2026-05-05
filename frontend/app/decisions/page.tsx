"use client";

import { useState, useEffect } from "react";
import { useUser, useAuth } from "@clerk/nextjs";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface DriftAlert {
  id: string;
  similarity: number;
  contradicts: string;
  reasoning: string;
  status: string;
  detected_at: string;
  decision_a: { id: string; decision: string; rationale: string; decided_at: string } | null;
  decision_b: { id: string; decision: string; rationale: string; decided_at: string } | null;
}

interface Decision {
  id: string;
  decision: string;
  rationale: string;
  status: "active" | "superseded";
  decided_at: string;
  superseded_by: string | null;
  superseded_at: string | null;
  reversal_reason: string | null;
  visibility?: "public" | "group" | "private";
  groups?: { id: string; name: string }[];
}

interface DecisionList {
  items: Decision[];
  total_active: number;
  total_superseded: number;
}

interface ChainEntry {
  id: string;
  decision: string;
  rationale: string;
  status: string;
  decided_at: string;
  superseded_at: string | null;
  reversal_reason: string | null;
  is_current: boolean;
}

function formatDate(iso: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function DecisionsPage() {
  const { user } = useUser();
  const { getToken } = useAuth();
  const userEmail = user?.emailAddresses?.[0]?.emailAddress ?? "";
  const [data, setData] = useState<DecisionList | null>(null);
  const [filter, setFilter] = useState<"all" | "active" | "superseded">("all");
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [extractMsg, setExtractMsg] = useState("");
  const [expandedChain, setExpandedChain] = useState<string | null>(null);
  const [chains, setChains] = useState<Record<string, ChainEntry[]>>({});
  const [driftAlerts, setDriftAlerts] = useState<DriftAlert[]>([]);
  const [driftRunning, setDriftRunning] = useState(false);
  const [driftMsg, setDriftMsg] = useState("");
  const [driftExpanded, setDriftExpanded] = useState(false);

  const fetchDecisions = (status = filter) => {
    setLoading(true);
    const url = `${API_URL}/api/admin/decisions?status=${status}&limit=100${userEmail ? `&user_email=${encodeURIComponent(userEmail)}` : ""}`;
    fetch(url)
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchDecisions(filter); }, [filter, userEmail]);

  const fetchDriftAlerts = async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const res = await fetch(`${API_URL}/api/admin/drift-sweep/alerts?status=open`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const d = await res.json();
      setDriftAlerts(Array.isArray(d?.alerts) ? d.alerts : []);
    } catch {}
  };

  useEffect(() => { fetchDriftAlerts(); }, []);

  const runDriftSweep = async () => {
    setDriftRunning(true);
    setDriftMsg("");
    try {
      const token = await getToken();
      const res = await fetch(`${API_URL}/api/admin/drift-sweep/run`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const d = await res.json();
      if (!res.ok) {
        setDriftMsg(d?.detail || "Drift sweep failed.");
      } else {
        setDriftMsg(`Sweep complete — ${d.alerts_created ?? 0} new alert(s), ${d.checked_pairs ?? 0} pair(s) checked.`);
        fetchDriftAlerts();
      }
    } catch (e: any) {
      setDriftMsg(e?.message || "Drift sweep failed.");
    } finally {
      setDriftRunning(false);
    }
  };

  const acknowledgeDriftAlert = async (alertId: string, status: "acknowledged" | "resolved") => {
    try {
      const token = await getToken();
      await fetch(`${API_URL}/api/admin/drift-sweep/alerts/${alertId}`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      fetchDriftAlerts();
    } catch {}
  };

  const triggerExtraction = async () => {
    setExtracting(true);
    setExtractMsg("");
    try {
      const res = await fetch(`${API_URL}/api/admin/decisions/extract`, { method: "POST" });
      const d = await res.json();
      setExtractMsg(`Done — ${d.decisions_total} decisions in system.`);
      fetchDecisions(filter);
    } catch {
      setExtractMsg("Extraction failed. Check backend logs.");
    } finally {
      setExtracting(false);
    }
  };

  const loadChain = async (id: string) => {
    if (expandedChain === id) { setExpandedChain(null); return; }
    if (!chains[id]) {
      const res = await fetch(`${API_URL}/api/admin/decisions/${id}/history`);
      const d = await res.json();
      setChains((prev) => ({ ...prev, [id]: d.chain || [] }));
    }
    setExpandedChain(id);
  };

  const items = data?.items || [];

  return (
    <div className="flex-1 overflow-y-auto h-full">
      <div className="max-w-4xl mx-auto px-10 py-12">
        {/* Header */}
        <div className="flex items-start justify-between mb-10">
          <div>
            <h1 className="text-3xl font-black text-foreground tracking-tight mb-2">Decision Log</h1>
            <p className="text-gray-400 text-sm font-medium">Every decision extracted from your ingested knowledge.</p>
          </div>
          <button
            onClick={triggerExtraction}
            disabled={extracting}
            className="px-5 py-2.5 bg-foreground text-white rounded-xl text-sm font-bold hover:bg-gray-800 transition-all disabled:opacity-40 flex items-center gap-2"
          >
            {extracting ? (
              <span className="animate-spin w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full inline-block"></span>
            ) : "⚡"}
            {extracting ? "Extracting..." : "Extract decisions"}
          </button>
        </div>

        {extractMsg && (
          <div className="mb-6 px-4 py-3 bg-green-50 border border-green-100 rounded-xl text-sm text-green-700 font-medium">
            {extractMsg}
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="bg-white rounded-2xl border border-gray-100 p-5">
            <div className="text-3xl font-black text-foreground mb-1">{data?.total_active ?? "—"}</div>
            <div className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Active decisions</div>
          </div>
          <div className="bg-white rounded-2xl border border-gray-100 p-5">
            <div className="text-3xl font-black text-gray-400 mb-1">{data?.total_superseded ?? "—"}</div>
            <div className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Reversed / superseded</div>
          </div>
        </div>

        {/* Drift alerts banner */}
        <div className={`mb-8 rounded-2xl border p-5 ${driftAlerts.length > 0 ? "bg-amber-50 border-amber-200" : "bg-blue-50 border-blue-100"}`}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg">{driftAlerts.length > 0 ? "⚠️" : "🛡️"}</span>
                <p className={`text-sm font-bold ${driftAlerts.length > 0 ? "text-amber-900" : "text-blue-900"}`}>
                  {driftAlerts.length > 0
                    ? `${driftAlerts.length} potential decision drift${driftAlerts.length > 1 ? "s" : ""} detected`
                    : "No active drift detected"}
                </p>
              </div>
              <p className={`text-xs leading-relaxed ${driftAlerts.length > 0 ? "text-amber-700" : "text-blue-700"}`}>
                {driftAlerts.length > 0
                  ? "Pairs of decisions that may contradict each other. Review and resolve to keep institutional memory consistent."
                  : "Periodic sweep checks every 4 hours. Manual trigger runs the same logic on demand."}
              </p>
              {driftMsg && (
                <p className="text-[11px] mt-2 font-medium text-gray-600">{driftMsg}</p>
              )}
            </div>
            <div className="flex flex-col gap-2 shrink-0">
              <button
                onClick={runDriftSweep}
                disabled={driftRunning}
                className="px-4 py-2 bg-foreground text-white rounded-xl text-[11px] font-bold hover:bg-gray-800 transition-all disabled:opacity-40 whitespace-nowrap"
              >
                {driftRunning ? "Sweeping…" : "Run sweep now"}
              </button>
              {driftAlerts.length > 0 && (
                <button
                  onClick={() => setDriftExpanded((v) => !v)}
                  className="px-4 py-2 bg-white border border-amber-200 text-amber-800 rounded-xl text-[11px] font-bold hover:bg-amber-100 transition-all whitespace-nowrap"
                >
                  {driftExpanded ? "Hide" : "Review"}
                </button>
              )}
            </div>
          </div>

          {driftExpanded && driftAlerts.length > 0 && (
            <div className="mt-5 space-y-3">
              {driftAlerts.map((a) => (
                <div key={a.id} className="bg-white rounded-xl border border-amber-100 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[10px] font-black uppercase tracking-widest text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                      {Math.round((a.similarity || 0) * 100)}% similar
                    </span>
                    <span className="text-[10px] font-bold text-gray-400">→</span>
                    <span className="text-[10px] font-black uppercase tracking-widest text-red-700 bg-red-50 px-2 py-0.5 rounded-full">
                      LLM verdict: contradicts
                    </span>
                  </div>
                  {a.reasoning && (
                    <p className="text-xs text-gray-600 italic mb-3 leading-relaxed">{a.reasoning}</p>
                  )}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="rounded-lg border border-gray-100 bg-gray-50/60 p-3">
                      <p className="font-bold text-gray-700 leading-snug mb-1">{a.decision_a?.decision || "—"}</p>
                      {a.decision_a?.rationale && (
                        <p className="text-gray-500 text-[11px] leading-relaxed">{a.decision_a.rationale}</p>
                      )}
                      <p className="text-[10px] text-gray-400 mt-2">{formatDate(a.decision_a?.decided_at || "")}</p>
                    </div>
                    <div className="rounded-lg border border-gray-100 bg-gray-50/60 p-3">
                      <p className="font-bold text-gray-700 leading-snug mb-1">{a.decision_b?.decision || "—"}</p>
                      {a.decision_b?.rationale && (
                        <p className="text-gray-500 text-[11px] leading-relaxed">{a.decision_b.rationale}</p>
                      )}
                      <p className="text-[10px] text-gray-400 mt-2">{formatDate(a.decision_b?.decided_at || "")}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex justify-end gap-2">
                    <button
                      onClick={() => acknowledgeDriftAlert(a.id, "acknowledged")}
                      className="text-[11px] font-bold text-gray-500 hover:text-gray-700 px-3 py-1 rounded-md hover:bg-gray-100"
                    >
                      Acknowledge
                    </button>
                    <button
                      onClick={() => acknowledgeDriftAlert(a.id, "resolved")}
                      className="text-[11px] font-bold text-green-700 hover:text-green-900 px-3 py-1 rounded-md hover:bg-green-50"
                    >
                      Mark resolved
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2 mb-6">
          {(["all", "active", "superseded"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-xl text-[12px] font-bold transition-all ${
                filter === f ? "bg-foreground text-white" : "bg-white border border-gray-200 text-gray-500 hover:bg-gray-50"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {loading && (
          <div className="flex items-center gap-3 text-gray-400 text-sm py-12">
            <span className="animate-spin w-4 h-4 border-2 border-accent border-t-transparent rounded-full inline-block"></span>
            Loading decisions...
          </div>
        )}

        {!loading && items.length === 0 && (
          <div className="text-center py-20 bg-white rounded-3xl border border-dashed border-gray-200">
            <div className="text-4xl mb-4">📜</div>
            <p className="font-bold text-gray-500 mb-2">No decisions extracted yet</p>
            <p className="text-sm text-gray-400 max-w-sm mx-auto leading-relaxed">
              Click <strong>"Extract decisions"</strong> above to scan all ingested documents for decisions and rationale.
              Decisions are also extracted automatically when new documents are ingested via Google Meet.
            </p>
          </div>
        )}

        <div className="space-y-3">
          {items.map((d) => (
            <div key={d.id} className="bg-white rounded-2xl border border-gray-100 overflow-hidden">
              <div className="px-6 py-5">
                <div className="flex items-start gap-3">
                  <span className={`mt-0.5 shrink-0 px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${
                    d.status === "active"
                      ? "bg-green-100 text-green-700"
                      : "bg-gray-100 text-gray-500 line-through"
                  }`}>
                    {d.status}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="font-bold text-foreground text-sm leading-snug mb-2">{d.decision}</p>
                    {d.rationale && (
                      <p className="text-xs text-gray-500 leading-relaxed mb-2">{d.rationale}</p>
                    )}
                    <div className="flex items-center flex-wrap gap-2 text-[11px] text-gray-400">
                      <span>{formatDate(d.decided_at)}</span>
                      {d.visibility === "public" && (
                        <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 text-[10px] font-bold uppercase tracking-wider border border-blue-100">
                          🌐 Public
                        </span>
                      )}
                      {d.visibility === "private" && (
                        <span className="px-2 py-0.5 rounded-full bg-gray-50 text-gray-500 text-[10px] font-bold uppercase tracking-wider border border-gray-200">
                          🔒 Private
                        </span>
                      )}
                      {(d.groups || []).map((g) => (
                        <span
                          key={g.id}
                          className="px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 text-[10px] font-bold uppercase tracking-wider border border-purple-100"
                          title={`Visible to members of ${g.name}`}
                        >
                          👥 {g.name}
                        </span>
                      ))}
                      {d.superseded_at && (
                        <span className="text-red-400">Reversed {formatDate(d.superseded_at)}</span>
                      )}
                      {d.reversal_reason && (
                        <span className="italic">— {d.reversal_reason}</span>
                      )}
                    </div>
                  </div>
                  {d.superseded_by && (
                    <button
                      onClick={() => loadChain(d.id)}
                      className="shrink-0 text-[11px] font-bold text-accent hover:underline"
                    >
                      {expandedChain === d.id ? "Hide chain ▲" : "View chain ▼"}
                    </button>
                  )}
                </div>
              </div>

              {/* Reversal chain */}
              {expandedChain === d.id && chains[d.id] && (
                <div className="border-t border-gray-100 px-6 py-4 bg-gray-50/50">
                  <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">Decision chain</p>
                  <div className="space-y-3">
                    {chains[d.id].map((entry, i) => (
                      <div key={entry.id} className="flex gap-3">
                        <div className="flex flex-col items-center">
                          <div className={`w-2.5 h-2.5 rounded-full shrink-0 mt-1 ${entry.is_current ? "bg-accent" : "bg-gray-300"}`}></div>
                          {i < chains[d.id].length - 1 && <div className="w-px flex-1 bg-gray-200 mt-1"></div>}
                        </div>
                        <div className="pb-2">
                          <p className={`text-xs font-semibold ${entry.is_current ? "text-foreground" : "text-gray-400 line-through"}`}>
                            {entry.decision}
                          </p>
                          <p className="text-[11px] text-gray-400 mt-0.5">{formatDate(entry.decided_at)}</p>
                          {entry.reversal_reason && (
                            <p className="text-[11px] text-red-400 mt-0.5">↩ {entry.reversal_reason}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

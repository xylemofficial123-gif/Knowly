"use client";

import { useState, useRef, useEffect } from "react";
import { useUser } from "@clerk/nextjs";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AlertKind = "relitigation" | "decision_forming" | "action_item";

interface Alert {
  id: number;
  kind: AlertKind;
  text: string;
  metadata: Record<string, any>;
  ts: string;
}

interface Summary {
  summary: string;
  decisions: Array<{ decision: string; who?: string; context?: string }>;
  action_items: Array<{ task: string; assigned_to?: string; deadline?: string; priority?: string }>;
  takeaways: string[];
  follow_ups: Array<{ item: string; who?: string }>;
}

const ALERT_STYLES: Record<AlertKind, { border: string; bg: string; label: string; icon: string }> = {
  relitigation: {
    border: "border-yellow-300",
    bg: "bg-yellow-50",
    label: "Already Decided",
    icon: "⚠️",
  },
  decision_forming: {
    border: "border-blue-300",
    bg: "bg-blue-50",
    label: "Decision Forming",
    icon: "🔵",
  },
  action_item: {
    border: "border-green-300",
    bg: "bg-green-50",
    label: "Action Item",
    icon: "✅",
  },
};

export default function MeetingPage() {
  const { user } = useUser();
  const userEmail = user?.emailAddresses?.[0]?.emailAddress ?? "";

  const [phase, setPhase] = useState<"setup" | "active" | "ended">("setup");
  const [title, setTitle] = useState("Team Standup");
  const [speaker, setSpeaker] = useState(user?.firstName ?? "Me");
  const [sessionId, setSessionId] = useState("");
  const [chunkInput, setChunkInput] = useState("");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [wsStatus, setWsStatus] = useState<"disconnected" | "connected" | "processing">("disconnected");
  const [statusMsg, setStatusMsg] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const alertsEndRef = useRef<HTMLDivElement>(null);
  const counterRef = useRef(0);

  // Auto-scroll alerts
  useEffect(() => {
    alertsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [alerts]);

  const startSession = async () => {
    try {
      const res = await fetch(`${API_URL}/api/meeting/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, user_email: userEmail }),
      });
      const data = await res.json();
      const sid = data.session_id;
      setSessionId(sid);

      const wsBase = API_URL.replace(/^https/, "wss").replace(/^http/, "ws");
      const ws = new WebSocket(`${wsBase}/api/meeting/ws/${sid}`);

      ws.onopen = () => {
        setWsStatus("connected");
        setPhase("active");
        setStatusMsg("Connected — send transcript chunks to begin analysis.");
      };

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          handleServerMessage(msg);
        } catch {
          console.error("Bad WS message:", e.data);
        }
      };

      ws.onerror = () => {
        setStatusMsg("WebSocket error — check the backend is running.");
        setWsStatus("disconnected");
      };

      ws.onclose = () => {
        setWsStatus("disconnected");
      };

      wsRef.current = ws;
    } catch (err) {
      setStatusMsg(`Failed to start session: ${err}`);
    }
  };

  const handleServerMessage = (msg: any) => {
    switch (msg.type) {
      case "connected":
        break;
      case "alert":
        counterRef.current += 1;
        setAlerts((prev) => [
          ...prev,
          {
            id: counterRef.current,
            kind: msg.kind as AlertKind,
            text: msg.text,
            metadata: msg.metadata ?? {},
            ts: new Date().toLocaleTimeString(),
          },
        ]);
        break;
      case "processing":
        setWsStatus("processing");
        setStatusMsg("Generating meeting summary…");
        break;
      case "session_ended":
        setSummary({
          summary: msg.summary ?? "",
          decisions: msg.decisions ?? [],
          action_items: msg.action_items ?? [],
          takeaways: msg.takeaways ?? [],
          follow_ups: msg.follow_ups ?? [],
        });
        setPhase("ended");
        setWsStatus("disconnected");
        setStatusMsg("Meeting ended. Summary generated and saved to knowledge base.");
        break;
      case "pong":
        break;
      case "error":
        setStatusMsg(`Error: ${msg.text}`);
        break;
    }
  };

  const sendChunk = () => {
    if (!wsRef.current || !chunkInput.trim() || wsStatus !== "connected") return;
    wsRef.current.send(
      JSON.stringify({
        type: "chunk",
        speaker: speaker,
        text: chunkInput.trim(),
        timestamp: new Date().toISOString(),
      })
    );
    setChunkInput("");
  };

  const endMeeting = () => {
    if (!wsRef.current || wsStatus !== "connected") return;
    wsRef.current.send(JSON.stringify({ type: "end" }));
    setWsStatus("processing");
  };

  const resetSession = () => {
    wsRef.current?.close();
    wsRef.current = null;
    setPhase("setup");
    setAlerts([]);
    setSummary(null);
    setSessionId("");
    setWsStatus("disconnected");
    setStatusMsg("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChunk();
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-gray-50/40">
      {/* Header */}
      <div className="px-8 pt-8 pb-5 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Live Meeting</h1>
            <p className="text-sm text-gray-400 mt-1 font-medium">
              Stream transcript chunks for real-time re-litigation detection and decision capture.
            </p>
          </div>
          {sessionId && (
            <span className="text-[11px] font-mono text-gray-300 bg-gray-100 px-3 py-1 rounded-full">
              {sessionId.slice(0, 8)}…
            </span>
          )}
        </div>

        {/* Status pill */}
        {statusMsg && (
          <div className="mt-3 flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                wsStatus === "connected"
                  ? "bg-green-400"
                  : wsStatus === "processing"
                  ? "bg-yellow-400 animate-pulse"
                  : "bg-gray-300"
              }`}
            />
            <p className="text-[13px] text-gray-500 font-medium">{statusMsg}</p>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* Left panel */}
        <div className="w-[380px] shrink-0 border-r border-gray-100 flex flex-col p-6 gap-5 overflow-y-auto">

          {phase === "setup" && (
            <div className="flex flex-col gap-4">
              <div>
                <label className="block text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">
                  Meeting title
                </label>
                <input
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-accent/30"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Sprint Planning Q2"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">
                  Your name (for attribution)
                </label>
                <input
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-accent/30"
                  value={speaker}
                  onChange={(e) => setSpeaker(e.target.value)}
                  placeholder="e.g. Sachin"
                />
              </div>
              <button
                onClick={startSession}
                className="w-full py-4 rounded-2xl text-white font-bold text-sm transition-all active:scale-95"
                style={{
                  background: "linear-gradient(135deg, #22c55e 0%, #16a34a 100%)",
                  boxShadow: "0 4px 16px rgba(22,163,74,.3)",
                }}
              >
                🎙️ Start Meeting
              </button>
              <div className="p-4 bg-blue-50 rounded-2xl border border-blue-100">
                <p className="text-[12px] font-bold text-blue-600 mb-1">How it works</p>
                <p className="text-[12px] text-blue-500 leading-relaxed">
                  Paste transcript segments as your meeting progresses. Every ~40 words the system
                  checks for re-litigation, forming decisions, and action items — and alerts you in real-time.
                </p>
              </div>
            </div>
          )}

          {phase === "active" && (
            <div className="flex flex-col gap-4">
              <div>
                <label className="block text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">
                  Speaker
                </label>
                <input
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-accent/30"
                  value={speaker}
                  onChange={(e) => setSpeaker(e.target.value)}
                  placeholder="Speaker name"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-2">
                  Transcript chunk
                </label>
                <textarea
                  className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-accent/30 resize-none"
                  rows={6}
                  value={chunkInput}
                  onChange={(e) => setChunkInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Paste or type what was said… (Enter to send)"
                />
                <p className="text-[11px] text-gray-400 mt-1 font-medium">
                  {chunkInput.trim().split(/\s+/).filter(Boolean).length} words — analysis triggers at 40
                </p>
              </div>
              <button
                onClick={sendChunk}
                disabled={!chunkInput.trim()}
                className="w-full py-3 rounded-2xl font-bold text-sm bg-accent text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-95"
              >
                Send Chunk
              </button>
              <div className="border-t border-gray-100 pt-4">
                <button
                  onClick={endMeeting}
                  className="w-full py-3 rounded-2xl font-bold text-sm border-2 border-red-200 text-red-500 hover:bg-red-50 transition-all"
                >
                  End Meeting & Generate Summary
                </button>
              </div>
            </div>
          )}

          {phase === "ended" && (
            <div className="flex flex-col gap-3">
              <div className="p-4 bg-green-50 rounded-2xl border border-green-200 text-center">
                <p className="text-2xl mb-1">✅</p>
                <p className="text-sm font-bold text-green-700">Meeting complete</p>
                <p className="text-[12px] text-green-600 mt-1">
                  Summary saved to your knowledge base.
                </p>
              </div>
              <button
                onClick={resetSession}
                className="w-full py-3 rounded-2xl font-bold text-sm bg-gray-100 text-gray-600 hover:bg-gray-200 transition-all"
              >
                Start New Meeting
              </button>
            </div>
          )}
        </div>

        {/* Right panel — alerts */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="px-6 pt-5 pb-3 border-b border-gray-100 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-[14px] font-bold text-foreground">Real-Time Alerts</h2>
              {alerts.length > 0 && (
                <span className="text-[11px] bg-accent text-white font-bold px-2 py-0.5 rounded-full">
                  {alerts.length}
                </span>
              )}
            </div>
            {alerts.length > 0 && (
              <button
                onClick={() => setAlerts([])}
                className="text-[12px] text-gray-400 hover:text-gray-600 font-bold"
              >
                Clear
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
            {alerts.length === 0 && phase !== "ended" && (
              <div className="text-center py-16">
                <p className="text-4xl mb-3">📡</p>
                <p className="text-sm font-bold text-gray-400">
                  {phase === "setup"
                    ? "Start a session to see real-time alerts"
                    : "Alerts will appear here as you send transcript chunks"}
                </p>
              </div>
            )}

            {alerts.map((alert) => {
              const style = ALERT_STYLES[alert.kind];
              return (
                <div
                  key={alert.id}
                  className={`rounded-2xl border p-4 ${style.border} ${style.bg}`}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-base">{style.icon}</span>
                    <span className="text-[11px] font-black uppercase tracking-widest text-gray-500">
                      {style.label}
                    </span>
                    <span className="ml-auto text-[10px] text-gray-400 font-bold">{alert.ts}</span>
                  </div>
                  <p className="text-[13px] text-gray-700 font-medium whitespace-pre-line leading-relaxed">
                    {alert.text}
                  </p>
                  {alert.kind === "relitigation" && alert.metadata.similarity && (
                    <p className="text-[11px] text-yellow-600 font-bold mt-2">
                      Similarity: {Math.round(alert.metadata.similarity * 100)}%
                    </p>
                  )}
                </div>
              );
            })}

            <div ref={alertsEndRef} />
          </div>

          {/* Summary panel */}
          {phase === "ended" && summary && (
            <div className="border-t border-gray-100 px-6 py-5 overflow-y-auto max-h-[50vh] space-y-5">
              <h2 className="text-[14px] font-black text-foreground uppercase tracking-widest">
                Meeting Summary
              </h2>

              {summary.summary && (
                <p className="text-[14px] text-gray-600 leading-relaxed">{summary.summary}</p>
              )}

              {summary.decisions.length > 0 && (
                <div>
                  <p className="text-[11px] font-black text-gray-400 uppercase tracking-widest mb-2">
                    Decisions
                  </p>
                  <ul className="space-y-2">
                    {summary.decisions.map((d, i) => (
                      <li key={i} className="flex gap-2 text-[13px] text-gray-700">
                        <span className="text-accent font-black shrink-0">•</span>
                        <span>
                          {d.decision}
                          {d.who && <span className="text-gray-400"> — {d.who}</span>}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {summary.action_items.length > 0 && (
                <div>
                  <p className="text-[11px] font-black text-gray-400 uppercase tracking-widest mb-2">
                    Action Items
                  </p>
                  <ul className="space-y-2">
                    {summary.action_items.map((a, i) => (
                      <li
                        key={i}
                        className="flex gap-2 text-[13px] text-gray-700 bg-white rounded-xl p-3 border border-gray-100"
                      >
                        <span className="text-green-500 font-black shrink-0">✓</span>
                        <div>
                          <span className="font-medium">{a.task}</span>
                          {a.assigned_to && (
                            <span className="text-gray-400 text-[12px]"> → {a.assigned_to}</span>
                          )}
                          {a.deadline && a.deadline !== "Not specified" && (
                            <span className="block text-[11px] text-gray-400 font-bold mt-0.5">
                              By {a.deadline}
                            </span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {summary.takeaways.length > 0 && (
                <div>
                  <p className="text-[11px] font-black text-gray-400 uppercase tracking-widest mb-2">
                    Key Takeaways
                  </p>
                  <ul className="space-y-1">
                    {summary.takeaways.map((t, i) => (
                      <li key={i} className="text-[13px] text-gray-600 flex gap-2">
                        <span className="text-accent shrink-0">—</span>
                        {t}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

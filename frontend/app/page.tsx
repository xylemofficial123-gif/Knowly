"use client";

import { useState, useRef, useEffect } from "react";
import OracleResponse from "@/components/OracleResponse";
import CitationCard from "@/components/CitationCard";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Citation {
  url: string;
  source: string;
  display: string;
  excerpt: string;
  freshness: number;
  score: number;
}

interface AgentResult {
  answer: string;
  citations: Citation[];
  chunks_used: string[];
  agent: string;
  query_type: string;
  reasoning_steps: string[];
  confidence: number;
  session_id: string;
  audit_log_id: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  result?: AgentResult;
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [feedbackGiven, setFeedbackGiven] = useState<Record<number, string>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleAsk = async () => {
    if (!question.trim() || loading) return;

    const userMessage: ChatMessage = { role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);
    setError("");

    try {
      // Build history from previous messages (for backend context)
      const history = [...messages, userMessage].map((m) => ({
        role: m.role,
        content: m.role === "assistant" ? m.result?.answer || m.content : m.content,
      }));

      const res = await fetch(`${API_URL}/api/oracle/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: userMessage.content,
          user_email: "sachin.kurup@seedlinglabs.com",
          session_id: sessionId,
          history,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Request failed");
      }

      const data: AgentResult = await res.json();
      if (data.session_id) setSessionId(data.session_id);

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.answer,
        result: data,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Something went wrong";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setSessionId("");
    setError("");
    setQuestion("");
    setFeedbackGiven({});
  };

  const handleFeedback = async (msgIndex: number, rating: string) => {
    const msg = messages[msgIndex];
    if (!msg.result) return;

    setFeedbackGiven((prev) => ({ ...prev, [msgIndex]: rating }));

    try {
      await fetch(`${API_URL}/api/admin/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audit_log_id: msg.result.audit_log_id || "",
          session_id: sessionId,
          user_email: "sachin.kurup@seedlinglabs.com",
          query: messages[msgIndex - 1]?.content || "",
          rating,
          agent: msg.result.agent,
          query_type: msg.result.query_type,
          confidence: msg.result.confidence,
        }),
      });
    } catch (e) {
      console.error("Feedback submission failed:", e);
    }
  };

  const agentLabel = (name: string) => {
    const labels: Record<string, string> = {
      research: "Research Agent",
      onboarding: "Onboarding Agent",
      router: "Router",
    };
    return labels[name] || name;
  };

  const queryTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      factual: "Fact Lookup",
      timeline: "Timeline",
      decision_history: "Decision History",
      who_what: "People & Roles",
      comparison: "Comparison",
      meeting_summary: "Meeting Summary",
      action_items: "Action Items",
      onboarding: "Onboarding",
      multi_hop: "Deep Research",
    };
    return labels[type] || type;
  };

  return (
    <main className="max-w-4xl mx-auto px-4 py-8 flex flex-col h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold mb-1">Knowledge Agent</h1>
          <p className="text-gray-500 text-sm">
            Ask questions about company decisions, meetings, history, and
            projects.
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={handleNewChat}
            className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            New Chat
          </button>
        )}
      </div>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0">
        {messages.length === 0 && !loading && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            Ask a question to get started
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            {msg.role === "user" ? (
              <div className="flex justify-end">
                <div className="bg-blue-600 text-white px-4 py-3 rounded-2xl rounded-br-md max-w-[80%]">
                  {msg.content}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Agent metadata bar */}
                {msg.result?.agent && (
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                      {agentLabel(msg.result.agent)}
                    </span>
                    {msg.result.query_type && (
                      <span className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">
                        {queryTypeLabel(msg.result.query_type)}
                      </span>
                    )}
                    {msg.result.confidence > 0 && (
                      <span>
                        {Math.round(msg.result.confidence * 100)}% confidence
                      </span>
                    )}
                  </div>
                )}

                <OracleResponse
                  answer={msg.content}
                  citations={msg.result?.citations || []}
                />

                {msg.result && msg.result.citations.length > 0 && (
                  <details className="group">
                    <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-700">
                      {msg.result.citations.length} source
                      {msg.result.citations.length > 1 ? "s" : ""} referenced
                    </summary>
                    <div className="grid gap-2 mt-2">
                      {msg.result.citations.map((citation, ci) => (
                        <CitationCard
                          key={ci}
                          citation={citation}
                          index={ci + 1}
                        />
                      ))}
                    </div>
                  </details>
                )}

                {/* Feedback buttons */}
                {msg.result && (
                  <div className="flex items-center gap-2 mt-1">
                    {feedbackGiven[i] ? (
                      <span className="text-xs text-gray-400">
                        {feedbackGiven[i] === "helpful" ? "Marked as helpful" : "Marked as not helpful"} — thanks!
                      </span>
                    ) : (
                      <>
                        <span className="text-xs text-gray-400">Was this helpful?</span>
                        <button
                          onClick={() => handleFeedback(i, "helpful")}
                          className="px-2 py-0.5 text-xs text-green-600 border border-green-200 rounded hover:bg-green-50 transition-colors"
                        >
                          Yes
                        </button>
                        <button
                          onClick={() => handleFeedback(i, "not_helpful")}
                          className="px-2 py-0.5 text-xs text-red-600 border border-red-200 rounded hover:bg-red-50 transition-colors"
                        >
                          No
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3 p-4 bg-white rounded-lg border">
            <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
            <span className="text-gray-500 text-sm">
              Agents analyzing your question...
            </span>
          </div>
        )}

        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input bar — fixed at bottom */}
      <div className="flex gap-3 pt-3 border-t border-gray-200">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            messages.length > 0
              ? "Ask a follow-up..."
              : "What happened in the standup? Who edited X? Brief me on project Y..."
          }
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <button
          onClick={handleAsk}
          disabled={loading || !question.trim()}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "..." : "Ask"}
        </button>
      </div>

      <div className="mt-3 text-center">
        <a
          href="/admin"
          className="text-xs text-gray-400 hover:text-gray-600 underline"
        >
          Admin Dashboard
        </a>
      </div>
    </main>
  );
}

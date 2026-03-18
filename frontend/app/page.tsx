"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import OracleResponse from "@/components/OracleResponse";
import CitationCard from "@/components/CitationCard";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Stats could come from an API endpoint, but keeping it simple for now
  const stats = {
    indexedCount: "1,204",
    verifiedOnly: false,
    allTime: true
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

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
      const res = await fetch(`${API_URL}/api/oracle/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: q,
          user_email: "chaitra.narem@seedlinglabs.com",
          session_id: sessionId,
          history: messages.map(m => ({ role: m.role, content: m.content }))
        }),
      });

      if (!res.ok) throw new Error("API Request Failed");

      const data = await res.json();
      if (data.session_id) setSessionId(data.session_id);

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
  }, [question, loading, messages, sessionId]);

  useEffect(() => {
    const handleCustomQuery = (e: any) => {
      if (e.detail) {
        // detail can now be a string (legacy) or an object { text, result }
        if (typeof e.detail === "string") {
          handleAsk(e.detail);
        } else {
          handleAsk(e.detail.text, e.detail.result);
        }
      }
    };
    window.addEventListener("xylem_query", handleCustomQuery);
    return () => window.removeEventListener("xylem_query", handleCustomQuery);
  }, [handleAsk]);

  return (
    <div className="flex-1 flex flex-col h-screen min-w-0 bg-[#fdfdff]">
      {/* Top Header Stats Bar */}
      <header className="h-20 border-b border-gray-100 bg-white/80 backdrop-blur-md px-10 flex items-center justify-between sticky top-0 z-40 shrink-0">
        <h2 className="text-xl font-bold tracking-tight text-foreground">Query memory</h2>
        <div className="flex items-center gap-3">
          <div className="bg-accent-soft px-4 py-2.5 rounded-2xl flex items-center gap-2 border border-accent/5">
            <span className="text-accent font-bold text-xs">{stats.indexedCount}</span>
            <span className="text-accent/60 text-[10px] font-bold uppercase tracking-widest translate-y-[0.5px]">decisions indexed</span>
          </div>
          <button className="h-10 px-4 rounded-xl border border-gray-100 text-[11px] font-bold text-gray-400 flex items-center gap-2 hover:bg-gray-50 transition-all">
            <span></span> Verified only
          </button>
          <button className="h-10 px-4 rounded-xl border border-gray-100 text-[11px] font-bold text-gray-400 flex items-center gap-2 hover:bg-gray-50 transition-all">
            <span>📅</span> All time
          </button>
          <button className="h-10 px-6 rounded-xl bg-foreground text-white text-[11px] font-bold flex items-center gap-2 shadow-lg shadow-gray-200 hover:bg-gray-800 transition-all">
            <span>🎚️</span> Filters
          </button>
        </div>
      </header>

      {/* Main View Area */}
      <main className="flex-1 overflow-y-auto custom-scrollbar relative px-10 pt-16 pb-32">
        <div className="max-w-4xl mx-auto w-full">
          {messages.length === 0 ? (
            <section className="flex flex-col items-center pt-10 text-center animate-in">
              <div className="w-20 h-20 bg-accent-soft rounded-[2.5rem] flex items-center justify-center text-3xl mb-10 shadow-inner">
                🌱
              </div>
              <h1 className="text-6xl font-black text-foreground mb-6 tracking-tight">
                Ask Xylem anything
              </h1>
              <p className="text-gray-400 text-lg font-medium max-w-xl leading-relaxed mb-16 px-4">
                Query the why behind every decision, meeting, and pivot across your company's entire history.
              </p>

              {/* Dynamic Category Suggestion Grid */}
              <div className="grid grid-cols-2 gap-5 w-full max-w-3xl">
                {["Pricing", "Ownership", "Leadership", "Engineering"].map((category) => (
                  <button
                    key={category}
                    onClick={() => handleAsk(`What are the key decisions in ${category.toLowerCase()}?`)}
                    className="p-8 text-left bg-white border border-gray-100 rounded-[2rem] hover:border-accent/30 hover:shadow-2xl hover:shadow-gray-100 transition-all duration-300 group"
                  >
                    <p className="text-[11px] font-bold text-gray-300 uppercase tracking-widest mb-3 group-hover:text-accent">
                      {category}
                    </p>
                    <p className="text-lg font-bold text-foreground leading-snug group-hover:text-accent-dark">
                      Query the history of {category.toLowerCase()} and its impact...
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
                        <span className="w-2.5 h-2.5 rounded-full bg-accent animate-pulse shadow-[0_0_10px_rgba(90,78,251,0.5)]"></span>
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
              { name: "Slack", color: "bg-purple-400" },
              { name: "Notion", color: "bg-gray-400" },
              { name: "Drive", color: "bg-orange-400" },
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
    </div>
  );
}

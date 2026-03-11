"use client";

import { useState } from "react";
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

interface OracleResult {
  answer: string;
  citations: Citation[];
  chunks_used: string[];
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<OracleResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleAsk = async () => {
    if (!question.trim()) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/api/oracle/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          user_email: "sachin.kurup@seedlinglabs.com",
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Request failed");
      }

      const data: OracleResult = await res.json();
      setResult(data);
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

  return (
    <main className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Knowledge Oracle</h1>
        <p className="text-gray-600">
          Ask questions about company decisions, history, and rationale.
        </p>
      </div>

      <div className="flex gap-3 mb-6">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Why did we choose X? What was decided about Y?"
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <button
          onClick={handleAsk}
          disabled={loading || !question.trim()}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Thinking..." : "Ask"}
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-3 p-6 bg-white rounded-lg border">
          <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full"></div>
          <span className="text-gray-600">Searching knowledge base...</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <OracleResponse answer={result.answer} citations={result.citations} />

          {result.citations.length > 0 && (
            <div>
              <h2 className="text-lg font-semibold mb-3">Sources</h2>
              <div className="grid gap-3">
                {result.citations.map((citation, i) => (
                  <CitationCard key={i} citation={citation} index={i + 1} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="mt-8 text-center">
        <a
          href="/admin"
          className="text-sm text-gray-500 hover:text-gray-700 underline"
        >
          Admin Dashboard
        </a>
      </div>
    </main>
  );
}

"use client";

import { useState, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface AuditEntry {
  id: string;
  user_email: string;
  query: string;
  result_count: string;
  timestamp: string;
}

interface ReviewItem {
  id: string;
  proposed_decision: string;
  proposed_rationale: string;
  confidence: number;
  decision_type: string;
  trigger_phrase: string;
  source_url: string;
  status: string;
  created_at: string;
}

export default function AdminPage() {
  const [tab, setTab] = useState<"audit" | "review">("audit");
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [reviewQueue, setReviewQueue] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchAuditLog = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/audit-log`);
      const data = await res.json();
      setAuditLog(data.entries || []);
    } catch (e) {
      console.error("Failed to fetch audit log:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchReviewQueue = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/review-queue?status=pending`);
      const data = await res.json();
      setReviewQueue(data.items || []);
    } catch (e) {
      console.error("Failed to fetch review queue:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "audit") fetchAuditLog();
    else fetchReviewQueue();
  }, [tab]);

  const handleReview = async (id: string, action: "approve" | "reject") => {
    try {
      const res = await fetch(
        `${API_URL}/api/admin/review-queue/${id}/${action}`,
        { method: "POST" }
      );
      if (res.ok) {
        setReviewQueue((prev) => prev.filter((item) => item.id !== id));
      }
    } catch (e) {
      console.error(`Failed to ${action}:`, e);
    }
  };

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <a href="/" className="text-sm text-blue-600 hover:underline">
          &larr; Back to Oracle
        </a>
      </div>

      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setTab("audit")}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            tab === "audit"
              ? "bg-blue-600 text-white"
              : "bg-gray-200 text-gray-700 hover:bg-gray-300"
          }`}
        >
          Audit Log
        </button>
        <button
          onClick={() => setTab("review")}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            tab === "review"
              ? "bg-blue-600 text-white"
              : "bg-gray-200 text-gray-700 hover:bg-gray-300"
          }`}
        >
          Review Queue
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 p-4">
          <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
          Loading...
        </div>
      )}

      {tab === "audit" && !loading && (
        <div className="bg-white rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Timestamp
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  User
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Question
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Results
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {auditLog.map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm text-gray-600">
                    {entry.timestamp
                      ? new Date(entry.timestamp).toLocaleString()
                      : "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-sm">{entry.user_email}</td>
                  <td className="px-4 py-3 text-sm max-w-md truncate">
                    {entry.query}
                  </td>
                  <td className="px-4 py-3 text-sm">{entry.result_count}</td>
                </tr>
              ))}
              {auditLog.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-8 text-center text-gray-500"
                  >
                    No audit log entries yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "review" && !loading && (
        <div className="grid gap-4">
          {reviewQueue.map((item) => (
            <div key={item.id} className="p-5 bg-white rounded-lg border">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <span className="px-2 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 rounded-full mr-2">
                    {item.decision_type}
                  </span>
                  <span className="text-sm text-gray-500">
                    Confidence: {Math.round(item.confidence * 100)}%
                  </span>
                </div>
                <span className="text-xs text-gray-400">
                  {item.created_at
                    ? new Date(item.created_at).toLocaleString()
                    : ""}
                </span>
              </div>

              <h3 className="font-medium mb-1">{item.proposed_decision}</h3>
              <p className="text-sm text-gray-600 mb-1">
                <span className="font-medium">Rationale:</span>{" "}
                {item.proposed_rationale}
              </p>
              {item.trigger_phrase && (
                <p className="text-xs text-gray-500 mb-3">
                  Trigger: &ldquo;{item.trigger_phrase}&rdquo;
                </p>
              )}

              <div className="flex gap-2">
                <button
                  onClick={() => handleReview(item.id, "approve")}
                  className="px-4 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleReview(item.id, "reject")}
                  className="px-4 py-1.5 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors"
                >
                  Reject
                </button>
                {item.source_url && (
                  <a
                    href={item.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-1.5 text-sm text-blue-600 hover:underline"
                  >
                    View source
                  </a>
                )}
              </div>
            </div>
          ))}
          {reviewQueue.length === 0 && (
            <div className="p-8 text-center text-gray-500 bg-white rounded-lg border">
              No pending items in the review queue.
            </div>
          )}
        </div>
      )}
    </main>
  );
}

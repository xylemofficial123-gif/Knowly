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

interface FeedbackItem {
  id: string;
  query: string;
  rating: string;
  comment: string;
  agent: string;
  query_type: string;
  confidence: number;
  user_email: string;
  created_at: string;
}

interface Metrics {
  overview: {
    total_queries: number;
    queries_today: number;
    queries_this_week: number;
    unique_users: number;
    avg_confidence: number;
    avg_response_time_ms: number;
  };
  feedback: {
    total: number;
    helpful: number;
    not_helpful: number;
    helpfulness_rate: number;
  };
  agent_usage: Record<string, number>;
  query_type_usage: Record<string, number>;
  daily_usage: { date: string; count: number }[];
}

export default function AdminPage() {
  const [tab, setTab] = useState<"metrics" | "audit" | "review" | "feedback">(
    "metrics"
  );
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [reviewQueue, setReviewQueue] = useState<ReviewItem[]>([]);
  const [feedbackList, setFeedbackList] = useState<FeedbackItem[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
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
      const res = await fetch(
        `${API_URL}/api/admin/review-queue?status=pending`
      );
      const data = await res.json();
      setReviewQueue(data.items || []);
    } catch (e) {
      console.error("Failed to fetch review queue:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchFeedback = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/feedback`);
      const data = await res.json();
      setFeedbackList(data.items || []);
    } catch (e) {
      console.error("Failed to fetch feedback:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/metrics`);
      const data = await res.json();
      setMetrics(data);
    } catch (e) {
      console.error("Failed to fetch metrics:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "audit") fetchAuditLog();
    else if (tab === "review") fetchReviewQueue();
    else if (tab === "feedback") fetchFeedback();
    else if (tab === "metrics") fetchMetrics();
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

  const tabs = [
    { key: "metrics", label: "Metrics" },
    { key: "audit", label: "Audit Log" },
    { key: "review", label: "Review Queue" },
    { key: "feedback", label: "Feedback" },
  ] as const;

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <a href="/" className="text-sm text-blue-600 hover:underline">
          &larr; Back to Oracle
        </a>
      </div>

      <div className="flex gap-2 mb-6">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              tab === t.key
                ? "bg-blue-600 text-white"
                : "bg-gray-200 text-gray-700 hover:bg-gray-300"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center gap-2 p-4">
          <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
          Loading...
        </div>
      )}

      {/* Metrics Tab */}
      {tab === "metrics" && !loading && metrics && (
        <div className="space-y-6">
          {/* Overview Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard
              label="Total Queries"
              value={metrics.overview.total_queries}
            />
            <StatCard label="Today" value={metrics.overview.queries_today} />
            <StatCard
              label="This Week"
              value={metrics.overview.queries_this_week}
            />
            <StatCard
              label="Unique Users"
              value={metrics.overview.unique_users}
            />
            <StatCard
              label="Avg Confidence"
              value={`${Math.round(metrics.overview.avg_confidence * 100)}%`}
            />
            <StatCard
              label="Avg Response"
              value={`${Math.round(metrics.overview.avg_response_time_ms / 1000)}s`}
            />
          </div>

          {/* Feedback Summary */}
          <div className="bg-white rounded-lg border p-5">
            <h3 className="font-medium mb-3">Answer Quality (User Feedback)</h3>
            {metrics.feedback.total > 0 ? (
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 rounded-full bg-green-500"
                    style={{
                      width: `${Math.max(metrics.feedback.helpfulness_rate * 2, 20)}px`,
                    }}
                  ></div>
                  <span className="text-sm">
                    {metrics.feedback.helpful} helpful (
                    {metrics.feedback.helpfulness_rate}%)
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div
                    className="h-3 rounded-full bg-red-400"
                    style={{
                      width: `${Math.max((100 - metrics.feedback.helpfulness_rate) * 2, 20)}px`,
                    }}
                  ></div>
                  <span className="text-sm">
                    {metrics.feedback.not_helpful} not helpful
                  </span>
                </div>
                <span className="text-sm text-gray-500">
                  ({metrics.feedback.total} total ratings)
                </span>
              </div>
            ) : (
              <p className="text-sm text-gray-500">
                No feedback collected yet.
              </p>
            )}
          </div>

          {/* Agent & Query Type Usage */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-lg border p-5">
              <h3 className="font-medium mb-3">Agent Usage</h3>
              {Object.keys(metrics.agent_usage).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(metrics.agent_usage).map(([agent, count]) => (
                    <div key={agent} className="flex justify-between text-sm">
                      <span className="capitalize">{agent}</span>
                      <span className="font-mono text-gray-600">{count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No agent data yet (new metrics start tracking from now).
                </p>
              )}
            </div>
            <div className="bg-white rounded-lg border p-5">
              <h3 className="font-medium mb-3">Query Types</h3>
              {Object.keys(metrics.query_type_usage).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(metrics.query_type_usage).map(
                    ([qtype, count]) => (
                      <div
                        key={qtype}
                        className="flex justify-between text-sm"
                      >
                        <span>{qtype}</span>
                        <span className="font-mono text-gray-600">{count}</span>
                      </div>
                    )
                  )}
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  No query type data yet.
                </p>
              )}
            </div>
          </div>

          {/* Daily Usage */}
          {metrics.daily_usage.length > 0 && (
            <div className="bg-white rounded-lg border p-5">
              <h3 className="font-medium mb-3">Daily Queries (Last 7 Days)</h3>
              <div className="flex items-end gap-2 h-32">
                {metrics.daily_usage.map((d) => {
                  const maxCount = Math.max(
                    ...metrics.daily_usage.map((x) => x.count)
                  );
                  const height = maxCount > 0 ? (d.count / maxCount) * 100 : 0;
                  return (
                    <div
                      key={d.date}
                      className="flex-1 flex flex-col items-center gap-1"
                    >
                      <span className="text-xs text-gray-600">{d.count}</span>
                      <div
                        className="w-full bg-blue-500 rounded-t"
                        style={{ height: `${Math.max(height, 4)}%` }}
                      ></div>
                      <span className="text-xs text-gray-400">
                        {d.date.slice(5)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Audit Log Tab */}
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

      {/* Review Queue Tab */}
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

      {/* Feedback Tab */}
      {tab === "feedback" && !loading && (
        <div className="space-y-3">
          {feedbackList.map((f) => (
            <div
              key={f.id}
              className="p-4 bg-white rounded-lg border flex items-start gap-4"
            >
              <span
                className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                  f.rating === "helpful"
                    ? "bg-green-100 text-green-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {f.rating === "helpful" ? "Helpful" : "Not Helpful"}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{f.query}</p>
                {f.comment && (
                  <p className="text-xs text-gray-500 mt-1">{f.comment}</p>
                )}
                <div className="flex gap-3 mt-1 text-xs text-gray-400">
                  <span>{f.agent}</span>
                  <span>{f.query_type}</span>
                  <span>{Math.round(f.confidence * 100)}% confidence</span>
                  <span>
                    {f.created_at
                      ? new Date(f.created_at).toLocaleString()
                      : ""}
                  </span>
                </div>
              </div>
            </div>
          ))}
          {feedbackList.length === 0 && (
            <div className="p-8 text-center text-gray-500 bg-white rounded-lg border">
              No feedback collected yet. Users can rate answers in the chat.
            </div>
          )}
        </div>
      )}
    </main>
  );
}

function StatCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="bg-white rounded-lg border p-4 text-center">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}

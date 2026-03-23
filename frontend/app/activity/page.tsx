"use client";

import { useState, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface LogEntry {
  id: string;
  user_email: string;
  query: string;
  result_count: string;
  timestamp: string;
}

function groupByDay(entries: LogEntry[]) {
  const groups: Record<string, LogEntry[]> = {};
  for (const e of entries) {
    const day = e.timestamp ? new Date(e.timestamp).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "Unknown";
    if (!groups[day]) groups[day] = [];
    groups[day].push(e);
  }
  return groups;
}

function timeAgo(ts: string) {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function ActivityPage() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterUser, setFilterUser] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/api/admin/audit-log?limit=200`)
      .then((r) => r.json())
      .then((d) => {
        setEntries(d.entries || []);
        setTotal(d.total || 0);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = filterUser.trim()
    ? entries.filter((e) => e.user_email.toLowerCase().includes(filterUser.toLowerCase()))
    : entries;

  const uniqueUsers = [...new Set(entries.map((e) => e.user_email))];
  const todayCount = entries.filter((e) => {
    if (!e.timestamp) return false;
    const d = new Date(e.timestamp);
    const now = new Date();
    return d.toDateString() === now.toDateString();
  }).length;

  const grouped = groupByDay(filtered);

  return (
    <div className="flex-1 overflow-y-auto h-full bg-[#fdfdff]">
      <div className="max-w-4xl mx-auto px-10 py-12">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-3xl font-black text-foreground tracking-tight mb-2">Activity Log</h1>
          <p className="text-gray-400 text-sm font-medium">Every query made to Xylem, in order.</p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-4 mb-10">
          {[
            { label: "Total queries", value: total },
            { label: "Today", value: todayCount },
            { label: "Unique users", value: uniqueUsers.length },
          ].map((s) => (
            <div key={s.label} className="bg-white rounded-2xl border border-gray-100 p-5">
              <div className="text-3xl font-black text-foreground mb-1">{s.value}</div>
              <div className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Filter */}
        <div className="mb-6">
          <input
            type="text"
            value={filterUser}
            onChange={(e) => setFilterUser(e.target.value)}
            placeholder="Filter by user email..."
            className="w-full max-w-sm px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-accent/30 focus:border-accent outline-none"
          />
        </div>

        {loading && (
          <div className="flex items-center gap-3 text-gray-400 text-sm py-12">
            <span className="animate-spin w-4 h-4 border-2 border-accent border-t-transparent rounded-full inline-block"></span>
            Loading activity...
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="text-center py-20 bg-white rounded-3xl border border-dashed border-gray-200">
            <div className="text-4xl mb-4">🕒</div>
            <p className="font-bold text-gray-400">No activity yet</p>
            <p className="text-sm text-gray-300 mt-1">Queries made in Xylem will appear here.</p>
          </div>
        )}

        {/* Timeline */}
        <div className="space-y-8">
          {Object.entries(grouped).map(([day, dayEntries]) => (
            <div key={day}>
              <div className="flex items-center gap-3 mb-4">
                <span className="text-[11px] font-black text-gray-400 uppercase tracking-widest">{day}</span>
                <div className="flex-1 h-px bg-gray-100"></div>
                <span className="text-[11px] font-bold text-gray-300">{dayEntries.length} queries</span>
              </div>
              <div className="space-y-2">
                {dayEntries.map((entry) => (
                  <div
                    key={entry.id}
                    className="bg-white rounded-2xl border border-gray-100 px-5 py-4 flex items-start gap-4 hover:border-accent/20 hover:shadow-sm transition-all"
                  >
                    <div className="w-8 h-8 rounded-xl bg-accent-soft flex items-center justify-center shrink-0 mt-0.5">
                      <span className="text-accent text-xs font-black">
                        {entry.user_email?.[0]?.toUpperCase() || "?"}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-foreground mb-1 line-clamp-2">{entry.query}</p>
                      <div className="flex items-center gap-3 text-[11px] text-gray-400 font-medium">
                        <span>{entry.user_email}</span>
                        <span>·</span>
                        <span>{entry.result_count} results</span>
                        <span>·</span>
                        <span>{entry.timestamp ? timeAgo(entry.timestamp) : ""}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

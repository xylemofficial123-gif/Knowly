"use client";

import { useState, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface GraphData {
  totals: { docs: number; chunks: number; decisions: number };
  sources: { id: string; count: number }[];
  clusters: { name: string; count: number; sources: string[]; docs: { title: string; source: string; url: string }[] }[];
  people: { email: string; doc_count: number }[];
  recent_docs: { title: string; source: string; url: string; created_at: string }[];
}

const SOURCE_META: Record<string, { label: string; color: string; bg: string; dot: string }> = {
  drive:    { label: "Google Drive",  color: "text-orange-600", bg: "bg-orange-50 border-orange-100",  dot: "bg-orange-400" },
  calendar: { label: "Calendar",      color: "text-blue-600",   bg: "bg-blue-50 border-blue-100",      dot: "bg-blue-400" },
  slack:    { label: "Slack",         color: "text-teal-600",   bg: "bg-teal-50 border-teal-100",      dot: "bg-teal-500" },
  meet:     { label: "Meet",          color: "text-green-600",  bg: "bg-green-50 border-green-100",    dot: "bg-green-400" },
  upload:   { label: "Uploads",       color: "text-gray-600",   bg: "bg-gray-50 border-gray-200",      dot: "bg-gray-400" },
};

function SourceDot({ source }: { source: string }) {
  const meta = SOURCE_META[source] || SOURCE_META.upload;
  return <span className={`inline-block w-2 h-2 rounded-full ${meta.dot} shrink-0`}></span>;
}

function formatDate(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}

export default function GraphPage() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/admin/graph`)
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  const totalDocs = data?.totals.docs ?? 0;

  return (
    <div className="flex-1 overflow-y-auto h-full">
      <div className="max-w-5xl mx-auto px-10 py-12">
        {/* Header */}
        <div className="mb-10">
          <h1 className="text-3xl font-black text-foreground tracking-tight mb-2">Knowledge Graph</h1>
          <p className="text-gray-400 text-sm font-medium">Everything Xylem knows, organised by source and topic.</p>
        </div>

        {loading && (
          <div className="flex items-center gap-3 text-gray-400 text-sm py-20">
            <span className="animate-spin w-4 h-4 border-2 border-accent border-t-transparent rounded-full inline-block"></span>
            Building graph...
          </div>
        )}

        {data && (
          <div className="space-y-10">
            {/* Totals */}
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: "Documents", value: data.totals.docs, icon: "📄" },
                { label: "Searchable chunks", value: data.totals.chunks, icon: "🧩" },
                { label: "Decisions extracted", value: data.totals.decisions, icon: "⚖️" },
              ].map((s) => (
                <div key={s.label} className="bg-white rounded-2xl border border-gray-100 p-5 flex items-center gap-4">
                  <span className="text-3xl">{s.icon}</span>
                  <div>
                    <div className="text-2xl font-black text-foreground">{s.value}</div>
                    <div className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">{s.label}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Source breakdown — visual bars */}
            <section className="bg-white rounded-2xl border border-gray-100 p-6">
              <h2 className="text-sm font-black text-gray-400 uppercase tracking-widest mb-5">Sources</h2>
              <div className="space-y-4">
                {data.sources.map((s) => {
                  const meta = SOURCE_META[s.id] || SOURCE_META.upload;
                  const pct = totalDocs > 0 ? Math.round((s.count / totalDocs) * 100) : 0;
                  return (
                    <div key={s.id}>
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span className={`w-2.5 h-2.5 rounded-full ${meta.dot}`}></span>
                          <span className="text-sm font-bold text-foreground">{meta.label}</span>
                        </div>
                        <span className="text-sm font-mono text-gray-500">{s.count} docs ({pct}%)</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full ${meta.dot} transition-all duration-700`}
                          style={{ width: `${pct}%` }}
                        ></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Project clusters */}
            <section>
              <h2 className="text-sm font-black text-gray-400 uppercase tracking-widest mb-4">Topic clusters</h2>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {data.clusters.map((cluster) => (
                  <div key={cluster.name} className="bg-white rounded-2xl border border-gray-100 p-5 hover:border-accent/30 hover:shadow-sm transition-all">
                    <div className="flex items-start justify-between mb-3">
                      <p className="font-black text-foreground text-base">{cluster.name}</p>
                      <span className="text-[11px] font-black text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{cluster.count}</span>
                    </div>
                    <div className="flex gap-1.5 flex-wrap mb-3">
                      {cluster.sources.map((src) => {
                        const meta = SOURCE_META[src] || SOURCE_META.upload;
                        return (
                          <span key={src} className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${meta.bg} ${meta.color}`}>
                            {meta.label}
                          </span>
                        );
                      })}
                    </div>
                    <button
                      onClick={() => setExpandedCluster(expandedCluster === cluster.name ? null : cluster.name)}
                      className="text-[11px] font-bold text-accent hover:underline"
                    >
                      {expandedCluster === cluster.name ? "Hide docs ▲" : `See ${cluster.docs.length} docs ▼`}
                    </button>
                    {expandedCluster === cluster.name && (
                      <div className="mt-3 space-y-1.5">
                        {cluster.docs.map((doc, i) => (
                          <div key={i} className="flex items-start gap-2">
                            <SourceDot source={doc.source} />
                            {doc.url ? (
                              <a href={doc.url} target="_blank" rel="noopener noreferrer" className="text-[12px] text-gray-600 hover:text-accent line-clamp-1 leading-snug">
                                {doc.title}
                              </a>
                            ) : (
                              <span className="text-[12px] text-gray-500 line-clamp-1 leading-snug">{doc.title}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>

            {/* Recent ingestions */}
            <section>
              <h2 className="text-sm font-black text-gray-400 uppercase tracking-widest mb-4">Recently ingested</h2>
              <div className="space-y-2">
                {data.recent_docs.map((doc, i) => {
                  const meta = SOURCE_META[doc.source] || SOURCE_META.upload;
                  return (
                    <div key={i} className="bg-white rounded-xl border border-gray-100 px-4 py-3 flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${meta.dot} shrink-0`}></span>
                      <div className="flex-1 min-w-0">
                        {doc.url ? (
                          <a href={doc.url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-foreground hover:text-accent truncate block">
                            {doc.title}
                          </a>
                        ) : (
                          <span className="text-sm font-medium text-foreground truncate block">{doc.title}</span>
                        )}
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${meta.bg} ${meta.color} shrink-0`}>
                        {meta.label}
                      </span>
                      <span className="text-[11px] text-gray-400 shrink-0">{formatDate(doc.created_at)}</span>
                    </div>
                  );
                })}
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

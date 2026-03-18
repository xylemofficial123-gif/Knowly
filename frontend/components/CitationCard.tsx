"use client";

interface Citation {
  url: string;
  source: string;
  display: string;
  excerpt: string;
  freshness: number;
  score: number;
}

interface Props {
  citation: Citation;
  index: number;
}

const sourceIcons: Record<string, string> = {
  slack: "\uD83D\uDCAC",
  clickup: "\uD83D\uDCCB",
  meet: "\uD83C\uDFA5",
  unknown: "\uD83D\uDCC4",
};

const sourceNames: Record<string, string> = {
  slack: "Slack Message",
  clickup: "ClickUp Task",
  meet: "Google Meet Transcript",
  drive: "Google Drive File",
};

function FreshnessBadge({ freshness }: { freshness: number }) {
  if (freshness > 0.7) {
    return (
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.4)]"></span>
        <span className="text-[10px] uppercase tracking-wider font-bold text-green-600">Current</span>
      </div>
    );
  }
  if (freshness >= 0.4) {
    return (
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.4)]"></span>
        <span className="text-[10px] uppercase tracking-wider font-bold text-yellow-600">Aged</span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.4)]"></span>
      <span className="text-[10px] uppercase tracking-wider font-bold text-red-600">Archival</span>
    </div>
  );
}

export default function CitationCard({ citation, index }: Props) {
  const icon = sourceIcons[citation.source] || sourceIcons.unknown;
  const sourceName = sourceNames[citation.source] || "External Source";

  return (
    <div className="bg-white border border-gray-100 rounded-[2rem] p-6 hover:border-accent/30 hover:shadow-2xl hover:shadow-gray-100 transition-all duration-300 group cursor-default relative overflow-hidden">
      <div className="absolute top-0 right-0 p-3 opacity-5 group-hover:opacity-10 transition-opacity">
        <span className="text-5xl grayscale group-hover:grayscale-0 transition-all duration-500">{icon}</span>
      </div>
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-accent text-white flex items-center justify-center text-[10px] font-black shadow-lg shadow-accent/20">
              {index}
            </span>
            <span className="text-[10px] uppercase tracking-widest font-black text-gray-400">
              {sourceName}
            </span>
          </div>
          <FreshnessBadge freshness={citation.freshness} />
        </div>

        <div className="mb-4">
          {citation.url ? (
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[15px] font-bold text-foreground hover:text-accent transition-colors line-clamp-1 block underline-offset-4 decoration-accent/30 hover:underline"
            >
              {citation.display || "View Original Source"}
              <svg className="w-3.5 h-3.5 inline-block ml-1.5 opacity-0 group-hover:opacity-100 transition-all translate-x-[-4px] group-hover:translate-x-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          ) : (
            <span className="text-[15px] font-bold text-foreground block line-clamp-1">
              {citation.display || "Archived Content"}
            </span>
          )}
        </div>

        <div className="relative">
          <p className="text-[13px] text-gray-500 font-medium leading-relaxed line-clamp-3">
            "{citation.excerpt.length > 250 ? citation.excerpt.slice(0, 250) + "..." : citation.excerpt}"
          </p>
          <div className="h-0.5 w-0 group-hover:w-full bg-accent/20 mt-4 transition-all duration-700 rounded-full"></div>
        </div>
      </div>
    </div>
  );
}

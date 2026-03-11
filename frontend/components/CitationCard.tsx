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

function FreshnessBadge({ freshness }: { freshness: number }) {
  if (freshness > 0.7) {
    return (
      <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded-full">
        Recent
      </span>
    );
  }
  if (freshness >= 0.4) {
    return (
      <span className="px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-700 rounded-full">
        Moderate
      </span>
    );
  }
  return (
    <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
      Old
    </span>
  );
}

export default function CitationCard({ citation, index }: Props) {
  const icon = sourceIcons[citation.source] || sourceIcons.unknown;

  return (
    <div className="p-4 bg-white rounded-lg border hover:border-gray-400 transition-colors">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span className="text-sm font-medium text-gray-500">
            Source {index}
          </span>
          {citation.url ? (
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-blue-600 hover:underline font-medium"
            >
              {citation.display || "View source"}
            </a>
          ) : (
            <span className="text-sm text-gray-700 font-medium">
              {citation.display || "Unknown source"}
            </span>
          )}
        </div>
        <FreshnessBadge freshness={citation.freshness} />
      </div>
      <p className="text-sm text-gray-600 line-clamp-3">
        {citation.excerpt.slice(0, 300)}
      </p>
    </div>
  );
}

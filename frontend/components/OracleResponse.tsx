interface Citation {
  url: string;
  source: string;
  display: string;
  excerpt: string;
  freshness: number;
  score: number;
}

interface Props {
  answer: string;
  citations: Citation[];
}

export default function OracleResponse({ answer, citations }: Props) {
  const renderAnswer = () => {
    const parts = answer.split(/(\[SOURCE_\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[SOURCE_(\d+)\]/);
      if (match) {
        const idx = parseInt(match[1]) - 1;
        const citation = citations[idx];
        if (citation?.url) {
          return (
            <a
              key={i}
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-1.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
              title={citation.display}
            >
              {match[1]}
            </a>
          );
        }
        return (
          <span
            key={i}
            className="inline-flex items-center px-1.5 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded"
          >
            {match[1]}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div className="p-6 bg-white rounded-lg border">
      <div className="prose max-w-none leading-relaxed">{renderAnswer()}</div>
    </div>
  );
}

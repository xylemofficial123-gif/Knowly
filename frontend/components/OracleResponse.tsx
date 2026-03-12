"use client";

import ReactMarkdown from "react-markdown";

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
  // Replace [N] with a placeholder that won't be mangled by markdown,
  // then render citations as clickable badges after markdown processing.
  const CITE_PLACEHOLDER = "%%CITE_";

  // Pre-process: [1] → %%CITE_1%%
  const preprocessed = answer.replace(/\[(\d+)\]/g, `${CITE_PLACEHOLDER}$1%%`);

  return (
    <div className="p-6 bg-white rounded-lg border">
      <div className="prose prose-sm max-w-none leading-relaxed">
        <ReactMarkdown
          components={{
            // Render text nodes, replacing cite placeholders with badges
            text: undefined,
            p: ({ children, ...props }) => (
              <p {...props} className="mb-3 last:mb-0">
                {processChildren(children, citations)}
              </p>
            ),
            li: ({ children, ...props }) => (
              <li {...props}>{processChildren(children, citations)}</li>
            ),
            strong: ({ children, ...props }) => (
              <strong {...props} className="font-semibold">
                {children}
              </strong>
            ),
          }}
        >
          {preprocessed}
        </ReactMarkdown>
      </div>
    </div>
  );
}

function processChildren(
  children: React.ReactNode,
  citations: { url: string; display: string }[]
): React.ReactNode {
  if (!children) return children;

  if (typeof children === "string") {
    return replaceCitePlaceholders(children, citations);
  }

  if (Array.isArray(children)) {
    return children.map((child, i) => {
      if (typeof child === "string") {
        return (
          <span key={i}>{replaceCitePlaceholders(child, citations)}</span>
        );
      }
      return child;
    });
  }

  return children;
}

function replaceCitePlaceholders(
  text: string,
  citations: { url: string; display: string }[]
): React.ReactNode {
  const parts = text.split(/(%%CITE_\d+%%)/g);
  if (parts.length === 1) return text;

  return parts.map((part, i) => {
    const match = part.match(/%%CITE_(\d+)%%/);
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
            className="inline-flex items-center px-1.5 py-0.5 mx-0.5 text-xs font-medium bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors no-underline"
            title={citation.display}
          >
            {match[1]}
          </a>
        );
      }
      return (
        <span
          key={i}
          className="inline-flex items-center px-1.5 py-0.5 mx-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded"
        >
          {match[1]}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

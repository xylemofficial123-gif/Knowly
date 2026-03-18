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
  const CITE_PLACEHOLDER = "%%CITE_";
  const preprocessed = answer.replace(/\[(\d+)\]/g, `${CITE_PLACEHOLDER}$1%%`);

  return (
    <div className="bg-white border border-gray-100 rounded-[2.5rem] p-8 shadow-xl shadow-gray-100/50 relative overflow-hidden group">
      <div className="absolute top-0 right-0 w-32 h-32 bg-accent/5 rounded-full blur-3xl -mr-16 -mt-16 group-hover:bg-accent/10 transition-colors duration-1000"></div>
      
      <div className="prose prose-slate max-w-none leading-relaxed select-text relative z-10">
        <ReactMarkdown
          components={{
            p: ({ children, ...props }) => (
              <p {...props} className="mb-5 last:mb-0 text-[16px] text-gray-700 leading-relaxed">
                {processChildren(children, citations)}
              </p>
            ),
            li: ({ children, ...props }) => (
              <li {...props} className="mb-2 text-[15px] text-gray-600 leading-relaxed font-medium">
                {processChildren(children, citations)}
              </li>
            ),
            strong: ({ children, ...props }) => (
              <strong {...props} className="font-extrabold text-foreground tracking-tight">
                {children}
              </strong>
            ),
            h1: ({ children, ...props }) => (
              <h1 {...props} className="text-2xl font-black text-foreground mb-6 tracking-tighter">
                {children}
              </h1>
            ),
            h2: ({ children, ...props }) => (
              <h2 {...props} className="text-xl font-black text-foreground mb-4 mt-8 tracking-tighter uppercase text-[11px] tracking-[0.2em] text-accent">
                {children}
              </h2>
            ),
            code: ({ children, ...props }) => (
              <code {...props} className="font-mono text-accent font-bold bg-accent-soft px-1.5 py-0.5 rounded border border-accent/10 text-sm">
                {children}
              </code>
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
            className="inline-flex items-center justify-center w-5 h-5 mx-1 text-[10px] font-black bg-accent text-white rounded-full shadow-lg shadow-accent/20 hover:scale-110 transition-all no-underline translate-y-[-2px]"
            title={citation.display}
          >
            {match[1]}
          </a>
        );
      }
      return (
        <span
          key={i}
          className="inline-flex items-center justify-center w-5 h-5 mx-1 text-[10px] font-black bg-gray-100 text-gray-400 rounded-full translate-y-[-2px]"
        >
          {match[1]}
        </span>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

"use client";

import { useState } from "react";
import Link from "next/link";
import PublicNav from "@/components/PublicNav";

const SECTIONS = [
  { id: "overview",      label: "Overview"             },
  { id: "asking",        label: "Asking questions"     },
  { id: "sources",       label: "Connected sources"    },
  { id: "citations",     label: "Citations"            },
  { id: "decisions",     label: "Decisions index"      },
  { id: "activity",      label: "Activity log"         },
  { id: "graph",         label: "Knowledge graph"      },
  { id: "admin",         label: "Admin panel"          },
  { id: "access",        label: "Access control"       },
  { id: "faq",           label: "FAQ"                  },
];

export default function DocsPage() {
  const [active, setActive] = useState("overview");

  const scrollTo = (id: string) => {
    setActive(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#f8fdf9",
        fontFamily: "Inter, -apple-system, sans-serif",
        color: "#052e16",
      }}
    >
      <PublicNav />

      <div style={{ display: "flex", flex: 1 }}>

        {/* ── Sidebar ──────────────────────────────────────────────────────── */}
        <aside
          style={{
            width: 220,
            flexShrink: 0,
            position: "sticky",
            top: 0,
            height: "calc(100vh - 60px)",
            overflowY: "auto",
            padding: "32px 20px",
            borderRight: "1px solid rgba(134,239,172,.4)",
            background: "rgba(240,253,244,.6)",
          }}
        >
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "2px", textTransform: "uppercase", color: "#6bad7e", marginBottom: 14 }}>
            Documentation
          </div>
          <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => scrollTo(s.id)}
                style={{
                  background: active === s.id ? "rgba(220,252,231,.8)" : "transparent",
                  border: "none",
                  borderRadius: 8,
                  padding: "7px 12px",
                  fontSize: 13,
                  fontWeight: active === s.id ? 600 : 400,
                  color: active === s.id ? "#14532d" : "#4d7c5a",
                  textAlign: "left",
                  cursor: "pointer",
                  transition: "all .15s",
                  borderLeft: active === s.id ? "2px solid #22c55e" : "2px solid transparent",
                  width: "100%",
                }}
              >
                {s.label}
              </button>
            ))}
          </nav>

          <div
            style={{
              marginTop: 32,
              padding: "14px 14px",
              background: "rgba(220,252,231,.6)",
              border: "1px solid rgba(134,239,172,.5)",
              borderRadius: 10,
              fontSize: 12,
              color: "#3d6b50",
              lineHeight: 1.6,
            }}
          >
            <strong style={{ color: "#14532d", display: "block", marginBottom: 4 }}>Need help?</strong>
            Ask Xylem directly — it knows its own docs.
            <Link href="/sign-in" style={{ display: "block", marginTop: 8, color: "#16a34a", fontWeight: 600, textDecoration: "none", fontSize: 12 }}>
              Sign in to ask →
            </Link>
          </div>
        </aside>

        {/* ── Content ──────────────────────────────────────────────────────── */}
        <main
          style={{
            flex: 1,
            padding: "48px 56px 80px",
            maxWidth: 780,
            overflowY: "auto",
          }}
          onScroll={(e) => {
            const el = e.currentTarget;
            for (const s of SECTIONS) {
              const section = document.getElementById(s.id);
              if (section && section.offsetTop - el.scrollTop - 120 <= 0) setActive(s.id);
            }
          }}
        >

          {/* ── Overview ─────────────────────────────────────────── */}
          <DocSection id="overview" title="Overview">
            <p>
              Xylem is an AI-powered institutional memory system for Seedling Labs. It continuously indexes your company&apos;s knowledge sources — Slack, Google Drive, Meet transcripts, ClickUp tasks, and Calendar — and makes everything queryable through a conversational interface.
            </p>
            <p>
              Unlike a traditional search engine, Xylem <em>synthesises</em> answers across sources, attributing every claim to its origin. This means you get a direct answer with citations, not a list of links to scroll through.
            </p>
            <Callout>
              Xylem is named after the vascular tissue in plants that carries water and minerals from roots to leaves. In the same way, Xylem carries information from every corner of your organisation to wherever it&apos;s needed.
            </Callout>
            <h3>How it works</h3>
            <ol>
              <li>Sources are connected via OAuth or API tokens in the <strong>Connections</strong> tab.</li>
              <li>A Celery background worker ingests documents, chunking and embedding them into a Qdrant vector store.</li>
              <li>When you ask a question, a multi-agent pipeline retrieves relevant chunks, reasons across them, and returns a cited answer.</li>
              <li>Answers and source metadata are stored so the system improves over time and can detect drift.</li>
            </ol>
          </DocSection>

          {/* ── Asking questions ──────────────────────────────────── */}
          <DocSection id="asking" title="Asking questions">
            <p>
              The main interface is the <strong>Query memory</strong> view. Type any question in plain English — Xylem is designed to understand context, not just keywords.
            </p>
            <h3>Example queries</h3>
            <CodeBlock>{`Why did we change our pricing model?
What was decided in the Q3 strategy meeting?
Who owns the payments integration?
What are the engineering constraints on mobile-first?
Has anything changed about our hiring freeze decision?`}</CodeBlock>
            <h3>Keyboard shortcuts</h3>
            <Table
              headers={["Shortcut", "Action"]}
              rows={[
                ["Enter", "Send message"],
                ["Shift + Enter", "New line in message"],
                ["↑ / ↓", "Navigate suggestion cards"],
              ]}
            />
            <h3>Session continuity</h3>
            <p>
              Xylem maintains conversation context within a session. You can ask follow-up questions and it will remember what was discussed. Start a new session by refreshing the page.
            </p>
            <h3>Suggestion cards</h3>
            <p>
              When no messages exist, four category suggestion cards are shown (Pricing, Ownership, Leadership, Engineering). Click any to run a pre-built query for that topic.
            </p>
          </DocSection>

          {/* ── Connected sources ─────────────────────────────────── */}
          <DocSection id="sources" title="Connected sources">
            <p>
              Xylem connects to five source types. Each is configured in <strong>Settings → Connections</strong>. Per-user OAuth means the system only indexes content the signed-in user can access.
            </p>
            <Table
              headers={["Source", "What's indexed", "How to connect"]}
              rows={[
                ["Slack", "All channel messages you have access to, DMs excluded", "OAuth via Connections tab"],
                ["Google Drive", "Docs, Sheets, Slides, PDFs you own or can view", "Per-user Google OAuth"],
                ["Google Meet", "Auto-generated transcripts attached to calendar events", "Included with Google OAuth"],
                ["ClickUp", "Tasks, descriptions, comments, status changes", "API token in Connections tab"],
                ["Google Calendar", "Event titles, descriptions, attendees", "Included with Google OAuth"],
              ]}
            />
            <h3>Ingestion schedule</h3>
            <p>
              Sources sync on a Celery beat schedule. Google Drive and Meet sync every 6 hours; Slack syncs every 2 hours; ClickUp syncs every 4 hours. Manual re-ingestion can be triggered from the <strong>Ingest</strong> tab.
            </p>
            <Callout type="info">
              Only content you personally have access to is indexed under your account. An admin&apos;s index is broader than a member&apos;s — see <button onClick={() => scrollTo("access")} style={{ background: "none", border: "none", color: "#16a34a", fontWeight: 600, cursor: "pointer", padding: 0, fontSize: "inherit" }}>Access control</button> for details.
            </Callout>
          </DocSection>

          {/* ── Citations ─────────────────────────────────────────── */}
          <DocSection id="citations" title="Citations">
            <p>
              Every answer Xylem produces includes numbered citations in the format <code>[1]</code>, <code>[2]</code>, etc. These appear inline in the text and as expandable citation cards below the answer.
            </p>
            <h3>Citation card anatomy</h3>
            <p>Each citation card shows:</p>
            <ul>
              <li><strong>Source type</strong> — Slack, Drive, Meet, ClickUp, or Calendar</li>
              <li><strong>Title</strong> — Document name, channel name, or task title</li>
              <li><strong>Author</strong> — Who created or sent the content</li>
              <li><strong>Date</strong> — When it was created (DD/MM/YYYY, IST)</li>
              <li><strong>Excerpt</strong> — The relevant passage that informed the answer</li>
            </ul>
            <Callout>
              All timestamps are shown in IST (GMT+5:30) regardless of where the source content was created. This is the standard for Seedling Labs.
            </Callout>
            <h3>Confidence scoring</h3>
            <p>
              Citations are ranked by relevance score. The top-ranked sources appear first. If a source scores below a minimum threshold it is excluded from the answer to avoid noise.
            </p>
          </DocSection>

          {/* ── Decisions ─────────────────────────────────────────── */}
          <DocSection id="decisions" title="Decisions index">
            <p>
              The <strong>Decisions</strong> tab lists key decisions that Xylem has identified across all indexed sources. Decisions are extracted automatically using LLM reasoning — no manual tagging required.
            </p>
            <h3>What counts as a decision</h3>
            <p>
              Xylem looks for conclusive statements across sources: a Slack message confirming a product direction, a doc summarising a meeting outcome, a ClickUp task marked done with a conclusion. Ambiguous discussions that never reached a conclusion are not surfaced as decisions.
            </p>
            <h3>Decision detail view</h3>
            <p>Each decision record contains:</p>
            <ul>
              <li>A one-sentence summary of the decision</li>
              <li>The date it was made</li>
              <li>The original sources it was inferred from (with citations)</li>
              <li>A drift status — <em>current</em>, <em>possibly outdated</em>, or <em>superseded</em></li>
            </ul>
          </DocSection>

          {/* ── Activity log ──────────────────────────────────────── */}
          <DocSection id="activity" title="Activity log">
            <p>
              The <strong>Activity</strong> tab provides a full audit trail of:
            </p>
            <ul>
              <li>Ingestion runs — when each source was synced and how many items were indexed</li>
              <li>Query events — what was asked, by whom, and when</li>
              <li>Drift alerts — when the system detected a potentially outdated decision</li>
            </ul>
            <p>
              Activity is paginated and filterable by type and date. Admins see activity for all users; members see only their own.
            </p>
          </DocSection>

          {/* ── Knowledge graph ───────────────────────────────────── */}
          <DocSection id="graph" title="Knowledge graph">
            <p>
              The <strong>Graph</strong> tab renders an interactive force-directed visualisation of how topics, decisions, and sources interconnect across your indexed knowledge.
            </p>
            <h3>Node types</h3>
            <Table
              headers={["Node type", "Colour", "Represents"]}
              rows={[
                ["Decision", "Amber", "A key company decision"],
                ["Source", "Blue", "A document, channel, or meeting"],
                ["Topic", "Green", "A recurring theme or subject area"],
              ]}
            />
            <h3>Interactions</h3>
            <ul>
              <li><strong>Click a node</strong> — see its details and connected nodes</li>
              <li><strong>Drag</strong> — reposition nodes</li>
              <li><strong>Scroll</strong> — zoom in and out</li>
              <li><strong>Double-click</strong> — navigate to the source document or decision</li>
            </ul>
          </DocSection>

          {/* ── Admin panel ───────────────────────────────────────── */}
          <DocSection id="admin" title="Admin panel">
            <p>
              The <strong>Admin</strong> panel (available to users with the <code>admin</code> or <code>owner</code> role) provides controls over the entire workspace.
            </p>
            <h3>Sections</h3>
            <Table
              headers={["Section", "Purpose"]}
              rows={[
                ["Users", "View all workspace members, their roles, and their connection status"],
                ["Connections", "See which sources are connected for each user; trigger manual re-ingestion"],
                ["Ingest", "Monitor ingestion queue, run manual ingestion per source or per user"],
                ["Guardian", "View the content safety log and configure exclusion rules"],
                ["System", "View system health, queue depth, and Qdrant collection stats"],
              ]}
            />
            <Callout type="warning">
              Admin actions affect all users in the workspace. Triggering a full re-ingestion will queue a large number of Celery tasks — do this during off-peak hours.
            </Callout>
          </DocSection>

          {/* ── Access control ────────────────────────────────────── */}
          <DocSection id="access" title="Access control">
            <p>
              Xylem uses a three-tier role system to control what each user can see and do.
            </p>
            <Table
              headers={["Role", "Can query", "Can see admin panel", "Index scope"]}
              rows={[
                ["owner", "✓", "Full access", "All connected sources workspace-wide"],
                ["admin", "✓", "Full access", "All connected sources workspace-wide"],
                ["member", "✓", "None", "Only sources the member has personally connected"],
              ]}
            />
            <h3>Per-user OAuth</h3>
            <p>
              Each member connects their own Google account. Xylem uses that account&apos;s credentials to fetch Drive and Meet content — meaning it only ever sees files that user can access. This enforces Google&apos;s own permission model without any additional configuration.
            </p>
            <h3>Slack ACL</h3>
            <p>
              Slack is connected at the workspace level by an admin. Individual users can request access to specific channels. Xylem respects Slack&apos;s private channel membership — private channel content is only surfaced in answers for users who are members of that channel.
            </p>
          </DocSection>

          {/* ── FAQ ───────────────────────────────────────────────── */}
          <DocSection id="faq" title="FAQ">
            <FAQ q="Does Xylem send my data to third-party AI providers?">
              Xylem uses a free-tier fallback chain: Gemini → Groq → OpenRouter. Your content is sent to these APIs for processing. Embeddings are generated locally using a self-hosted BAAI/bge model, so document content never leaves your server for embedding.
            </FAQ>
            <FAQ q="How long does initial ingestion take?">
              For a typical company with 2–3 years of Drive, Slack, and Meet data, initial ingestion takes 30–90 minutes depending on volume. Subsequent syncs are incremental and take 1–5 minutes.
            </FAQ>
            <FAQ q="Can I exclude certain channels or folders from indexing?">
              Yes. The <strong>Guardian</strong> section in the Admin panel lets you add exclusion rules by source type, channel name, folder path, or keyword pattern. Excluded content is never embedded or stored.
            </FAQ>
            <FAQ q="What happens if I disconnect a source?">
              Existing indexed content from that source remains in the vector store until a full re-ingestion is triggered. Future syncs for that source are paused. You can manually purge a source&apos;s content from the Admin panel.
            </FAQ>
            <FAQ q="Is there a limit on how much can be indexed?">
              There is no hard limit. Qdrant stores vectors efficiently — 1 million chunks (roughly 10,000 long documents) uses approximately 1 GB of storage. Xylem is designed to scale with your company.
            </FAQ>
            <FAQ q="How do I add a new team member?">
              New users sign in with their Google Workspace account. They are automatically provisioned as <code>member</code> role. An admin can promote them to <code>admin</code> from the Users section of the Admin panel.
            </FAQ>
          </DocSection>

        </main>
      </div>

      {/* Footer */}
      <div
        style={{
          textAlign: "center",
          padding: "16px 20px",
          fontSize: 11,
          color: "#86bfa0",
          borderTop: "1px solid rgba(134,239,172,.3)",
          background: "rgba(220,252,231,.3)",
        }}
      >
        Xylem by Seedling Labs — AI knowledge intelligence for growing teams
      </div>
    </div>
  );
}

/* ── Shared doc components ────────────────────────────────────────────────── */

function DocSection({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section
      id={id}
      style={{ marginBottom: 64, scrollMarginTop: 24 }}
    >
      <h2
        style={{
          fontSize: 26,
          fontWeight: 800,
          letterSpacing: -0.8,
          color: "#052e16",
          marginBottom: 18,
          paddingBottom: 12,
          borderBottom: "1px solid rgba(134,239,172,.4)",
        }}
      >
        {title}
      </h2>
      <div
        style={{
          display: "flex",
          flexDirection: "column" as const,
          gap: 14,
          fontSize: 14.5,
          lineHeight: 1.75,
          color: "#1a4731",
        }}
      >
        {children}
      </div>
    </section>
  );
}

function Callout({ children, type = "note" }: { children: React.ReactNode; type?: "note" | "info" | "warning" }) {
  const styles = {
    note:    { bg: "rgba(220,252,231,.5)", border: "#86efac", icon: "🌱" },
    info:    { bg: "rgba(219,234,254,.4)", border: "#93c5fd", icon: "ℹ️"  },
    warning: { bg: "rgba(254,243,199,.5)", border: "#fcd34d", icon: "⚠️" },
  }[type];

  return (
    <div
      style={{
        background: styles.bg,
        border: `1px solid ${styles.border}`,
        borderRadius: 10,
        padding: "14px 16px",
        display: "flex",
        gap: 10,
        alignItems: "flex-start",
        fontSize: 13.5,
        color: "#1a4731",
      }}
    >
      <span style={{ flexShrink: 0, marginTop: 1 }}>{styles.icon}</span>
      <div>{children}</div>
    </div>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre
      style={{
        background: "#052e16",
        color: "#86efac",
        borderRadius: 10,
        padding: "16px 18px",
        fontSize: 13,
        lineHeight: 1.7,
        overflowX: "auto",
        fontFamily: "ui-monospace, 'Cascadia Code', monospace",
        margin: 0,
      }}
    >
      {children}
    </pre>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div style={{ overflowX: "auto" as const, margin: "4px 0" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 13.5,
        }}
      >
        <thead>
          <tr>
            {headers.map((h) => (
              <th
                key={h}
                style={{
                  textAlign: "left",
                  padding: "8px 14px",
                  background: "rgba(220,252,231,.5)",
                  borderBottom: "1px solid rgba(134,239,172,.5)",
                  color: "#14532d",
                  fontWeight: 700,
                  fontSize: 11,
                  letterSpacing: "0.8px",
                  textTransform: "uppercase",
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: "1px solid rgba(134,239,172,.2)" }}>
              {row.map((cell, j) => (
                <td
                  key={j}
                  style={{
                    padding: "10px 14px",
                    color: "#1a4731",
                    background: i % 2 === 0 ? "transparent" : "rgba(240,253,244,.4)",
                    verticalAlign: "top",
                  }}
                  dangerouslySetInnerHTML={{ __html: cell }}
                />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FAQ({ q, children }: { q: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <h4 style={{ fontSize: 15, fontWeight: 700, color: "#052e16", marginBottom: 6 }}>{q}</h4>
      <div style={{ fontSize: 14, color: "#3d6b50", lineHeight: 1.7 }}>{children}</div>
    </div>
  );
}

import PublicNav from "@/components/PublicNav";
import Link from "next/link";

const FEATURES = [
  {
    icon: "🧠",
    title: "AI Oracle",
    desc: "Ask any question in plain English and get a synthesised answer backed by citations from your real company sources — Slack threads, meeting transcripts, documents, and tasks.",
    tag: "Core",
  },
  {
    icon: "🔗",
    title: "Multi-source ingestion",
    desc: "Xylem continuously pulls from Google Drive, Google Meet transcripts, Slack channels, ClickUp tasks, and Google Calendar. Everything your team produces flows in automatically.",
    tag: "Integrations",
  },
  {
    icon: "📌",
    title: "Cited answers",
    desc: "Every answer includes numbered citations linking back to the exact source document, Slack message, or meeting timestamp. No hallucinations — only grounded, traceable responses.",
    tag: "Trust",
  },
  {
    icon: "📋",
    title: "Decision tracking",
    desc: "Xylem identifies and indexes key decisions as they're made across sources. Browse the full decision history with who made it, when, and why — fully searchable.",
    tag: "Memory",
  },
  {
    icon: "⚠️",
    title: "Drift detection",
    desc: "Automatically flags when a past decision may have been superseded or contradicted by newer discussions — so your team never acts on stale information.",
    tag: "Intelligence",
  },
  {
    icon: "🕸️",
    title: "Knowledge graph",
    desc: "Visualise how decisions, people, and topics connect across your company history. See clusters of related discussions and trace the lineage of any idea.",
    tag: "Insights",
  },
  {
    icon: "🔒",
    title: "Role-based access control",
    desc: "Per-user Google OAuth means every person only ingests and sees the files they have permission to access. Admins get full visibility; members see their scope.",
    tag: "Security",
  },
  {
    icon: "🤖",
    title: "Multi-agent research",
    desc: "Complex questions trigger a multi-agent pipeline — a router decides the strategy, then Research and Onboarding agents collaborate to produce deep, multi-hop answers.",
    tag: "Advanced",
  },
];

const INTEGRATIONS = [
  { name: "Slack",          color: "#4a154b", bg: "#f4ede4", emoji: "💬" },
  { name: "Google Drive",   color: "#1a73e8", bg: "#e8f0fe", emoji: "📁" },
  { name: "Google Meet",    color: "#00897b", bg: "#e0f2f1", emoji: "🎥" },
  { name: "ClickUp",        color: "#7b68ee", bg: "#f0eeff", emoji: "✅" },
  { name: "Google Calendar",color: "#1967d2", bg: "#e8f0fe", emoji: "📅" },
];

export default function FeaturesPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: `
          radial-gradient(ellipse 80% 50% at 50% -5%, rgba(90,78,251,.06) 0%, transparent 50%),
          radial-gradient(ellipse 50% 40% at 10% 85%, rgba(124,114,255,.04) 0%, transparent 50%),
          #fdfdff
        `,
        fontFamily: "Inter, -apple-system, sans-serif",
        color: "#0a0a0f",
      }}
    >
      {/* Nav */}
      <PublicNav />

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section
        style={{
          textAlign: "center",
          padding: "72px 24px 64px",
          maxWidth: 720,
          margin: "0 auto",
        }}
      >
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 7,
            background: "#0a0a0f",
            borderRadius: 20,
            padding: "5px 14px",
            marginBottom: 24,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "2.5px",
            textTransform: "uppercase" as const,
            color: "#818cf8",
          }}
        >
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "#818cf8",
              display: "inline-block",
            }}
          />
          Everything in Xylem
        </div>

        <h1
          style={{
            fontSize: "clamp(36px, 5vw, 58px)",
            fontWeight: 800,
            letterSpacing: -2,
            lineHeight: 1.05,
            marginBottom: 20,
            color: "#0a0a0f",
          }}
        >
          Stop losing knowledge.{" "}
          <span
            style={{
              backgroundImage: "linear-gradient(90deg, #a5b4fc, #7c72ff)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            Start building memory.
          </span>
        </h1>

        <p style={{ fontSize: 17, color: "#64748b", lineHeight: 1.75, maxWidth: 520, margin: "0 auto 36px" }}>
          Xylem is an AI-powered knowledge layer that continuously indexes everything
          your company produces and makes it instantly queryable — with full citations.
        </p>

        <Link
          href="/sign-in"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            height: 50,
            padding: "0 28px",
            background: "#5a4efb",
            color: "#fff",
            borderRadius: 10,
            fontSize: 15,
            fontWeight: 600,
            textDecoration: "none",
            boxShadow: "0 4px 16px rgba(90,78,251,.25)",
            transition: "all .2s",
          }}
        >
          Get started free →
        </Link>
      </section>

      {/* ── Feature grid ─────────────────────────────────────────────────── */}
      <section style={{ padding: "0 40px 80px", maxWidth: 1100, margin: "0 auto", width: "100%" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
            gap: 20,
          }}
        >
          {FEATURES.map((f) => (
            <div
              key={f.title}
              style={{
                background: "rgba(255,255,255,.7)",
                border: "1px solid rgba(90,78,251,.1)",
                borderRadius: 16,
                padding: "28px 28px 24px",
                backdropFilter: "blur(8px)",
                transition: "all .2s",
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
                <div
                  style={{
                    width: 44,
                    height: 44,
                    background: "linear-gradient(145deg, rgba(90,78,251,.03), rgba(90,78,251,.06))",
                    borderRadius: 12,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 22,
                    border: "1px solid rgba(90,78,251,.15)",
                  }}
                >
                  {f.icon}
                </div>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "1.5px",
                    textTransform: "uppercase" as const,
                    color: "#5a4efb",
                    background: "rgba(90,78,251,.03)",
                    border: "1px solid rgba(90,78,251,.06)",
                    borderRadius: 20,
                    padding: "3px 9px",
                  }}
                >
                  {f.tag}
                </span>
              </div>
              <h3
                style={{
                  fontSize: 16,
                  fontWeight: 700,
                  color: "#0a0a0f",
                  marginBottom: 8,
                  letterSpacing: -0.3,
                }}
              >
                {f.title}
              </h3>
              <p style={{ fontSize: 13.5, color: "#64748b", lineHeight: 1.65 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Integrations ─────────────────────────────────────────────────── */}
      <section
        style={{
          background: "rgba(240,239,255,.4)",
          borderTop: "1px solid rgba(90,78,251,.1)",
          borderBottom: "1px solid rgba(90,78,251,.1)",
          padding: "56px 40px",
          textAlign: "center",
        }}
      >
        <p
          style={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "2px",
            textTransform: "uppercase" as const,
            color: "#94a3b8",
            marginBottom: 28,
          }}
        >
          Connected sources
        </p>
        <div
          style={{
            display: "flex",
            gap: 16,
            justifyContent: "center",
            flexWrap: "wrap" as const,
          }}
        >
          {INTEGRATIONS.map((s) => (
            <div
              key={s.name}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                background: "rgba(255,255,255,.75)",
                border: "1px solid rgba(90,78,251,.1)",
                borderRadius: 12,
                padding: "10px 18px",
                fontSize: 13,
                fontWeight: 600,
                color: "#0a0a0f",
              }}
            >
              <span style={{ fontSize: 20 }}>{s.emoji}</span>
              {s.name}
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA strip ────────────────────────────────────────────────────── */}
      <section
        style={{
          padding: "80px 24px",
          textAlign: "center",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(28px, 4vw, 44px)",
            fontWeight: 800,
            letterSpacing: -1.5,
            color: "#0a0a0f",
            marginBottom: 14,
          }}
        >
          Ready to give your team a memory?
        </h2>
        <p style={{ fontSize: 16, color: "#64748b", marginBottom: 32, maxWidth: 400, margin: "0 auto 32px" }}>
          Sign in with your Google Workspace account and Xylem starts indexing immediately.
        </p>
        <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
          <Link
            href="/sign-in"
            style={{
              height: 50,
              padding: "0 28px",
              display: "inline-flex",
              alignItems: "center",
              background: "#5a4efb",
              color: "#fff",
              borderRadius: 10,
              fontSize: 15,
              fontWeight: 600,
              textDecoration: "none",
              boxShadow: "0 4px 16px rgba(90,78,251,.25)",
            }}
          >
            Sign in with Google →
          </Link>
          <Link
            href="/docs"
            style={{
              height: 50,
              padding: "0 28px",
              display: "inline-flex",
              alignItems: "center",
              background: "rgba(255,255,255,.6)",
              color: "#4a3eeb",
              border: "1px solid rgba(90,78,251,.15)",
              borderRadius: 10,
              fontSize: 15,
              fontWeight: 600,
              textDecoration: "none",
              backdropFilter: "blur(8px)",
            }}
          >
            Read the docs
          </Link>
        </div>
      </section>

      {/* Footer */}
      <div
        style={{
          textAlign: "center",
          padding: "16px 20px",
          fontSize: 11,
          color: "#cbd5e1",
          borderTop: "1px solid rgba(90,78,251,.08)",
          background: "rgba(240,239,255,.3)",
        }}
      >
        Xylem by Seedling Labs — AI knowledge intelligence for growing teams
      </div>
    </div>
  );
}

"use client";

import { SignIn } from "@clerk/nextjs";
import PublicNav from "@/components/PublicNav";

const PROOF = [
  { num: "1,204", label: "Decisions indexed" },
  { num: "5",     label: "Connected sources"  },
  { num: "<2s",   label: "Avg. response time" },
  { num: "100%",  label: "Cited answers"      },
];

export default function SignInPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: `
          radial-gradient(ellipse 90% 60% at 50% -10%, #bbf7d0 0%, transparent 55%),
          radial-gradient(ellipse 60% 50% at 15% 90%,  #d1fae5 0%, transparent 50%),
          radial-gradient(ellipse 50% 40% at 88% 75%,  #dcfce7 0%, transparent 50%),
          #f0fdf4
        `,
        fontFamily: "Inter, -apple-system, sans-serif",
      }}
    >
      {/* ── Announcement bar ───────────────────────────────────────────────── */}
      <div
        style={{
          background: "rgba(187,247,208,.5)",
          borderBottom: "1px solid rgba(134,239,172,.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: 40,
          fontSize: 12,
          color: "#166534",
          letterSpacing: "0.4px",
          backdropFilter: "blur(8px)",
          gap: 8,
        }}
      >
        <span
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: "#22c55e",
            display: "inline-block",
            boxShadow: "0 0 5px rgba(34,197,94,.6)",
            animation: "pulse 2.4s ease-in-out infinite",
          }}
        />
        Now available for{" "}
        <strong style={{ color: "#14532d", fontWeight: 600, marginLeft: 4 }}>
          Seedling Labs
        </strong>
        &nbsp;— Early access
      </div>

      {/* ── Nav ────────────────────────────────────────────────────────────── */}
      <PublicNav />

      {/* ── Main ───────────────────────────────────────────────────────────── */}
      <main
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexDirection: "column",
          padding: "48px 24px 64px",
          textAlign: "center",
        }}
      >
        {/* Eyebrow pill */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 7,
            background: "#14532d",
            borderRadius: 20,
            padding: "5px 14px",
            marginBottom: 24,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "2.5px",
            textTransform: "uppercase",
            color: "#4ade80",
          }}
        >
          <span
            style={{
              width: 5,
              height: 5,
              borderRadius: "50%",
              background: "#4ade80",
              display: "inline-block",
            }}
          />
          Company knowledge intelligence
        </div>

        {/* Headline */}
        <h1
          style={{
            fontSize: "clamp(36px, 5vw, 60px)",
            fontWeight: 800,
            letterSpacing: -2.5,
            lineHeight: 1.05,
            marginBottom: 18,
            color: "#052e16",
            maxWidth: 640,
          }}
        >
          Your company&apos;s memory,{" "}
          <span
            style={{
              backgroundImage: "linear-gradient(90deg, #86efac, #4ade80)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            perfected.
          </span>
        </h1>

        {/* Subtext */}
        <p
          style={{
            fontSize: 16,
            color: "#3d6b50",
            lineHeight: 1.75,
            maxWidth: 440,
            marginBottom: 44,
          }}
        >
          Xylem carries what your company needs — every decision, meeting, and
          discussion — delivering cited answers when you need them.
        </p>

        {/* ── Clerk sign-in card ────────────────────────────────────────────── */}
        <div style={{ width: "100%", maxWidth: 400 }}>
          <SignIn
            appearance={{
              variables: {
                colorPrimary: "#16a34a",
                colorBackground: "rgba(255,255,255,0.75)",
                colorInputBackground: "#ffffff",
                colorInputText: "#052e16",
                colorText: "#052e16",
                colorTextSecondary: "#4d7c5a",
                fontFamily: "Inter, system-ui, sans-serif",
                fontSize: "14px",
                borderRadius: "12px",
              },
              elements: {
                card: [
                  "shadow-none border p-8 w-full",
                  "backdrop-blur-sm",
                ].join(" "),
                headerTitle: "hidden",
                headerSubtitle: "hidden",
                socialButtonsBlockButton:
                  "border border-green-200 bg-white hover:bg-green-50 text-green-900 font-semibold rounded-xl h-[46px] transition-all duration-200 shadow-sm",
                socialButtonsBlockButtonText: "font-semibold text-[13px]",
                dividerLine: "bg-green-100",
                dividerText: "text-green-400 text-[11px] font-bold uppercase tracking-[0.15em]",
                formFieldLabel:
                  "text-[11px] font-bold text-green-700 uppercase tracking-wider mb-1.5",
                formFieldInput:
                  "bg-white border border-green-200 rounded-xl h-[46px] text-[14px] font-medium placeholder:text-green-300 focus:ring-2 focus:ring-green-400/20 focus:border-green-400 transition-all duration-200",
                formButtonPrimary:
                  "bg-[#16a34a] hover:bg-[#15803d] text-white font-bold rounded-xl h-[46px] text-[14px] shadow-md shadow-green-500/20 transition-all duration-200",
                footerActionLink:
                  "text-[#16a34a] font-semibold hover:text-[#15803d] transition-colors",
                footerActionText: "text-[13px] text-green-600",
                identityPreviewText: "text-[13px] font-medium text-green-800",
                identityPreviewEditButton: "text-[#16a34a] font-semibold text-[12px]",
                alertText: "text-[13px]",
                formFieldSuccessText: "text-[12px] text-green-600",
                formFieldErrorText: "text-[12px] text-red-500",
                rootBox: "w-full",
                cardBox: "w-full border border-green-200/60 rounded-2xl bg-white/75 backdrop-blur-sm",
              },
            }}
          />
        </div>

        {/* ── Proof stats ──────────────────────────────────────────────────── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 32,
            marginTop: 56,
            paddingTop: 36,
            borderTop: "1px solid rgba(134,239,172,.4)",
          }}
        >
          {PROOF.map((p, i) => (
            <>
              {i > 0 && (
                <div
                  key={`sep-${i}`}
                  style={{ width: 1, height: 40, background: "rgba(134,239,172,.5)" }}
                />
              )}
              <div key={p.label} style={{ textAlign: "center" }}>
                <div
                  style={{
                    fontSize: 28,
                    fontWeight: 800,
                    letterSpacing: -1,
                    color: "#14532d",
                  }}
                >
                  {p.num}
                </div>
                <div style={{ fontSize: 12, color: "#6bad7e", marginTop: 3 }}>
                  {p.label}
                </div>
              </div>
            </>
          ))}
        </div>
      </main>

      {/* ── Footer caption ─────────────────────────────────────────────────── */}
      <div
        style={{
          textAlign: "center",
          padding: "16px 20px",
          fontSize: 11,
          color: "#86bfa0",
          letterSpacing: "0.4px",
          borderTop: "1px solid rgba(134,239,172,.3)",
          background: "rgba(220,252,231,.3)",
        }}
      >
        Xylem — named after the vascular tissue that carries nutrients through a plant.
        Here, it carries knowledge through your company.
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}

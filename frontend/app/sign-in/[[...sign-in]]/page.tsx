"use client";

import { useState } from "react";
import { SignIn } from "@clerk/nextjs";
import PublicNav from "@/components/PublicNav";
import Link from "next/link";

const PROOF = [
  { num: "1,204", label: "Decisions indexed" },
  { num: "5",     label: "Connected sources"  },
  { num: "<2s",   label: "Avg. response time" },
  { num: "100%",  label: "Cited answers"      },
];

const GOOGLE_SVG = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

export default function SignInPage() {
  const [showAuth, setShowAuth] = useState(false);

  return (
    <div style={{
      minHeight: "100vh", display: "flex", flexDirection: "column",
      background: "#fdfdff",
      fontFamily: "Inter, -apple-system, sans-serif",
    }}>
      {/* Subtle top purple gradient wash — matches the app's feel */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0,
        background: `
          radial-gradient(ellipse 80% 50% at 50% -5%, rgba(90,78,251,.07) 0%, transparent 55%),
          radial-gradient(ellipse 40% 30% at 90% 80%, rgba(124,114,255,.04) 0%, transparent 50%)
        `,
      }} />

      {/* ── Announcement bar ─────────────────────────────────────────────── */}
      <div style={{
        position: "relative", zIndex: 10,
        background: "#f0efff",
        borderBottom: "1px solid #e8e6ff",
        display: "flex", alignItems: "center", justifyContent: "center",
        height: 40, fontSize: 12, color: "#4a3eeb", letterSpacing: "0.3px", gap: 8,
      }}>
        <span style={{
          width: 5, height: 5, borderRadius: "50%", background: "#5a4efb",
          display: "inline-block", animation: "blink 2.4s ease-in-out infinite",
        }} />
        Now available for{" "}
        <strong style={{ color: "#0a0a0f", fontWeight: 600, marginLeft: 4 }}>
          Seedling Labs
        </strong>
        &nbsp;— Early access
      </div>

      {/* ── Nav ──────────────────────────────────────────────────────────── */}
      <div style={{ position: "relative", zIndex: 10 }}>
        <PublicNav />
      </div>

      {/* ── Main ─────────────────────────────────────────────────────────── */}
      <main style={{
        position: "relative", zIndex: 10,
        flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
        flexDirection: "column", padding: "64px 24px 72px", textAlign: "center",
      }}>

        {/* Eyebrow pill */}
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 7,
          background: "#f0efff", border: "1px solid #e0deff",
          borderRadius: 20, padding: "5px 14px", marginBottom: 24,
          fontSize: 11, fontWeight: 700, letterSpacing: "2.5px",
          textTransform: "uppercase", color: "#5a4efb",
        }}>
          <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#5a4efb", display: "inline-block" }} />
          Company knowledge intelligence
        </div>

        {/* Headline */}
        <h1 style={{
          fontSize: "clamp(40px, 5.5vw, 64px)", fontWeight: 800,
          letterSpacing: -2.5, lineHeight: 1.05, marginBottom: 18,
          color: "#0a0a0f", maxWidth: 660,
        }}>
          Your company&apos;s memory,{" "}
          <span style={{
            backgroundImage: "linear-gradient(90deg, #5a4efb, #818cf8)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}>
            perfected.
          </span>
        </h1>

        {/* Subtext */}
        <p style={{
          fontSize: 16, color: "#64748b", lineHeight: 1.75,
          maxWidth: 440, marginBottom: 48,
        }}>
          Xylem carries what your company needs — every decision, meeting, and
          discussion — delivering cited answers when you need them.
        </p>

        {/* ── CTA area: landing buttons OR Clerk form ───────────────────── */}
        <div style={{ width: "100%", maxWidth: 400 }}>
          {!showAuth ? (
            /* ── State 1: landing buttons ── */
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <button
                onClick={() => setShowAuth(true)}
                style={{
                  height: 52, width: "100%",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
                  background: "#5a4efb", color: "#fff",
                  border: "none", borderRadius: 14,
                  fontSize: 16, fontWeight: 600, cursor: "pointer",
                  boxShadow: "0 4px 16px rgba(90,78,251,.3)",
                  transition: "all .2s",
                }}
                onMouseOver={e => { e.currentTarget.style.background = "#4a3eeb"; e.currentTarget.style.transform = "translateY(-1px)"; }}
                onMouseOut={e => { e.currentTarget.style.background = "#5a4efb"; e.currentTarget.style.transform = "translateY(0)"; }}
              >
                {GOOGLE_SVG}
                Sign in with Google
              </button>
              <Link href="/features" style={{
                height: 52, width: "100%",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                background: "#fff", color: "#0a0a0f",
                border: "1px solid #e2e8f0", borderRadius: 14,
                fontSize: 16, fontWeight: 600, textDecoration: "none",
                boxShadow: "0 1px 4px rgba(0,0,0,.04)",
                transition: "all .2s",
              }}>
                See how it works →
              </Link>
            </div>
          ) : (
            /* ── State 2: Clerk form ── */
            <div style={{ animation: "fadeUp .25s ease forwards" }}>
              <SignIn
                appearance={{
                  variables: {
                    colorPrimary: "#5a4efb",
                    colorBackground: "#ffffff",
                    colorInputBackground: "#ffffff",
                    colorInputText: "#0a0a0f",
                    colorText: "#0a0a0f",
                    colorTextSecondary: "#64748b",
                    fontFamily: "Inter, system-ui, sans-serif",
                    fontSize: "14px",
                    borderRadius: "12px",
                  },
                  elements: {
                    card: "shadow-none p-0 bg-transparent w-full",
                    headerTitle: "hidden",
                    headerSubtitle: "hidden",
                    socialButtonsBlockButton:
                      "border border-gray-200 bg-white hover:bg-gray-50 text-gray-800 font-semibold rounded-xl h-[48px] transition-all duration-200 shadow-sm",
                    socialButtonsBlockButtonText: "font-semibold text-[14px]",
                    dividerLine: "bg-gray-100",
                    dividerText: "text-gray-400 text-[11px] font-bold uppercase tracking-[0.15em]",
                    formFieldLabel:
                      "text-[11px] font-bold text-gray-500 uppercase tracking-wider mb-1.5",
                    formFieldInput:
                      "bg-white border border-gray-200 rounded-xl h-[48px] text-[14px] font-medium text-gray-900 placeholder:text-gray-300 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 transition-all duration-200",
                    formButtonPrimary:
                      "bg-[#5a4efb] hover:bg-[#4a3eeb] text-white font-bold rounded-xl h-[48px] text-[15px] shadow-md shadow-indigo-500/20 transition-all duration-200",
                    footerActionLink:
                      "text-[#5a4efb] font-semibold hover:text-[#4a3eeb] transition-colors",
                    footerActionText: "text-[13px] text-gray-500",
                    identityPreviewText: "text-[13px] font-medium text-gray-700",
                    identityPreviewEditButton: "text-[#5a4efb] font-semibold text-[12px]",
                    alertText: "text-[13px]",
                    formFieldSuccessText: "text-[12px] text-green-600",
                    formFieldErrorText: "text-[12px] text-red-500",
                    rootBox: "w-full",
                    cardBox: "w-full border border-gray-200 rounded-2xl bg-white shadow-lg shadow-gray-100",
                  },
                }}
              />
              <button
                onClick={() => setShowAuth(false)}
                style={{
                  marginTop: 14, background: "none", border: "none",
                  color: "#94a3b8", fontSize: 13, cursor: "pointer",
                  textDecoration: "underline", textUnderlineOffset: 3,
                }}
              >
                ← Back
              </button>
            </div>
          )}
        </div>

        {/* ── Proof stats ──────────────────────────────────────────────────── */}
        <div style={{
          display: "flex", alignItems: "center", gap: 32,
          marginTop: 64, paddingTop: 36,
          borderTop: "1px solid #f1f5f9",
        }}>
          {PROOF.map((p, i) => (
            <div key={p.label} style={{ display: "flex", alignItems: "center", gap: 32 }}>
              {i > 0 && <div style={{ width: 1, height: 40, background: "#e2e8f0" }} />}
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: -1, color: "#0a0a0f" }}>
                  {p.num}
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 3 }}>
                  {p.label}
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* ── Footer caption ───────────────────────────────────────────────── */}
      <div style={{
        position: "relative", zIndex: 10,
        textAlign: "center", padding: "16px 20px", fontSize: 11,
        color: "#cbd5e1", letterSpacing: "0.3px",
        borderTop: "1px solid #f1f5f9",
      }}>
        Xylem — named after the vascular tissue that carries nutrients through a plant.
        Here, it carries knowledge through your company.
      </div>

      <style>{`
        @keyframes blink { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
        @keyframes fadeUp { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
      `}</style>
    </div>
  );
}

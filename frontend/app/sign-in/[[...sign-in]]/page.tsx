"use client";

import { useState } from "react";
import { SignIn } from "@clerk/nextjs";
import PublicNav from "@/components/PublicNav";
import Link from "next/link";

const PROOF = [
  { num: "5",     label: "Connected sources"  },
  { num: "200+",  label: "Cross-source links" },
  { num: "<8s",   label: "Avg. response time" },
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
      background: `
        radial-gradient(ellipse 90% 60% at 50% -10%, #bbf7d0 0%, transparent 55%),
        radial-gradient(ellipse 60% 50% at 15% 90%,  #d1fae5 0%, transparent 50%),
        radial-gradient(ellipse 50% 40% at 88% 75%,  #dcfce7 0%, transparent 50%),
        #f0fdf4
      `,
      fontFamily: "Inter, -apple-system, sans-serif",
    }}>
      {/* Announcement bar */}
      <div style={{
        background: "rgba(187,247,208,.5)", borderBottom: "1px solid rgba(134,239,172,.5)",
        display: "flex", alignItems: "center", justifyContent: "center",
        height: 40, fontSize: 12, color: "#166534", letterSpacing: "0.4px",
        backdropFilter: "blur(8px)", gap: 8,
      }}>
        <span style={{
          width: 5, height: 5, borderRadius: "50%", background: "#22c55e",
          display: "inline-block", boxShadow: "0 0 5px rgba(34,197,94,.6)",
          animation: "blink 2.4s ease-in-out infinite",
        }} />
        Now available for{" "}
        <strong style={{ color: "#14532d", fontWeight: 600, marginLeft: 4 }}>Seedling Labs</strong>
        &nbsp;— Early access
      </div>

      <PublicNav />

      <main style={{
        flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
        flexDirection: "column", padding: "32px 24px 64px", textAlign: "center",
      }}>
        {/* Mascot */}
        <img
          src="/xylem-mascot.png"
          alt="Xylem mascot"
          style={{
            width: 140, height: 140, objectFit: "contain",
            marginBottom: 8,
          }}
        />

        {/* Eyebrow */}
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 7,
          background: "#14532d", borderRadius: 20, padding: "5px 14px", marginBottom: 24,
          fontSize: 11, fontWeight: 700, letterSpacing: "2.5px",
          textTransform: "uppercase", color: "#4ade80",
        }}>
          <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#4ade80", display: "inline-block" }} />
          Company knowledge intelligence
        </div>

        {/* Headline */}
        <h1 style={{
          fontSize: "clamp(40px, 5.5vw, 64px)", fontWeight: 800,
          letterSpacing: -2.5, lineHeight: 1.05, marginBottom: 18,
          color: "#052e16", maxWidth: 660,
        }}>
          Your company&apos;s memory,{" "}
          <span style={{
            backgroundImage: "linear-gradient(90deg, #86efac, #4ade80)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
          }}>
            perfected.
          </span>
        </h1>

        <p style={{ fontSize: 16, color: "#3d6b50", lineHeight: 1.75, maxWidth: 440, marginBottom: 48 }}>
          Xylem carries what your company needs — every decision, meeting, and
          discussion — delivering cited answers when you need them.
        </p>

        {/* CTA area */}
        <div style={{ width: "100%", maxWidth: 400 }}>
          {!showAuth ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <button
                onClick={() => setShowAuth(true)}
                style={{
                  height: 52, width: "100%",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
                  background: "#16a34a", color: "#fff", border: "none", borderRadius: 14,
                  fontSize: 16, fontWeight: 600, cursor: "pointer",
                  boxShadow: "0 4px 16px rgba(22,163,74,.3)", transition: "all .2s",
                }}
                onMouseOver={e => { e.currentTarget.style.background = "#15803d"; e.currentTarget.style.transform = "translateY(-1px)"; }}
                onMouseOut={e => { e.currentTarget.style.background = "#16a34a"; e.currentTarget.style.transform = "translateY(0)"; }}
              >
                {GOOGLE_SVG} Sign in with Google
              </button>
              <Link href="/features" style={{
                height: 52, width: "100%",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                background: "rgba(255,255,255,.6)", color: "#166534",
                border: "1px solid rgba(134,239,172,.7)", borderRadius: 14,
                fontSize: 16, fontWeight: 600, textDecoration: "none",
                backdropFilter: "blur(8px)", transition: "all .2s",
              }}>
                See how it works →
              </Link>
            </div>
          ) : (
            <div style={{ animation: "fadeUp .25s ease forwards" }}>
              <SignIn
                appearance={{
                  variables: {
                    colorPrimary: "#16a34a",
                    colorBackground: "rgba(255,255,255,0.9)",
                    colorInputBackground: "#ffffff",
                    colorInputText: "#052e16",
                    colorText: "#052e16",
                    colorTextSecondary: "#4d7c5a",
                    fontFamily: "Inter, system-ui, sans-serif",
                    fontSize: "14px",
                    borderRadius: "12px",
                  },
                  elements: {
                    card: "shadow-none p-0 bg-transparent w-full",
                    headerTitle: "hidden",
                    headerSubtitle: "hidden",
                    socialButtonsBlockButton:
                      "border border-green-200 bg-white hover:bg-green-50 text-green-900 font-semibold rounded-xl h-[48px] transition-all duration-200 shadow-sm",
                    socialButtonsBlockButtonText: "font-semibold text-[14px]",
                    dividerLine: "bg-green-100",
                    dividerText: "text-green-400 text-[11px] font-bold uppercase tracking-[0.15em]",
                    formFieldLabel: "text-[11px] font-bold text-green-700 uppercase tracking-wider mb-1.5",
                    formFieldInput:
                      "bg-white border border-green-200 rounded-xl h-[48px] text-[14px] font-medium placeholder:text-green-300 focus:ring-2 focus:ring-green-400/20 focus:border-green-400 transition-all duration-200",
                    formButtonPrimary:
                      "bg-[#16a34a] hover:bg-[#15803d] text-white font-bold rounded-xl h-[48px] text-[15px] shadow-md shadow-green-500/20 transition-all duration-200",
                    footerActionLink: "text-[#16a34a] font-semibold hover:text-[#15803d] transition-colors",
                    footerActionText: "text-[13px] text-green-600",
                    identityPreviewText: "text-[13px] font-medium text-green-800",
                    identityPreviewEditButton: "text-[#16a34a] font-semibold text-[12px]",
                    alertText: "text-[13px]",
                    formFieldSuccessText: "text-[12px] text-green-600",
                    formFieldErrorText: "text-[12px] text-red-500",
                    rootBox: "w-full",
                    cardBox: "w-full border border-green-200/60 rounded-2xl bg-white/80 backdrop-blur-sm shadow-lg shadow-green-900/5",
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

        {/* Proof stats */}
        <div style={{
          display: "flex", alignItems: "center", gap: 32,
          marginTop: 64, paddingTop: 36,
          borderTop: "1px solid rgba(134,239,172,.4)",
        }}>
          {PROOF.map((p, i) => (
            <div key={p.label} style={{ display: "flex", alignItems: "center", gap: 32 }}>
              {i > 0 && <div style={{ width: 1, height: 40, background: "rgba(134,239,172,.5)" }} />}
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: -1, color: "#14532d" }}>{p.num}</div>
                <div style={{ fontSize: 12, color: "#6bad7e", marginTop: 3 }}>{p.label}</div>
              </div>
            </div>
          ))}
        </div>
      </main>

      <div style={{
        textAlign: "center", padding: "16px 20px", fontSize: 11,
        color: "#86bfa0", letterSpacing: "0.4px",
        borderTop: "1px solid rgba(134,239,172,.3)",
        background: "rgba(220,252,231,.3)",
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

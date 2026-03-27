"use client";

import { SignIn } from "@clerk/nextjs";

// ─────────────────────────────────────────────────────────────────────────────
// XylemSynapse
// Shows every connected source feeding into the central Xylem node,
// like xylem tissue or a neural synapse drawing everything inward.
// ─────────────────────────────────────────────────────────────────────────────

const CX = 300;
const CY = 480;

const SOURCES = [
  { name: "Slack",    x: 82,  y: 175, color: "#34d399", cp1x: 82,  cp1y: 330, cp2x: 195, cp2y: 450, dur: "3.2s", begin: "0s"    },
  { name: "Drive",    x: 518, y: 155, color: "#22d3ee", cp1x: 518, cp1y: 310, cp2x: 405, cp2y: 450, dur: "2.8s", begin: "0.6s"  },
  { name: "Meet",     x: 562, y: 430, color: "#4ade80", cp1x: 455, cp1y: 430, cp2x: 388, cp2y: 470, dur: "3.5s", begin: "1.1s"  },
  { name: "Calendar", x: 472, y: 755, color: "#06b6d4", cp1x: 472, cp1y: 605, cp2x: 388, cp2y: 525, dur: "2.6s", begin: "0.3s"  },
  { name: "ClickUp",  x: 128, y: 755, color: "#6ee7b7", cp1x: 128, cp1y: 605, cp2x: 212, cp2y: 525, dur: "3.0s", begin: "1.5s"  },
  { name: "Uploads",  x: 38,  y: 435, color: "#38bdf8", cp1x: 148, cp1y: 435, cp2x: 215, cp2y: 468, dur: "2.4s", begin: "0.8s"  },
];

function XylemSynapse() {
  return (
    <svg
      viewBox="0 0 600 930"
      fill="none"
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 w-full h-full"
      aria-hidden
    >
      <defs>
        {/* Per-source path gradients, source colour → cyan at centre */}
        {SOURCES.map((s, i) => (
          <linearGradient
            key={i} id={`sg${i}`}
            x1={s.x} y1={s.y} x2={CX} y2={CY}
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0%"   stopColor={s.color} stopOpacity="0.0" />
            <stop offset="30%"  stopColor={s.color} stopOpacity="0.5" />
            <stop offset="100%" stopColor="#22d3ee"  stopOpacity="0.8" />
          </linearGradient>
        ))}

        {/* Per-source node glow */}
        {SOURCES.map((s, i) => (
          <radialGradient key={i} id={`ng${i}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor={s.color} stopOpacity="0.25" />
            <stop offset="100%" stopColor={s.color} stopOpacity="0"    />
          </radialGradient>
        ))}

        {/* Central glow */}
        <radialGradient id="cg" cx="50%" cy="50%" r="50%">
          <stop offset="0%"   stopColor="#22d3ee" stopOpacity="0.35" />
          <stop offset="50%"  stopColor="#059669" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#0891b2" stopOpacity="0"    />
        </radialGradient>

        {/* Radial fade mask — diagram dissolves at the edges */}
        <radialGradient id="fadeGrad" cx="50%" cy="53%" r="48%">
          <stop offset="35%" stopColor="white" stopOpacity="1" />
          <stop offset="100%" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <mask id="fade">
          <rect width="600" height="930" fill="url(#fadeGrad)" />
        </mask>
      </defs>

      <g mask="url(#fade)">
        {/* ── Paths (tubes) ───────────────────────────────────────────── */}
        {SOURCES.map((s, i) => (
          <path
            key={i}
            d={`M ${s.x} ${s.y} C ${s.cp1x} ${s.cp1y} ${s.cp2x} ${s.cp2y} ${CX} ${CY}`}
            stroke={`url(#sg${i})`}
            strokeWidth="1.4"
            fill="none"
          />
        ))}

        {/* ── Travelling dots along each path ─────────────────────────── */}
        {SOURCES.map((s, i) => (
          <circle key={i} r="2.8" fill={s.color} opacity="0.9">
            <animateMotion
              dur={s.dur}
              begin={s.begin}
              repeatCount="indefinite"
              path={`M ${s.x} ${s.y} C ${s.cp1x} ${s.cp1y} ${s.cp2x} ${s.cp2y} ${CX} ${CY}`}
            />
          </circle>
        ))}

        {/* ── Source node glows + dots ─────────────────────────────────── */}
        {SOURCES.map((s, i) => (
          <g key={i}>
            <circle cx={s.x} cy={s.y} r="24" fill={`url(#ng${i})`} />
            <circle cx={s.x} cy={s.y} r="4"  fill={s.color} opacity="0.55" />
            <circle cx={s.x} cy={s.y} r="2"  fill={s.color} opacity="0.9"  />
            {/* Label — positioned away from centre */}
            <text
              x={s.x + (s.x < CX ? 14 : -14)}
              y={s.y + 4}
              fill={s.color}
              opacity="0.45"
              fontSize="7.5"
              fontFamily="Inter, sans-serif"
              fontWeight="700"
              letterSpacing="0.1em"
              textAnchor={s.x < CX ? "start" : "end"}
            >
              {s.name.toUpperCase()}
            </text>
          </g>
        ))}

        {/* ── Central Xylem node ───────────────────────────────────────── */}
        <ellipse cx={CX} cy={CY} rx="115" ry="115" fill="url(#cg)" />
        <circle cx={CX} cy={CY} r="38" stroke="rgba(34,211,238,0.10)" strokeWidth="1" fill="none" />
        <circle cx={CX} cy={CY} r="26" stroke="rgba(34,211,238,0.20)" strokeWidth="1"
          fill="rgba(34,211,238,0.04)" />
        <circle cx={CX} cy={CY} r="14" fill="rgba(34,211,238,0.15)" />
        <circle cx={CX} cy={CY} r="6.5" fill="rgba(34,211,238,0.85)" />
        <circle cx={CX} cy={CY} r="3"   fill="white" opacity="0.95" />

        {/* Subtle pulse ring animation */}
        <circle cx={CX} cy={CY} r="26" stroke="rgba(34,211,238,0.35)" strokeWidth="1" fill="none">
          <animate attributeName="r" values="26;42;26" dur="3s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.35;0;0.35" dur="3s" repeatCount="indefinite" />
        </circle>
      </g>
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────

export default function SignInPage() {
  return (
    <div className="min-h-screen w-full flex" style={{ background: "#040e18" }}>

      {/* ── Left panel ──────────────────────────────────────────────────── */}
      <div
        className="hidden lg:flex lg:w-[55%] relative flex-col justify-between p-14 overflow-hidden"
        style={{
          background: "linear-gradient(145deg, #030d18 0%, #04141f 40%, #051a14 100%)",
        }}
      >
        {/* Synapse diagram fills the panel */}
        <XylemSynapse />

        {/* Top accent line */}
        <div className="absolute top-0 left-0 right-0 h-[1px]"
          style={{ background: "linear-gradient(90deg, transparent, rgba(34,211,238,0.2), transparent)" }} />

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-[10px] flex items-center justify-center shadow-lg"
            style={{
              background: "linear-gradient(135deg, #0891b2, #059669)",
              boxShadow: "0 4px 14px rgba(8,145,178,0.3)",
            }}
          >
            {/* Mini xylem cross-section mark */}
            <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
              {[0, 60, 120, 180, 240, 300].map((deg) => {
                const r = (deg * Math.PI) / 180;
                return (
                  <line key={deg}
                    x1="10" y1="10"
                    x2={10 + Math.cos(r) * 7} y2={10 + Math.sin(r) * 7}
                    stroke="white" strokeWidth="1.4" strokeLinecap="round" opacity="0.85"
                  />
                );
              })}
              <circle cx="10" cy="10" r="2.5" fill="white" />
            </svg>
          </div>
          <span className="text-[22px] font-bold tracking-tight text-white">Xylem</span>
        </div>

        {/* Footer — one line + live dot */}
        <div className="relative z-10 flex items-end justify-between">
          <p
            className="text-[15px] font-semibold leading-snug"
            style={{ color: "rgba(255,255,255,0.55)" }}
          >
            Every source.<br />
            <span
              className="text-transparent bg-clip-text font-black"
              style={{ backgroundImage: "linear-gradient(90deg, #22d3ee, #34d399)" }}
            >
              One memory.
            </span>
          </p>
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <p className="text-[10px] font-medium" style={{ color: "rgba(255,255,255,0.2)" }}>Live</p>
          </div>
        </div>
      </div>

      {/* ── Right panel ─────────────────────────────────────────────────── */}
      <div
        className="flex-1 flex flex-col items-center justify-center relative overflow-hidden"
        style={{ background: "#f4f8fb" }}
      >
        {/* Mobile logo */}
        <div className="lg:hidden flex items-center gap-3 mb-12">
          <div className="w-9 h-9 bg-accent rounded-[10px] flex items-center justify-center text-lg shadow-lg shadow-accent/20">
            🌱
          </div>
          <span className="text-xl font-bold tracking-tight text-foreground">Xylem</span>
        </div>

        <div className="w-full max-w-[360px] px-2">
          <div className="mb-8">
            <h2 className="text-[26px] font-black text-foreground tracking-tight leading-tight mb-2">
              Welcome back
            </h2>
            <p className="text-[13px] text-gray-400 font-medium leading-relaxed">
              Sign in to your organisation's knowledge base.
            </p>
          </div>

          <SignIn
            appearance={{
              variables: {
                colorPrimary: "#0891b2",
                colorBackground: "#f4f8fb",
                colorInputBackground: "#ffffff",
                colorInputText: "#0a0a0f",
                colorText: "#0a0a0f",
                colorTextSecondary: "#94a3b8",
                fontFamily: "Inter, system-ui, sans-serif",
                fontSize: "14px",
                borderRadius: "12px",
              },
              elements: {
                card: "shadow-none border-0 p-0 bg-transparent w-full",
                headerTitle: "hidden",
                headerSubtitle: "hidden",
                socialButtonsBlockButton:
                  "border border-gray-200 bg-white hover:bg-gray-50 text-foreground font-semibold rounded-xl h-[46px] transition-all duration-200 shadow-sm",
                socialButtonsBlockButtonText: "font-semibold text-[13px] text-gray-700",
                dividerLine: "bg-gray-200",
                dividerText: "text-gray-300 text-[11px] font-bold uppercase tracking-[0.15em]",
                formFieldLabel: "text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5",
                formFieldInput:
                  "bg-white border border-gray-200 rounded-xl h-[46px] text-[14px] font-medium text-foreground placeholder:text-gray-300 focus:ring-2 focus:ring-cyan-500/20 focus:border-cyan-400/60 transition-all duration-200",
                formButtonPrimary:
                  "bg-[#0891b2] hover:bg-[#0e7490] text-white font-bold rounded-xl h-[46px] text-[14px] shadow-md shadow-cyan-500/20 transition-all duration-200",
                footerActionLink: "text-[#0891b2] font-semibold hover:text-[#0e7490] transition-colors",
                footerActionText: "text-[13px] text-gray-400",
                identityPreviewText: "text-[13px] font-medium",
                identityPreviewEditButton: "text-[#0891b2] font-semibold text-[12px]",
                alertText: "text-[13px]",
                formFieldSuccessText: "text-[12px] text-green-600",
                formFieldErrorText: "text-[12px] text-red-500",
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}

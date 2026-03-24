"use client";

import { SignIn } from "@clerk/nextjs";

const features = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 3v18M3 12h18" strokeLinecap="round" />
        <path d="M12 3C8 6 5 9 5 13c0 3.5 3 6 7 7" strokeLinecap="round" />
        <path d="M12 3c4 3 7 6 7 10c0 3.5-3 6-7 7" strokeLinecap="round" />
      </svg>
    ),
    title: "Cross-source synthesis",
    desc: "Connects Slack, Drive, Meet, and Calendar into one unified memory.",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="1.5">
        <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
      </svg>
    ),
    title: "Decision intelligence",
    desc: "Auto-extracts and tracks every key decision with full rationale and history.",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 2L2 7l10 5 10-5-10-5z" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M2 17l10 5 10-5M2 12l10 5 10-5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    title: "Role-aware access",
    desc: "Every document respects permissions — public, team, or private.",
  },
];

// Subtle vascular/botanical SVG background
function BotanicalPattern() {
  return (
    <svg
      className="absolute inset-0 w-full h-full opacity-[0.06]"
      viewBox="0 0 600 800"
      fill="none"
      preserveAspectRatio="xMidYMid slice"
    >
      {/* Main stem */}
      <path d="M300 800 C300 600 300 400 300 100" stroke="white" strokeWidth="1.5" />
      {/* Left branches */}
      <path d="M300 650 C260 620 200 610 140 620" stroke="white" strokeWidth="1.2" />
      <path d="M300 530 C250 490 180 475 100 480" stroke="white" strokeWidth="1" />
      <path d="M300 420 C265 385 220 370 160 365" stroke="white" strokeWidth="1" />
      <path d="M300 310 C255 270 195 255 130 248" stroke="white" strokeWidth="0.8" />
      <path d="M300 210 C268 175 230 158 185 152" stroke="white" strokeWidth="0.8" />
      {/* Right branches */}
      <path d="M300 650 C340 620 400 610 460 620" stroke="white" strokeWidth="1.2" />
      <path d="M300 530 C350 490 420 475 500 480" stroke="white" strokeWidth="1" />
      <path d="M300 420 C335 385 380 370 440 365" stroke="white" strokeWidth="1" />
      <path d="M300 310 C345 270 405 255 470 248" stroke="white" strokeWidth="0.8" />
      <path d="M300 210 C332 175 370 158 415 152" stroke="white" strokeWidth="0.8" />
      {/* Sub-branches left */}
      <path d="M200 613 C175 590 155 568 145 540" stroke="white" strokeWidth="0.7" />
      <path d="M165 470 C148 445 138 418 140 388" stroke="white" strokeWidth="0.6" />
      {/* Sub-branches right */}
      <path d="M400 613 C425 590 445 568 455 540" stroke="white" strokeWidth="0.7" />
      <path d="M435 470 C452 445 462 418 460 388" stroke="white" strokeWidth="0.6" />
      {/* Leaf nodes */}
      <circle cx="140" cy="620" r="3" fill="white" />
      <circle cx="100" cy="480" r="3" fill="white" />
      <circle cx="160" cy="365" r="3" fill="white" />
      <circle cx="130" cy="248" r="3" fill="white" />
      <circle cx="185" cy="152" r="3" fill="white" />
      <circle cx="460" cy="620" r="3" fill="white" />
      <circle cx="500" cy="480" r="3" fill="white" />
      <circle cx="440" cy="365" r="3" fill="white" />
      <circle cx="470" cy="248" r="3" fill="white" />
      <circle cx="415" cy="152" r="3" fill="white" />
      <circle cx="300" cy="100" r="4" fill="white" />
    </svg>
  );
}

export default function SignInPage() {
  return (
    <div className="min-h-screen w-full flex">
      {/* ── Left panel: brand story ── */}
      <div className="hidden lg:flex lg:w-[58%] relative bg-[#0a0a0f] flex-col justify-between p-14 overflow-hidden">
        <BotanicalPattern />

        {/* Top: logo + name */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-10 h-10 bg-accent rounded-xl flex items-center justify-center text-xl shadow-lg shadow-accent/20">
            🌱
          </div>
          <span className="text-2xl font-bold tracking-tight text-white">Xylem</span>
        </div>

        {/* Center: headline */}
        <div className="relative z-10 space-y-8">
          <div>
            <p className="text-[11px] font-black text-accent/70 uppercase tracking-[0.25em] mb-5">
              Institutional Memory · Knowledge Synthesis
            </p>
            <h1 className="text-5xl font-black text-white leading-[1.1] tracking-tight mb-6">
              The vascular system<br />
              for your company's<br />
              <span className="text-accent">knowledge.</span>
            </h1>
            <p className="text-[16px] text-white/50 font-medium leading-relaxed max-w-md">
              In biology, xylem is the vascular tissue that silently transports nutrients
              throughout a plant — keeping every cell alive and connected.
              <br /><br />
              Xylem does the same for your organisation. Every Slack thread, Drive doc,
              meeting transcript, and decision flows into one living knowledge base —
              searchable, cited, and always in context.
            </p>
          </div>

          {/* Feature list */}
          <div className="space-y-4 pt-2">
            {features.map((f) => (
              <div key={f.title} className="flex items-start gap-4">
                <div className="w-8 h-8 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white/60 shrink-0 mt-0.5">
                  {f.icon}
                </div>
                <div>
                  <p className="text-[13px] font-bold text-white/90">{f.title}</p>
                  <p className="text-[12px] text-white/40 mt-0.5 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom: tagline */}
        <div className="relative z-10">
          <p className="text-[11px] text-white/25 font-medium tracking-wider">
            Built for Seedling Labs · Internal use only
          </p>
        </div>
      </div>

      {/* ── Right panel: auth ── */}
      <div className="flex-1 flex flex-col items-center justify-center bg-[#fdfdff] px-8 py-12">
        {/* Mobile logo (hidden on desktop) */}
        <div className="lg:hidden flex items-center gap-3 mb-10">
          <div className="w-10 h-10 bg-accent rounded-xl flex items-center justify-center text-xl shadow-lg shadow-accent/20">
            🌱
          </div>
          <span className="text-2xl font-bold tracking-tight text-foreground">Xylem</span>
        </div>

        <div className="w-full max-w-sm">
          <div className="mb-8">
            <h2 className="text-2xl font-black text-foreground tracking-tight mb-1.5">
              Welcome back
            </h2>
            <p className="text-sm text-gray-400 font-medium">
              Sign in to access your organisation's knowledge base.
            </p>
          </div>

          <SignIn
            appearance={{
              variables: {
                colorPrimary: "#5a4efb",
                colorBackground: "#ffffff",
                colorInputBackground: "#f8f9fc",
                colorInputText: "#0a0a0f",
                colorText: "#0a0a0f",
                colorTextSecondary: "#64748b",
                fontFamily: "Inter, system-ui, sans-serif",
                fontSize: "14px",
                borderRadius: "12px",
              },
              elements: {
                card: "shadow-none border-0 p-0 bg-transparent",
                headerTitle: "hidden",
                headerSubtitle: "hidden",
                socialButtonsBlockButton:
                  "border border-gray-100 bg-white hover:bg-gray-50 text-foreground font-semibold rounded-xl h-11 transition-all",
                socialButtonsBlockButtonText: "font-semibold text-[13px]",
                dividerLine: "bg-gray-100",
                dividerText: "text-gray-400 text-[11px] font-bold uppercase tracking-widest",
                formFieldLabel: "text-[12px] font-bold text-gray-500 uppercase tracking-wider mb-1",
                formFieldInput:
                  "bg-[#f8f9fc] border border-gray-100 rounded-xl h-11 text-[14px] font-medium focus:ring-2 focus:ring-accent/20 focus:border-accent/50 transition-all",
                formButtonPrimary:
                  "bg-accent hover:bg-accent-dark text-white font-bold rounded-xl h-11 text-[14px] shadow-md shadow-accent/20 transition-all",
                footerActionLink: "text-accent font-bold hover:text-accent-dark",
                identityPreviewText: "text-[13px] font-medium text-foreground",
                identityPreviewEditButton: "text-accent font-bold text-[12px]",
                alertText: "text-[13px]",
                formFieldSuccessText: "text-[12px]",
              },
            }}
          />
        </div>
      </div>
    </div>
  );
}

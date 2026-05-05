"use client";

// Xylem sidebar — unified line icons, single accent color.
// Stripe / Vercel dashboard aesthetic.

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser, useClerk, useAuth } from "@clerk/nextjs";

const Icon = ({ d, className = "" }: { d: string; className?: string }) => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.75"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden
  >
    <path d={d} />
  </svg>
);

// Lucide-style line icons. Single stroke, 24x24 viewBox.
const ICON_QUERY = "M21 21l-4.3-4.3M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16Z"; // search
const ICON_GRAPH = "M5 12a7 7 0 1 0 14 0 7 7 0 0 0-14 0Zm0 0h14M12 5a14 14 0 0 1 0 14M12 5a14 14 0 0 0 0 14"; // globe-ish
const ICON_DECISIONS = "M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v0a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2v0ZM9 12h6M9 16h4"; // clipboard with lines
const ICON_INGEST = "M13 2L3 14h9l-1 8 10-12h-9l1-8Z"; // bolt
const ICON_ACTIVITY = "M12 8v4l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"; // clock
const ICON_NEWJOINER = "M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M19 8v6M22 11h-6M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z"; // user-plus

interface SidebarItem {
  id: string;
  name: string;
  href: string;
  icon: string;
}

const navItems: SidebarItem[] = [
  { id: "query", name: "Current query", href: "/", icon: ICON_QUERY },
  { id: "graph", name: "Knowledge graph", href: "/graph", icon: ICON_GRAPH },
  { id: "decisions", name: "Decision log", href: "/decisions", icon: ICON_DECISIONS },
  { id: "ingest", name: "Ingest sources", href: "/ingest", icon: ICON_INGEST },
  { id: "activity", name: "Activity log", href: "/activity", icon: ICON_ACTIVITY },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useUser();
  const { signOut } = useClerk();
  const { getToken } = useAuth();
  const [recentQueries, setRecentQueries] = useState<{ text: string, time: string }[]>([]);
  const [selfRole, setSelfRole] = useState("member");
  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    const loadQueries = () => {
      const saved = localStorage.getItem("xylem_recent_queries");
      if (saved) {
        try { setRecentQueries(JSON.parse(saved)); } catch {}
      }
    };
    loadQueries();
    window.addEventListener("storage", loadQueries);
    return () => window.removeEventListener("storage", loadQueries);
  }, []);

  useEffect(() => {
    const fetchSelfRole = async () => {
      const currentUserEmail = user?.emailAddresses?.[0]?.emailAddress;
      if (!currentUserEmail) return;
      try {
        const token = await getToken();
        const headers = new Headers();
        if (token) headers.set("Authorization", `Bearer ${token}`);
        const res = await fetch(`${API_URL}/api/users/${encodeURIComponent(currentUserEmail)}`, { headers });
        if (!res.ok) return;
        const data = await res.json();
        if (data?.role) setSelfRole(data.role);
      } catch {}
    };
    fetchSelfRole();
  }, [API_URL, getToken, user]);

  const visibleNavItems = navItems.filter((item) => item.id !== "ingest" || selfRole !== "member");
  const openQuickOnboarding = () => {
    sessionStorage.setItem("xylem_open_quick_onboarding", "1");
    if (pathname !== "/") { window.location.href = "/"; return; }
    window.dispatchEvent(new Event("xylem_quick_onboarding"));
  };

  const handleQueryClick = (item: any) => {
    window.dispatchEvent(new CustomEvent("xylem_query", { detail: item }));
  };

  return (
    <aside className="w-[260px] border-r border-gray-100 flex flex-col pt-6 pb-5 shrink-0 h-screen z-50 bg-white">
      {/* Brand */}
      <div className="px-5 mb-9 flex items-center gap-2.5">
        <img
          src="/xylem-mascot.png"
          alt=""
          className="w-12 h-12 object-contain shrink-0"
        />
        <span className="text-[20px] font-bold tracking-tight text-foreground">Xylem</span>
      </div>

      {/* Primary Action */}
      <div className="px-4 mb-8">
        <button
          onClick={() => window.dispatchEvent(new Event("xylem_new_query"))}
          className="w-full bg-accent hover:bg-accent/90 text-white py-2.5 rounded-lg font-semibold text-[13px] flex items-center justify-center gap-1.5 transition-colors"
        >
          <span className="text-base leading-none font-light">+</span> New query
        </button>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-2 space-y-7">
        <section>
          <p className="px-3 text-[10px] font-semibold text-gray-400 uppercase tracking-[0.12em] mb-2">Navigate</p>
          <nav className="space-y-0.5">
            {visibleNavItems.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.id}
                  href={item.href}
                  className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-colors ${
                    active
                      ? "bg-accent/8 text-accent font-semibold"
                      : "text-gray-500 hover:bg-gray-50 hover:text-foreground"
                  }`}
                >
                  <Icon d={item.icon} className={active ? "text-accent" : "text-gray-400"} />
                  {item.name}
                </Link>
              );
            })}
          </nav>
        </section>

        <section>
          <p className="px-3 text-[10px] font-semibold text-gray-400 uppercase tracking-[0.12em] mb-2">Quick start</p>
          <button
            onClick={openQuickOnboarding}
            className="w-full text-left flex items-center justify-between px-3 py-2 rounded-md text-[13px] font-medium text-gray-500 hover:bg-gray-50 hover:text-foreground transition-colors group"
          >
            <span className="flex items-center gap-2.5">
              <Icon d={ICON_NEWJOINER} className="text-gray-400 group-hover:text-accent" />
              New joiner
            </span>
            <span className="text-[10px] text-accent/60 group-hover:text-accent">→</span>
          </button>
        </section>

        <section>
          <p className="px-3 text-[10px] font-semibold text-gray-400 uppercase tracking-[0.12em] mb-2">Recent</p>
          <div className="space-y-0.5">
            {recentQueries.length === 0 ? (
              <p className="px-3 py-3 text-[11px] text-gray-400 leading-relaxed">
                Your recent queries will appear here.
              </p>
            ) : (
              recentQueries.map((item, i) => (
                <button
                  key={i}
                  onClick={() => handleQueryClick(item)}
                  className="w-full text-left px-3 py-2 rounded-md hover:bg-gray-50 transition-colors group"
                >
                  <p className="text-[13px] font-medium text-gray-700 line-clamp-1 group-hover:text-foreground">
                    {item.text}
                  </p>
                  <p className="text-[10px] text-gray-400 mt-0.5">{item.time}</p>
                </button>
              ))
            )}
          </div>
        </section>
      </div>

      {/* User */}
      <div className="px-4 pt-4 border-t border-gray-100 mt-auto">
        <div
          className="flex items-center gap-2.5 px-2 py-2 hover:bg-gray-50 rounded-md cursor-pointer transition-colors group"
          onClick={() => signOut({ redirectUrl: "/sign-in" })}
          title="Sign out"
        >
          {/* Always render the brand-green initial circle. Clerk's
              auto-generated default avatar (purple X block) clashes with
              the sage palette; we only use user.imageUrl when it's a real
              uploaded photo, not a Clerk-generated default. */}
          {user?.imageUrl && !user.imageUrl.includes("img.clerk.com") ? (
            <img src={user.imageUrl} alt="" className="w-7 h-7 rounded-full object-cover" />
          ) : (
            <div className="w-7 h-7 bg-accent rounded-full flex items-center justify-center text-white text-[10px] font-bold shrink-0">
              {user?.firstName?.[0]?.toUpperCase() ?? user?.emailAddresses?.[0]?.emailAddress?.[0]?.toUpperCase() ?? "?"}
            </div>
          )}
          <div className="overflow-hidden flex-1 min-w-0">
            <p className="text-[12px] font-semibold text-foreground leading-none mb-0.5 truncate">
              {user?.firstName && user?.lastName
                ? `${user.firstName} ${user.lastName}`
                : user?.firstName ?? user?.emailAddresses?.[0]?.emailAddress?.split("@")[0] ?? "User"}
            </p>
            <p className="text-[10px] text-accent/70 truncate font-medium">
              {user?.emailAddresses?.[0]?.emailAddress ?? ""}
            </p>
          </div>
          <span className="text-[10px] text-gray-300 group-hover:text-gray-500 shrink-0 transition-colors">↩</span>
        </div>
      </div>
    </aside>
  );
}

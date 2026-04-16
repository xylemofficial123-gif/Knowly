"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser, useClerk } from "@clerk/nextjs";

interface SidebarItem {
  id: string;
  name: string;
  icon: string;
  href: string;
}

const navItems: SidebarItem[] = [
  { id: "query", name: "Current query", icon: "💎", href: "/" },
  { id: "graph", name: "Knowledge graph", icon: "🌐", href: "/graph" },
  { id: "decisions", name: "Decision log", icon: "📜", href: "/decisions" },
  { id: "ingest", name: "Ingest sources", icon: "⚡", href: "/ingest" },
  { id: "activity", name: "Activity log", icon: "🕒", href: "/activity" },
  { id: "meeting", name: "Live meeting", icon: "🎙️", href: "/meeting" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user } = useUser();
  const { signOut } = useClerk();
  const [recentQueries, setRecentQueries] = useState<{ text: string, time: string }[]>([]);

  useEffect(() => {
    const loadQueries = () => {
      const saved = localStorage.getItem("xylem_recent_queries");
      if (saved) {
        try {
          setRecentQueries(JSON.parse(saved));
        } catch (e) {
          console.error("Failed to parse recent queries", e);
        }
      }
    };

    loadQueries();
    window.addEventListener("storage", loadQueries);
    return () => window.removeEventListener("storage", loadQueries);
  }, []);

  const handleQueryClick = (item: any) => {
    window.dispatchEvent(new CustomEvent("xylem_query", { detail: item }));
  };

  return (
    <aside className="w-[280px] border-r border-green-100/60 flex flex-col pt-8 pb-6 shrink-0 h-screen z-50" style={{ background: "rgba(255,255,255,0.7)", backdropFilter: "blur(12px)" }}>
      {/* Brand */}
      <div className="px-7 mb-10 flex items-center gap-3">
        <div className="w-10 h-10 bg-accent rounded-xl flex items-center justify-center text-white text-xl shadow-lg shadow-accent/20">
          🌱
        </div>
        <span className="text-2xl font-bold tracking-tight text-foreground">Xylem</span>
      </div>

      {/* Primary Action Button */}
      <div className="px-5 mb-10">
        <button
          onClick={() => window.dispatchEvent(new Event("xylem_new_query"))}
          className="w-full text-white py-4 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 transition-all active:scale-95"
          style={{ background: "linear-gradient(135deg, #22c55e 0%, #16a34a 100%)", boxShadow: "0 4px 16px rgba(22,163,74,.3)" }}
        >
          <span className="text-xl leading-none font-light">+</span> New query
        </button>
      </div>

      {/* Navigation Scroll Area */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-3 space-y-10">
        <section>
          <p className="px-4 text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4">Navigate</p>
          <nav className="space-y-1">
            {navItems.map((item) => (
              <Link
                key={item.id}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-2xl text-[14px] font-bold transition-all ${
                  pathname === item.href
                    ? "bg-accent-soft text-accent"
                    : "text-gray-500 hover:bg-gray-50 hover:text-foreground"
                }`}
              >
                <span className="text-lg opacity-80">{item.icon}</span>
                {item.name}
              </Link>
            ))}
          </nav>
        </section>

        <section>
          <p className="px-4 text-[11px] font-bold text-gray-400 uppercase tracking-widest mb-4">Recent</p>
          <div className="space-y-1 px-2">
            {recentQueries.length === 0 ? (
              <div className="px-4 py-8 text-center bg-gray-50/50 rounded-2xl border border-dashed border-gray-100">
                <p className="text-[11px] text-gray-400 font-medium leading-relaxed">
                  Your recent queries will appear here
                </p>
              </div>
            ) : (
              recentQueries.map((item, i) => (
                <button
                  key={i}
                  onClick={() => handleQueryClick(item)}
                  className="w-full text-left px-4 py-3 rounded-2xl hover:bg-gray-50 group transition-all"
                >
                  <p className="text-[13px] font-bold text-gray-700 line-clamp-1 mb-1 group-hover:text-foreground">
                    {item.text}
                  </p>
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">{item.time}</p>
                </button>
              ))
            )}
          </div>
        </section>
      </div>

      {/* User Profile */}
      <div className="px-5 pt-6 border-t border-gray-50 mt-auto">
        <div
          className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 rounded-2xl cursor-pointer transition-all group"
          onClick={() => signOut({ redirectUrl: "/sign-in" })}
          title="Sign out"
        >
          {user?.imageUrl ? (
            <img
              src={user.imageUrl}
              alt="avatar"
              className="w-10 h-10 rounded-full object-cover shadow-lg"
            />
          ) : (
            <div className="w-10 h-10 bg-accent rounded-full flex items-center justify-center text-white text-[11px] font-black shadow-lg shadow-accent/10 shrink-0">
              {user?.firstName?.[0]?.toUpperCase() ?? user?.emailAddresses?.[0]?.emailAddress?.[0]?.toUpperCase() ?? "?"}
            </div>
          )}
          <div className="overflow-hidden flex-1 min-w-0">
            <p className="text-[14px] font-bold text-foreground leading-none mb-1 truncate">
              {user?.firstName && user?.lastName
                ? `${user.firstName} ${user.lastName}`
                : user?.firstName ?? user?.emailAddresses?.[0]?.emailAddress?.split("@")[0] ?? "User"}
            </p>
            <p className="text-[10px] font-bold text-gray-400 truncate uppercase tracking-tighter">
              {user?.emailAddresses?.[0]?.emailAddress ?? ""}
            </p>
          </div>
          <span className="text-[10px] text-gray-300 group-hover:text-gray-400 shrink-0 transition-colors">↩</span>
        </div>
      </div>
    </aside>
  );
}

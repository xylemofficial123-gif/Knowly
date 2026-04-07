"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function PublicNav() {
  const pathname = usePathname();

  const navLink = (href: string, label: string) => {
    const active = pathname === href;
    return (
      <Link
        href={href}
        style={{
          fontSize: 13,
          fontWeight: 500,
          color: active ? "#0a0a0f" : "#64748b",
          textDecoration: "none",
          transition: "color .15s",
          borderBottom: active ? "1.5px solid #5a4efb" : "1.5px solid transparent",
          paddingBottom: 2,
        }}
      >
        {label}
      </Link>
    );
  };

  const isSignIn = pathname.startsWith("/sign-in");

  return (
    <nav style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "18px 56px",
      borderBottom: "1px solid #f1f5f9",
      background: "rgba(253,253,255,.85)",
      backdropFilter: "blur(12px)",
      position: "sticky", top: 0, zIndex: 50,
    }}>
      {/* Logo */}
      <Link href="/sign-in" style={{ textDecoration: "none" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32,
            background: "linear-gradient(135deg, #5a4efb, #7c72ff)",
            borderRadius: 10,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16,
            boxShadow: "0 2px 10px rgba(90,78,251,.25)",
          }}>
            🌱
          </div>
          <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: -0.5, color: "#0a0a0f" }}>
            Xylem
          </span>
        </div>
      </Link>

      {/* Center links */}
      <div style={{ display: "flex", gap: 28 }}>
        {navLink("/features", "Features")}
        {navLink("/docs", "Docs")}
      </div>

      {/* Right actions */}
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        {!isSignIn && (
          <Link href="/sign-in" style={{
            height: 34, padding: "0 16px",
            display: "inline-flex", alignItems: "center",
            background: "transparent", color: "#64748b",
            border: "1px solid #e2e8f0", borderRadius: 8,
            fontSize: 13, fontWeight: 500, textDecoration: "none",
            transition: "all .15s",
          }}>
            Sign in
          </Link>
        )}
        <Link href="/sign-in" style={{
          height: 34, padding: "0 16px",
          display: "inline-flex", alignItems: "center",
          background: "#5a4efb", color: "#fff",
          border: "none", borderRadius: 8,
          fontSize: 13, fontWeight: 600, textDecoration: "none",
          boxShadow: "0 2px 10px rgba(90,78,251,.25)",
          transition: "all .15s",
        }}>
          Get started
        </Link>
      </div>
    </nav>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function PublicNav() {
  const pathname = usePathname();

  const navLink = (href: string, label: string) => {
    const active = pathname === href;
    return (
      <Link href={href} style={{
        fontSize: 13, fontWeight: 500, textDecoration: "none", transition: "color .15s",
        color: active ? "#14532d" : "#4d7c5a",
        borderBottom: active ? "1.5px solid #22c55e" : "1.5px solid transparent",
        paddingBottom: 2,
      }}>
        {label}
      </Link>
    );
  };

  const isSignIn = pathname.startsWith("/sign-in");

  return (
    <nav style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "18px 56px",
    }}>
      <Link href="/sign-in" style={{ textDecoration: "none" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <img
            src="/xylem-mascot.png"
            alt=""
            style={{ width: 32, height: 32, objectFit: "contain" }}
          />
          <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: -0.5, color: "#14532d" }}>
            Xylem
          </span>
        </div>
      </Link>

      <div style={{ display: "flex", gap: 28 }}>
        {navLink("/features", "Features")}
        {navLink("/docs", "Docs")}
      </div>

      <div style={{ display: "flex", gap: 10 }}>
        {!isSignIn && (
          <Link href="/sign-in" style={{
            height: 34, padding: "0 16px", display: "inline-flex", alignItems: "center",
            background: "rgba(255,255,255,.6)", color: "#166534",
            border: "1px solid rgba(134,239,172,.6)", borderRadius: 6,
            fontSize: 13, fontWeight: 500, textDecoration: "none",
          }}>
            Sign in
          </Link>
        )}
        <Link href="/sign-in" style={{
          height: 34, padding: "0 16px", display: "inline-flex", alignItems: "center",
          background: "#16a34a", color: "#fff", border: "none", borderRadius: 6,
          fontSize: 13, fontWeight: 600, textDecoration: "none",
          boxShadow: "0 2px 10px rgba(22,163,74,.3)",
        }}>
          Get started
        </Link>
      </div>
    </nav>
  );
}

import type { ReactNode } from "react";
import type { Me } from "../api/types.ts";
import { BrandMark } from "./BrandMark.tsx";

export type AppRoute = "signin" | "form" | "analysing" | "results" | "rankings" | "course" | "me";

interface ShellProps {
  active: AppRoute;
  me: Me | null;
  userEmail: string | null;
  onNavigate: (hash: string) => void;
  children: ReactNode;
}

const NAV_ITEMS: { id: AppRoute; hash: string; label: string; mobileLabel: string }[] = [
  { id: "form", hash: "#/form", label: "My results", mobileLabel: "Results" },
  { id: "results", hash: "#/results", label: "Courses", mobileLabel: "Courses" },
  { id: "rankings", hash: "#/rankings", label: "Ranked order", mobileLabel: "Order" },
  { id: "me", hash: "#/me", label: "Chats", mobileLabel: "Chats" },
];

function MobileIcon({ id }: { id: AppRoute }) {
  switch (id) {
    case "form":
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 20h4L19 9l-4-4L4 16z" />
        </svg>
      );
    case "results":
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
          <rect x="4" y="4" width="7" height="7" rx="2" />
          <rect x="13" y="4" width="7" height="7" rx="2" />
          <rect x="4" y="13" width="7" height="7" rx="2" />
          <rect x="13" y="13" width="7" height="7" rx="2" />
        </svg>
      );
    case "rankings":
      return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round">
          <path d="M9 6h11M9 12h11M9 18h11M4 6h1M4 12h1M4 18h1" />
        </svg>
      );
    default:
      return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z" />
        </svg>
      );
  }
}

export function Shell({ active, me, userEmail, onNavigate, children }: ShellProps) {
  const chatUsage = me?.usage?.chat;
  const pct = chatUsage && chatUsage.limit > 0 ? Math.min(100, (chatUsage.used / chatUsage.limit) * 100) : 0;
  const initial = (userEmail?.[0] ?? "S").toUpperCase();

  return (
    <>
      <div className="wrap">
        <header className="topbar">
          <div className="nav-inner">
            <BrandMark href="#/results" onClick={() => onNavigate("#/results")} />
            <nav className="nav" aria-label="Main navigation">
              {NAV_ITEMS.map((item) => {
                const isActive = active === item.id || (active === "course" && item.id === "results");
                return (
                  <a
                    key={item.id}
                    href={item.hash}
                    className={isActive ? "active" : ""}
                    onClick={(e) => {
                      e.preventDefault();
                      onNavigate(item.hash);
                    }}
                  >
                    {item.label}
                  </a>
                );
              })}
            </nav>
            <div className="nav-right">
              {chatUsage && chatUsage.limit > 0 && (
                <span className="usage" title="Chat questions used today">
                  <span className="bar">
                    <i style={{ width: `${pct}%` }} />
                  </span>
                  <span className="num">
                    {chatUsage.used}/{chatUsage.limit} today
                  </span>
                </span>
              )}
              <a
                className="avatar"
                href="#/me"
                aria-label="Account"
                onClick={(e) => {
                  e.preventDefault();
                  onNavigate("#/me");
                }}
              >
                {initial}
              </a>
            </div>
          </div>
        </header>
        <main className="page view-enter">{children}</main>
      </div>

      <nav className="tabbar" aria-label="Sections">
        {NAV_ITEMS.map((item) => {
          const isActive = active === item.id || (active === "course" && item.id === "results");
          return (
            <a
              key={item.id}
              href={item.hash}
              className={isActive ? "active" : ""}
              onClick={(e) => {
                e.preventDefault();
                onNavigate(item.hash);
              }}
            >
              <span className="ic">
                <MobileIcon id={item.id} />
              </span>
              <span>{item.mobileLabel}</span>
            </a>
          );
        })}
      </nav>
    </>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/",            label: "Dashboard",   icon: "▣" },
  { href: "/products",    label: "Products",    icon: "◈" },
  { href: "/approvals",   label: "Approvals",   icon: "◎" },
  { href: "/briefs",      label: "Daily Brief", icon: "◉" },
  { href: "/alerts",      label: "Alerts",      icon: "⚠" },
  { href: "/stores",      label: "Stores",      icon: "◆" },
  { href: "/agents",      label: "Agents",      icon: "⟳" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 min-h-screen bg-gray-950 border-r border-gray-800 flex flex-col">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-yellow-400 text-xl font-bold">⬡</span>
          <div>
            <p className="text-white font-semibold text-sm leading-none">Aurum</p>
            <p className="text-gray-500 text-xs">Commerce OS</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-0.5">
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-yellow-400/10 text-yellow-300 font-medium"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/60"
              }`}
            >
              <span className="text-base w-4 text-center opacity-70">{icon}</span>
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-gray-800">
        <p className="text-xs text-gray-600">v1.0.0 · DGX Spark</p>
      </div>
    </aside>
  );
}

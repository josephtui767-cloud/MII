/** Application shell with sidebar navigation. */

import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Overview", icon: "📊", description: "Security posture at a glance — key metrics, risk distribution, and top priority actions for leadership." },
  { to: "/identities", label: "Identities", icon: "🔑", description: "All discovered machine identities (IAM roles, tokens) with risk scores, last-used dates, and filtering." },
  { to: "/findings", label: "Findings", icon: "🚨", description: "Actionable security issues — each with severity, blast radius, and copy-paste remediation commands." },
  { to: "/compliance", label: "Compliance", icon: "📋", description: "Policy checks against security best practices — pass/fail status with specific failing identities." },
  { to: "/trust-debt", label: "Trust Debt", icon: "💰", description: "Accumulated unnecessary trust — like technical debt but for permissions. Lower score = cleaner environment." },
  { to: "/blast-path", label: "Blast Path", icon: "💥", description: "Attack simulation — what happens if an identity is compromised? Traces the full attack chain step by step." },
  { to: "/graph", label: "Trust Graph", icon: "🔗", description: "Visual map of trust relationships — who can assume whom, showing GitLab-to-AWS OIDC connections." },
];

export function Layout() {
  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 text-gray-100 flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-lg font-bold tracking-tight">MII Platform</h1>
          <p className="text-xs text-gray-400 mt-0.5">Machine Identity Intelligence</p>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-start gap-2 px-3 py-2 rounded text-sm group ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-gray-300 hover:bg-gray-800 hover:text-white"
                }`
              }
            >
              <span className="mt-0.5">{item.icon}</span>
              <div>
                <span className="font-medium">{item.label}</span>
                <p className="text-xs opacity-60 mt-0.5 leading-tight">{item.description}</p>
              </div>
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-gray-700 text-xs text-gray-500">
          v0.2.0 — Security Features
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

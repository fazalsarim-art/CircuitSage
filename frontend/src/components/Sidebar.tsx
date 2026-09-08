import { NavLink } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";

interface NavItem {
  to: string;
  label: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Ask" },
  { to: "/documents", label: "Documents" },
  { to: "/benchmark", label: "Benchmark" },
  { to: "/eval-runs", label: "Eval runs" },
  { to: "/feedback", label: "Feedback", adminOnly: true },
  { to: "/system", label: "System", adminOnly: true },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { isAdmin } = useAuth();
  return (
    <nav className="sidebar" aria-label="Primary">
      <ul>
        {NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.to === "/"}
              onClick={onNavigate}
              className={({ isActive }) => (isActive ? "active" : undefined)}
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

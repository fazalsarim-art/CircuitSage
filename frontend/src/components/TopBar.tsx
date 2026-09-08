import { useAuth } from "../features/auth/AuthContext";

export function TopBar({ onToggleNav }: { onToggleNav: () => void }) {
  const { user, logout } = useAuth();
  return (
    <header className="topbar">
      <button
        type="button"
        className="nav-toggle"
        aria-label="Toggle navigation"
        onClick={onToggleNav}
      >
        ☰
      </button>
      <span className="brand">CircuitSage</span>
      <div className="topbar-right">
        {user && <span className="topbar-user">{user.email}</span>}
        <button type="button" className="logout" onClick={() => void logout()}>
          Sign out
        </button>
      </div>
    </header>
  );
}

import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";

export function AdminRoute() {
  const { status, isAdmin } = useAuth();
  if (status === "loading") {
    return (
      <div className="app-loading" role="status">
        Loading…
      </div>
    );
  }
  if (status === "unauthenticated") {
    return <Navigate to="/signin" replace />;
  }
  if (!isAdmin) {
    return (
      <main className="page">
        <h1>Administrators only</h1>
        <p>You do not have access to this area.</p>
      </main>
    );
  }
  return <Outlet />;
}

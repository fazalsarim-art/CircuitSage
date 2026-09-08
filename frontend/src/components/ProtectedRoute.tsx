import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../features/auth/AuthContext";

export function ProtectedRoute() {
  const { status } = useAuth();
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
  return <Outlet />;
}

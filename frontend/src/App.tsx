import { Navigate, Route, Routes } from "react-router-dom";

import { AdminRoute } from "./components/AdminRoute";
import { AppShell } from "./components/AppShell";
import { NotFoundPage } from "./components/NotFoundPage";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { useAuth } from "./features/auth/AuthContext";
import { SignInPage } from "./features/auth/SignInPage";
import { AskPage } from "./pages/AskPage";
import { BenchmarkPage } from "./pages/BenchmarkPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { EvalRunsPage } from "./pages/EvalRunsPage";
import { FeedbackPage } from "./pages/FeedbackPage";
import { SystemPage } from "./pages/placeholders";

function SignInRoute() {
  const { status } = useAuth();
  if (status === "authenticated") {
    return <Navigate to="/" replace />;
  }
  return <SignInPage />;
}

export function App() {
  return (
    <Routes>
      <Route path="/signin" element={<SignInRoute />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<AskPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="benchmark" element={<BenchmarkPage />} />
          <Route path="eval-runs" element={<EvalRunsPage />} />
          <Route element={<AdminRoute />}>
            <Route path="feedback" element={<FeedbackPage />} />
            <Route path="system" element={<SystemPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}

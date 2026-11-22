import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";
import AuthPage from "./pages/AuthPage";
import NotFoundPage from "./pages/NotFoundPage";
import SiteDetailPage from "./pages/SiteDetailPage";
import SiteFormPage from "./pages/SiteFormPage";
import SitesPage from "./pages/SitesPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route
            element={
              <RequireLogin>
                <Layout />
              </RequireLogin>
            }
          >
            <Route index element={<SitesPage />} />
            <Route path="sites/new" element={<SiteFormPage />} />
            <Route path="sites/:id" element={<SiteDetailPage />} />
            <Route path="sites/:id/edit" element={<SiteFormPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

/** Only for logged-in advisors. This is for the user experience: the real
 * protection is on the server, which checks the session on every request. */
function RequireLogin({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  const location = useLocation();
  if (state.status === "loading") return <p className="page-status">Loading…</p>;
  if (state.status === "signed-out") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}

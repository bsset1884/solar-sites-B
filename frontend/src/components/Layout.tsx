import { useState } from "react";
import { Link, Outlet, useNavigate } from "react-router";
import { useAuth } from "../auth";
import { SunMark } from "./Icons";

export function Logo() {
  return (
    <Link to="/" className="logo" aria-label="Solar sites, home">
      <SunMark />
      <span>solar sites</span>
    </Link>
  );
}

export default function Layout() {
  const { state, logout } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  async function handleLogout() {
    setBusy(true);
    try {
      await logout();
    } finally {
      setBusy(false);
      navigate("/login");
    }
  }

  return (
    <>
      <header className="site-header">
        <div className="container site-header__inner">
          <Logo />
          <nav className="site-header__nav" aria-label="Main">
            <Link to="/">Sites</Link>
          </nav>
          <div className="site-header__user">
            {state.status === "signed-in" && <span className="site-header__email">{state.email}</span>}
            <button type="button" className="btn btn--outline btn--small" onClick={handleLogout} disabled={busy}>
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="container page">
        <Outlet />
      </main>
      <Footer />
    </>
  );
}

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container">Solar data: PVGIS © European Union. Estimates, not guarantees.</div>
    </footer>
  );
}

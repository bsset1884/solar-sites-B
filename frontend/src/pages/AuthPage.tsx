import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation } from "react-router";
import { ApiError, errorMessage } from "../api";
import { useAuth } from "../auth";
import Field from "../components/Field";
import { ArrowRight } from "../components/Icons";
import { Footer, Logo } from "../components/Layout";

type Mode = "login" | "register";

const TEXT = {
  login: { title: "Log in", button: "Log in", switchText: "New here?", switchLink: "Create an account" },
  register: { title: "Create your account", button: "Create account", switchText: "Already have an account?", switchLink: "Log in" },
};

/** Where to go after logging in. Only our own paths, never another website. */
function safeRedirect(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from;
  return typeof from === "string" && from.startsWith("/") && !from.startsWith("//") ? from : "/";
}

export default function AuthPage({ mode }: { mode: Mode }) {
  // A new key resets the form when switching between log in and register.
  return <AuthForm key={mode} mode={mode} />;
}

function AuthForm({ mode }: { mode: Mode }) {
  const { state, login, register } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const text = TEXT[mode];

  if (state.status === "signed-in") return <Navigate to={safeRedirect(location.state)} replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFieldErrors({});
    setFormError(null);
    try {
      await (mode === "login" ? login(email, password) : register(email, password));
      // Logged in: the auth state changes and <Navigate> above takes over.
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) setFieldErrors(error.fieldErrors);
      else setFormError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="site-header">
        <div className="container site-header__inner">
          <Logo />
          <div className="site-header__user">
            <Link to={mode === "login" ? "/register" : "/login"} className="btn btn--primary btn--small">
              {mode === "login" ? "Create account" : "Log in"}
            </Link>
          </div>
        </div>
      </header>

      <main className="container auth">
        <h1 className="hero-title">
          Solar estimates
          <span className="hero-title__soft">for every client roof</span>
        </h1>
        <p className="hero-sub">
          Yearly production, monthly detail and what a home battery adds — <strong>in a few clicks.</strong>
        </p>

        <form className="card auth__card" onSubmit={handleSubmit} noValidate>
          <h2 className="auth__title">{text.title}</h2>
          {formError && (
            <p className="alert" role="alert">
              {formError}
            </p>
          )}
          <Field
            name="email"
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={fieldErrors.email}
          />
          <Field
            name="password"
            label="Password"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={fieldErrors.password}
            hint={mode === "register" ? "At least 8 characters." : undefined}
          />
          <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
            {busy ? "One moment…" : text.button} {!busy && <ArrowRight />}
          </button>
          <p className="auth__switch">
            {text.switchText} <Link to={mode === "login" ? "/register" : "/login"}>{text.switchLink}</Link>
          </p>
        </form>
      </main>
      <Footer />
    </>
  );
}

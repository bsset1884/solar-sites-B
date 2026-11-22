import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, setCsrfToken, setUnauthorizedHandler } from "./api";

type AuthState = { status: "loading" } | { status: "signed-out" } | { status: "signed-in"; email: string };

type AuthContextValue = {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const signedIn = useCallback((me: { email: string; csrfToken: string }) => {
    setCsrfToken(me.csrfToken);
    setState({ status: "signed-in", email: me.email });
  }, []);

  const signedOut = useCallback(() => {
    setCsrfToken(null);
    setState({ status: "signed-out" });
  }, []);

  useEffect(() => {
    // A 401 later on (session expired or logged out elsewhere) shows the login page.
    setUnauthorizedHandler(signedOut);
    // Is this browser already logged in? (The cookie is HttpOnly, so we have to ask.)
    const controller = new AbortController();
    api.me(controller.signal).then(signedIn, () => {
      if (!controller.signal.aborted) signedOut();
    });
    return () => controller.abort();
  }, [signedIn, signedOut]);

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      login: async (email, password) => signedIn(await api.login(email, password)),
      register: async (email, password) => signedIn(await api.register(email, password)),
      logout: async () => {
        try {
          await api.logout();
        } finally {
          signedOut();
        }
      },
    }),
    [state, signedIn, signedOut],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}

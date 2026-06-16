import { createContext, useContext, useState, useCallback } from "react";
import api from "../api";

const AuthContext = createContext(null);

// Helper: sync the token to axios default headers immediately (no useEffect delay)
function applyToken(token) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    const t = sessionStorage.getItem("access_token");
    applyToken(t); // set header synchronously on page load
    return t;
  });

  const [user, setUser] = useState(() => {
    const u = sessionStorage.getItem("user");
    return u ? JSON.parse(u) : null;
  });

  const _saveSession = (access_token, user_id, email, role = "user") => {
    applyToken(access_token);
    setToken(access_token);
    setUser({ id: user_id, email, role });
    sessionStorage.setItem("access_token", access_token);
    sessionStorage.setItem("user", JSON.stringify({ id: user_id, email, role }));
  };

  const login = useCallback(async (email, password) => {
    const res = await api.post("/auth/login", { email, password });
    _saveSession(res.data.access_token, res.data.user_id, email, res.data.role ?? "user");
  }, []);

  const register = useCallback(async (email, password) => {
    const res = await api.post("/auth/register", { email, password });
    _saveSession(res.data.access_token, res.data.user_id, email, res.data.role ?? "user");
  }, []);

  const logout = useCallback(() => {
    applyToken(null);
    setToken(null);
    setUser(null);
    sessionStorage.removeItem("access_token");
    sessionStorage.removeItem("user");
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, login, register, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

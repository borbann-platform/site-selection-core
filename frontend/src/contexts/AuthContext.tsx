import React, { createContext, useContext, useEffect, useState } from "react";
import { api, type UserResponse, type TokenResponse } from "../lib/api";

interface AuthContextType {
  user: UserResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    confirmPassword: string,
    firstName: string,
    lastName: string
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = "auth_tokens";

function getStoredTokens(): TokenResponse | null {
  const stored = localStorage.getItem(TOKEN_KEY);
  if (!stored) return null;
  try {
    return JSON.parse(stored);
  } catch {
    return null;
  }
}

function storeTokens(tokens: TokenResponse) {
  localStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
}

function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const tokens = getStoredTokens();
      if (!tokens) {
        setIsLoading(false);
        return;
      }

      try {
        const currentUser = await api.getCurrentUser(tokens.access_token);
        setUser(currentUser);
      } catch {
        // Try to refresh the token
        try {
          const newTokens = await api.refreshToken(tokens.refresh_token);
          storeTokens(newTokens);
          const currentUser = await api.getCurrentUser(newTokens.access_token);
          setUser(currentUser);
        } catch {
          // Refresh failed, clear tokens
          clearTokens();
        }
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    const tokens = await api.login({ email, password });
    storeTokens(tokens);
    const currentUser = await api.getCurrentUser(tokens.access_token);
    setUser(currentUser);
  };

  const register = async (
    email: string,
    password: string,
    confirmPassword: string,
    firstName: string,
    lastName: string
  ) => {
    await api.register({
      email,
      password,
      confirm_password: confirmPassword,
      first_name: firstName,
      last_name: lastName,
    });
    // Auto-login after registration
    await login(email, password);
  };

  const logout = () => {
    clearTokens();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

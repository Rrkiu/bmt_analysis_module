// src/lib/auth.tsx - Updated with new flow
import React, { createContext, useContext, useEffect, useState } from "react";
import {
  me,
  checkEmail,
  login,
  signup,
  verifyOtp as verifyOtpApi,
  logout,
  type User,
} from "./api";

type AuthContextType = {
  user: User | null;
  loading: boolean;
  signOut: () => Promise<void>;
  checkEmail: (email: string) => Promise<{ exists: boolean }>;
  login: (email: string, phone: string) => Promise<void>;
  signup: (
    email: string,
    name: string,
    phone: string
  ) => Promise<{ message: string; requires_otp: boolean }>;
  verifyOtp: (email: string, otp: string) => Promise<void>;
};

const AuthContext = createContext<AuthContextType>(null!);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    me()
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        signOut: async () => {
          try {
            await logout();
          } finally {
            setUser(null);
          }
        },
        checkEmail: (email) => checkEmail(email),
        login: async (email, phone) => {
          const userData = await login(email, phone);
          setUser(userData);
        },
        signup: (email, name, phone) => signup(email, name, phone),
        verifyOtp: async (email, otp) => {
          const userData = await verifyOtpApi(email, otp);
          setUser(userData);
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

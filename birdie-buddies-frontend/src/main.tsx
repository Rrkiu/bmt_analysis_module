/**
 * main.tsx - Application Entry Point
 * 
 * [수정됨 - 2025-12-23]
 * AuthProvider를 조건부로 적용하여 분석 도구는 인증 우회
 * 
 * 구조:
 * - /analysis/* : AuthProvider 없이 렌더링 (공개 접근)
 * - 그 외 모든 경로: AuthProvider로 감싸짐 (인증 필요)
 */

import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, useLocation } from "react-router-dom";
import { AuthProvider } from "./lib/auth";
import App from "./App";
import "./styles/mobile.css";

const qc = new QueryClient();

/**
 * [추가됨] ConditionalAuthProvider
 * 
 * /analysis/* 경로는 AuthProvider를 우회
 * 다른 모든 경로는 AuthProvider 적용
 */
function ConditionalAuthProvider({ children }: { children: React.ReactNode }) {
  const location = useLocation();

  // /analysis로 시작하는 경로는 인증 우회
  if (location.pathname.startsWith('/analysis')) {
    return <>{children}</>;
  }

  // 그 외 경로는 인증 필요
  return <AuthProvider>{children}</AuthProvider>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <ConditionalAuthProvider>
          <App />
        </ConditionalAuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);


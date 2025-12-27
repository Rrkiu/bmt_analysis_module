/**
 * App.tsx - Main Application Router
 * 
 * [수정됨 - 2025-12-23]
 * 이 파일은 두 개의 독립적인 애플리케이션을 라우팅합니다:
 * 
 * 1. Birdie Buddies 앱 (기존)
 *    - 경로: /login, /sessions, /wallet, /my, /admin
 *    - 인증 필요: AuthProvider + RouteGuards 사용
 *    - 백엔드: Birdie Buddies API
 * 
 * 2. 배드민턴 분석 도구 (신규 추가)
 *    - 경로: /analysis/*
 *    - 인증 불필요: 공개 접근 가능
 *    - 백엔드: 분석 엔진 API (localhost:8000)
 * 
 * 주의사항:
 * - /analysis/* 경로는 AuthProvider 외부에 위치
 * - 두 앱은 완전히 독립적으로 동작
 * - 향후 머지 시 이 구조를 유지해야 함
 */

import { Routes, Route, Navigate } from "react-router-dom";

// ============================================
// [기존] Birdie Buddies 앱 컴포넌트
// ============================================
import SessionsPage from "./pages/SessionsPage";
import SessionDetailPage from "./pages/SessionDetailPage";
import WalletPage from "./pages/WalletPage";
import MyGamesPage from "./pages/MyGamesPage";
import AdminPage from "./pages/AdminPage";
// import ProfilePage from "./pages/ProfilePage"; // used as the login screen
import LoginPage from "./pages/LoginPage";
import {
  RequireAuth,
  RequireGuest,
  RequireAdmin,
} from "./components/RouteGuards";

// ============================================
// [추가됨] 배드민턴 분석 도구 컴포넌트
// ============================================
import AnalysisApp from "./AnalysisApp";

export default function App() {
  return (
    <Routes>
      {/* ==========================================
          [기존] Birdie Buddies 앱 라우팅
          - 인증 필요
          - AuthProvider로 감싸져 있음 (main.tsx 참조)
          ========================================== */}

      {/* Default to /login */}
      <Route path="/" element={<Navigate to="/login" replace />} />

      {/* Public (guest-only) */}
      <Route
        path="/login"
        element={
          <RequireGuest>
            <LoginPage />
          </RequireGuest>
        }
      />

      {/* Authenticated app */}
      <Route
        path="/sessions"
        element={
          <RequireAuth>
            <SessionsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/sessions/:id"
        element={
          <RequireAuth>
            <SessionDetailPage />
          </RequireAuth>
        }
      />
      <Route
        path="/wallet"
        element={
          <RequireAuth>
            <WalletPage />
          </RequireAuth>
        }
      />
      <Route
        path="/my"
        element={
          <RequireAuth>
            <MyGamesPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <AdminPage />
          </RequireAdmin>
        }
      />

      {/* ==========================================
          [추가됨 - 2025-12-23] 배드민턴 분석 도구
          
          경로: /analysis/*
          인증: 불필요 (공개 접근)
          
          하위 라우트:
          - /analysis/calibration : 코트 캘리브레이션
          - /analysis/video       : 비디오 분석 (향후 구현)
          - /analysis/profiles    : 프로파일 관리 (향후 구현)
          
          주의:
          - RequireAuth로 감싸지 않음
          - AnalysisApp 내부에서 자체 라우팅 처리
          - 백엔드 API: http://localhost:8000 (VITE_API_BASE_URL)
          ========================================== */}
      <Route path="/analysis/*" element={<AnalysisApp />} />

      {/* Catch-all → /login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

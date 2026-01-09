/**
 * AnalysisApp.tsx
 * 
 * 배드민턴 코트 분석 도구 - 독립 실행형 앱
 * 
 * [추가됨 - 2025-12-23]
 * - Birdie Buddies 메인 앱과 분리된 독립 분석 도구
 * - 인증 불필요: 누구나 접근 가능
 * - 백엔드 API (localhost:8000)와 직접 통신
 * 
 * 주요 기능:
 * 1. 코트 캘리브레이션 (4점 코너 지정)
 * 2. 비디오 분석 (셔틀콕 추적)
 * 3. 프로파일 관리
 * 
 * 라우팅 구조:
 * - /analysis/calibration  : 캘리브레이션 페이지
 * - /analysis/video        : 비디오 분석 페이지 (향후 구현)
 * - /analysis/profiles     : 프로파일 관리 (향후 구현)
 */

import { Routes, Route, Navigate, Link } from "react-router-dom";
import { CalibrationPage } from "./pages/Analysis/CalibrationPage";
import { VideoAnalysisPage } from "./pages/Analysis/VideoAnalysisPage";  // [추가됨]

export default function AnalysisApp() {
    return (
        <div className="analysis-app">
            {/* 
        [추가됨] 분석 도구 전용 네비게이션 바
        - Birdie Buddies 앱의 MobileShell과 독립적
        - 간단한 탭 네비게이션 제공
      */}
            <nav className="analysis-nav">
                <div className="nav-container">
                    <h1>🏸 배드민턴 코트 분석 도구</h1>
                    <div className="nav-links">
                        <Link to="/analysis/calibration" className="nav-link">
                            캘리브레이션
                        </Link>
                        <Link to="/analysis/video" className="nav-link">
                            비디오 분석
                        </Link>
                        <Link to="/analysis/profiles" className="nav-link">
                            프로파일 관리
                        </Link>
                    </div>
                </div>
            </nav>

            {/* 
        [추가됨] 분석 도구 라우팅
        - 모든 라우트는 인증 없이 접근 가능
        - /analysis/* 경로 하위에서만 동작
      */}
            <main className="analysis-content">
                <Routes>
                    {/* 기본 경로: 캘리브레이션으로 리다이렉트 */}
                    <Route path="/" element={<Navigate to="/analysis/calibration" replace />} />

                    {/* 
            [추가됨] 캘리브레이션 페이지
            - 이미지 업로드
            - 4점 코너 지정
            - Homography 계산
          */}
                    <Route path="/calibration" element={<CalibrationPage />} />

                    {/* 
            [추가됨 - Step 2] 비디오 분석 페이지
            - 비디오 파일 업로드
            - HTML5 Video Player
            - 재생 컨트롤
          */}
                    <Route path="/video" element={<VideoAnalysisPage />} />

                    {/* 
            [향후 구현] 프로파일 관리 페이지
            - 캘리브레이션 프로파일 저장/로드
            - 프로파일 목록 관리
          */}
                    <Route
                        path="/profiles"
                        element={
                            <div style={{ padding: '40px', textAlign: 'center' }}>
                                <h2>프로파일 관리 페이지</h2>
                                <p>향후 구현 예정</p>
                            </div>
                        }
                    />

                    {/* Catch-all: 잘못된 경로는 캘리브레이션으로 */}
                    <Route path="*" element={<Navigate to="/analysis/calibration" replace />} />
                </Routes>
            </main>

            {/* 
        [추가됨] 간단한 인라인 스타일
        - 향후 별도 CSS 파일로 분리 권장
      */}
            <style>{`
        .analysis-app {
          min-height: 100vh;
          background: #f5f5f5;
        }

        .analysis-nav {
          background: white;
          border-bottom: 2px solid #e0e0e0;
          padding: 15px 0;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .nav-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 0 20px;
        }

        .analysis-nav h1 {
          margin: 0 0 15px 0;
          font-size: 24px;
          color: #333;
        }

        .nav-links {
          display: flex;
          gap: 20px;
        }

        .nav-link {
          padding: 8px 16px;
          text-decoration: none;
          color: #555;
          border-radius: 4px;
          transition: all 0.2s;
          font-weight: 500;
        }

        .nav-link:hover {
          background: #f0f0f0;
          color: #007bff;
        }

        .analysis-content {
          max-width: 1400px;
          margin: 0 auto;
          padding: 20px;
        }

        @media (max-width: 768px) {
          .nav-links {
            flex-direction: column;
            gap: 10px;
          }

          .analysis-nav h1 {
            font-size: 20px;
          }
        }
      `}</style>
        </div>
    );
}

// src/pages/LoginPage.tsx
import { useState } from "react";
import MobileShell from "../components/MobileShell/MobileShell";
import { useAuth } from "../lib/auth";
import { useNavigate, useLocation, Navigate } from "react-router-dom";

type Step = "email" | "login" | "signup" | "verify";

export default function LoginPage() {
  const {
    user,
    loading,
    checkEmail: checkEmailCtx,
    login: loginCtx,
    signup: signupCtx,
    verifyOtp: verifyOtpCtx,
  } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [step, setStep] = useState<Step>("email");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!loading && user) {
    const to =
      (typeof (loc.state as any)?.from === "string"
        ? (loc.state as any).from
        : (loc.state as any)?.from?.pathname) || "/sessions";
    return <Navigate to={to} replace />;
  }

  const handleEmailSubmit = async () => {
    if (!email.trim()) {
      setError("Please enter your email");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await checkEmailCtx(email.trim());
      setStep(result.exists ? "login" : "signup");
    } catch (e: any) {
      setError(e.message || "Failed to check email");
    } finally {
      setBusy(false);
    }
  };

  const handleLogin = async () => {
    if (!phone.trim()) {
      setError("Please enter your phone number");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await loginCtx(email.trim(), phone.trim());
      //   setStep("verify");
      const to =
        (typeof (loc.state as any)?.from === "string"
          ? (loc.state as any).from
          : (loc.state as any)?.from?.pathname) || "/sessions";
      nav(to, { replace: true });
    } catch (e: any) {
      setError(e.message || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  const handleSignup = async () => {
    if (!name.trim() || !phone.trim()) {
      setError("Please fill all fields");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signupCtx(email.trim(), name.trim(), phone.trim());
      setStep("verify");
    } catch (e: any) {
      setError(e.message || "Signup failed");
    } finally {
      setBusy(false);
    }
  };

  const handleVerifyOtp = async () => {
    if (otp.length < 6) {
      setError("Please enter the 6-digit code");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await verifyOtpCtx(email.trim(), otp.trim());
      const to =
        (typeof (loc.state as any)?.from === "string"
          ? (loc.state as any).from
          : (loc.state as any)?.from?.pathname) || "/sessions";
      nav(to, { replace: true });
    } catch (e: any) {
      setError(e.message || "Verification failed");
      setOtp("");
    } finally {
      setBusy(false);
    }
  };

  const handleBack = () => {
    setStep("email");
    setPhone("");
    setName("");
    setOtp("");
    setError(null);
  };

  if (loading) {
    return (
      <MobileShell>
        <div className="skeleton" />
      </MobileShell>
    );
  }

  return (
    <MobileShell>
      <div className="detail-container">
        <h1 className="page-title">
          {step === "email" && "Welcome"}
          {step === "login" && "Welcome Back"}
          {step === "signup" && "Create Account"}
          {step === "verify" && "Verify Code"}
        </h1>

        {step === "email" && (
          <>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input
                className="form-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                onKeyDown={(e) => e.key === "Enter" && handleEmailSubmit()}
                autoFocus
              />
            </div>
            <button
              className="btn btn-primary"
              disabled={busy || !email}
              onClick={handleEmailSubmit}
            >
              {busy ? "Checking..." : "Continue"}
            </button>
          </>
        )}

        {step === "login" && (
          <>
            <div className="form-group">
              <label className="form-label">Email</label>
              <div
                className="form-input"
                style={{ background: "var(--light)", cursor: "not-allowed" }}
              >
                {email}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Phone Number</label>
              <input
                className="form-input"
                type="tel"
                value={phone}
                onChange={(e) =>
                  setPhone(e.target.value.replace(/[^0-9]/g, ""))
                }
                placeholder="7781234567"
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                autoFocus
              />
              <small
                style={{
                  color: "var(--medium)",
                  fontSize: "12px",
                  marginTop: "4px",
                  display: "block",
                }}
              >
                Enter your registered phone (no dashes)
              </small>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              {/* <button
                className="btn btn-secondary"
                disabled={busy}
                onClick={handleBack}
              >
                ← Back
              </button> */}
              <button
                className="btn btn-primary"
                disabled={busy || !phone}
                onClick={handleLogin}
                style={{ flex: 1 }}
              >
                {busy ? "Signing In..." : "Sign In"}
              </button>
            </div>
          </>
        )}

        {step === "signup" && (
          <>
            <div className="form-group">
              <label className="form-label">Email</label>
              <div
                className="form-input"
                style={{ background: "var(--light)", cursor: "not-allowed" }}
              >
                {email}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Name (한국이름/영문이름)</label>
              <input
                className="form-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="권지용 / G Dragon"
                autoFocus
              />
            </div>
            <div className="form-group">
              <label className="form-label">Phone Number</label>
              <input
                className="form-input"
                type="tel"
                value={phone}
                onChange={(e) =>
                  setPhone(e.target.value.replace(/[^0-9]/g, ""))
                }
                placeholder="7781234567"
              />
              <small
                style={{
                  color: "var(--medium)",
                  fontSize: "12px",
                  marginTop: "4px",
                  display: "block",
                }}
              >
                No dashes - used to verify your identity
              </small>
            </div>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                className="btn btn-secondary"
                disabled={busy}
                onClick={handleBack}
              >
                ← Back
              </button>
              <button
                className="btn btn-primary"
                disabled={busy || !name || !phone}
                onClick={handleSignup}
                style={{ flex: 1 }}
              >
                {busy ? "Creating..." : "Create Account"}
              </button>
            </div>
          </>
        )}

        {step === "verify" && (
          <>
            {/* <p
              style={{
                textAlign: "center",
                color: "var(--medium)",
                marginBottom: "20px",
              }}
            >
              We sent a 6-digit code to
              <br />
              <strong>{email}</strong>
            </p> */}
            <div className="form-group">
              {/* <label className="form-label">Verification Code</label> */}
              <input
                className="form-input"
                inputMode="numeric"
                maxLength={6}
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                placeholder="000000"
                onKeyDown={(e) =>
                  e.key === "Enter" && otp.length === 6 && handleVerifyOtp()
                }
                autoFocus
                style={{
                  fontSize: "20px",
                  letterSpacing: "4px",
                  textAlign: "center",
                  fontWeight: "600",
                }}
              />
            </div>
            <button
              className="btn btn-primary"
              disabled={busy || otp.length < 6}
              onClick={handleVerifyOtp}
              style={{ marginBottom: "12px" }}
            >
              {busy ? "Verifying..." : "Verify & Continue"}
            </button>
            <div style={{ display: "flex", gap: "8px" }}>
              {/* <button
                className="btn btn-secondary"
                disabled={busy}
                onClick={handleResend}
                style={{ flex: 1 }}
              >
                Resend
              </button> */}
              <button
                className="btn btn-secondary"
                disabled={busy}
                onClick={handleBack}
                style={{ flex: 1 }}
              >
                ← Back
              </button>
            </div>
          </>
        )}

        {error && (
          <div
            className="info-banner"
            style={{
              marginTop: "16px",
              background: error.includes("success") ? "#dcfce7" : "#fee2e2",
              color: error.includes("success") ? "#16a34a" : "#dc2626",
            }}
          >
            {error}
          </div>
        )}
      </div>
    </MobileShell>
  );
}

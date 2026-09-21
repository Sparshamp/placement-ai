import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../shared/auth/AuthContext";
import AuthLayout from "./AuthLayout";

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signup(email, password, displayName);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || "Signup failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <h2>Create your account</h2>
      <p className="muted auth-lead">A few details and you&apos;re ready to start practicing.</p>
      <form className="auth-form" onSubmit={handleSubmit}>
        <div className="auth-field">
          <label className="muted" htmlFor="signup-name">Name</label>
          <input
            id="signup-name"
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
          />
        </div>

        <div className="auth-field">
          <label className="muted" htmlFor="signup-email">Email</label>
          <input
            id="signup-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div className="auth-field">
          <label className="muted" htmlFor="signup-password">Password</label>
          <input
            id="signup-password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <span className="faint">At least 8 characters.</span>
        </div>

        {error && <p className="warning-text">{error}</p>}

        <button className="primary" type="submit" disabled={busy}>
          {busy ? "Creating account…" : "Sign up"}
        </button>
      </form>
      <p className="muted auth-switch">
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </AuthLayout>
  );
}

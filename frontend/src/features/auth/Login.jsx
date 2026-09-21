import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../../shared/auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      navigate(location.state?.from ?? "/", { replace: true });
    } catch (err) {
      setError(err.message || "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-narrow">
      <h2>Log in</h2>
      <form onSubmit={handleSubmit}>
        <label className="muted" htmlFor="login-email">Email</label>
        <input id="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />

        <label className="muted" htmlFor="login-password" style={{ marginTop: "0.8rem", display: "block" }}>Password</label>
        <input id="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />

        {error && <p className="warning-text">{error}</p>}

        <button className="primary" type="submit" disabled={busy} style={{ marginTop: "1.2rem" }}>
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
      <p className="muted" style={{ marginTop: "1rem" }}>Don't have an account? <Link to="/signup">Sign up</Link></p>
    </div>
  );
}
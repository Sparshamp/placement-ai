import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../shared/auth/AuthContext";

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
    <div className="page-narrow">
      <h2>Create an account</h2>
      <form onSubmit={handleSubmit}>
        <label className="muted" htmlFor="signup-name">Name</label>
        <input id="signup-name" type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} required />

        <label className="muted" htmlFor="signup-email" style={{ marginTop: "0.8rem", display: "block" }}>Email</label>
        <input id="signup-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />

        <label className="muted" htmlFor="signup-password" style={{ marginTop: "0.8rem", display: "block" }}>Password (min. 8 characters)</label>
        <input id="signup-password" type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />

        {error && <p className="warning-text">{error}</p>}

        <button className="primary" type="submit" disabled={busy} style={{ marginTop: "1.2rem" }}>
          {busy ? "Creating account…" : "Sign up"}
        </button>
      </form>
      <p className="muted" style={{ marginTop: "1rem" }}>Already have an account? <Link to="/login">Log in</Link></p>
    </div>
  );
}
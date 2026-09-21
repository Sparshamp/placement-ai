import ThemeToggle from "../../shared/components/ThemeToggle";
import "./auth.css";

export default function AuthLayout({ children }) {
  return (
    <div className="auth-shell">
      <div className="auth-theme">
        <ThemeToggle expanded={false} />
      </div>
      <section className="auth-brand" aria-hidden="true">
        <p className="auth-kicker">Placement AI</p>
        <h1>Practice, interview, and land the role.</h1>
        <p>
          Adaptive aptitude, mock interviews, and job matches from your resume —
          all in one place.
        </p>
      </section>
      <section className="auth-panel">
        <div className="auth-card">{children}</div>
      </section>
    </div>
  );
}

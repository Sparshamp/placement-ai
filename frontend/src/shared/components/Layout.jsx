import { useState, useEffect } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { checkConnection } from "../../features/adaptive-aptitude/api";
import { useAuth } from "../auth/AuthContext";
import ThemeToggle from "./ThemeToggle";

const SIDEBAR_KEY = "sidebarExpanded";

export default function Layout() {
  const [connected, setConnected] = useState(null);
  const [expanded, setExpanded] = useState(() => localStorage.getItem(SIDEBAR_KEY) === "true");

  useEffect(() => {
    let cancelled = false;
    checkConnection().then((ok) => { if (!cancelled) setConnected(ok); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, String(expanded));
  }, [expanded]);

  const { student, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  const connStatus = connected === null ? "unknown" : connected ? "ok" : "down";
  const connLabel = connected === null ? "Checking…" : connected ? "Connected" : "Not reachable";

  return (
    <div className={`app-shell ${expanded ? "sidebar-expanded" : "sidebar-collapsed"}`}>
      <aside className={`sidebar ${expanded ? "sidebar--expanded" : "sidebar--collapsed"}`}>
        <button
          className="sidebar-toggle"
          onClick={() => setExpanded((e) => !e)}
          aria-label={expanded ? "Collapse sidebar" : "Expand sidebar"}
          aria-expanded={expanded}
          title={expanded ? "Collapse sidebar" : "Expand sidebar"}
        >
          {expanded ? "«" : "☰"}
        </button>

        <nav className="side-nav">
          <NavLink to="/" end aria-label="Dashboard" title="Dashboard"
            className={({ isActive }) => `side-nav-link ${isActive ? "side-nav-link--active" : ""}`}>
            <span className="side-nav-icon" aria-hidden="true">📊</span>
            {expanded && <span>Dashboard</span>}
          </NavLink>
          <NavLink to="/practice" aria-label="Practice Session" title="Practice Session"
            className={({ isActive }) => `side-nav-link ${isActive ? "side-nav-link--active" : ""}`}>
            <span className="side-nav-icon" aria-hidden="true">🎯</span>
            {expanded && <span>Practice Session</span>}
          </NavLink>
          <NavLink to="/interview" aria-label="Interview Simulation" title="Interview Simulation"
            className={({ isActive }) => `side-nav-link ${isActive ? "side-nav-link--active" : ""}`}>
            <span className="side-nav-icon" aria-hidden="true">🎤</span>
            {expanded && <span>Interview Simulation</span>}
          </NavLink>
          <NavLink to="/jobs" aria-label="Job Recommendations" title="Job Recommendations"
            className={({ isActive }) => `side-nav-link ${isActive ? "side-nav-link--active" : ""}`}>
            <span className="side-nav-icon" aria-hidden="true">💼</span>
            {expanded && <span>Job Recommendations</span>}
          </NavLink>
        </nav>

        <div className="sidebar-spacer" />

        <ThemeToggle expanded={expanded} />

        {student && (
          <button
            className="side-nav-link"
            onClick={handleLogout}
            aria-label="Log out"
            title={student.email}
          >
            <span className="side-nav-icon" aria-hidden="true">🚪</span>
            {expanded && <span>Log out{student.display_name ? ` (${student.display_name})` : ""}</span>}
          </button>
        )}

        <div className="sidebar-status" title={connLabel}>
          <span className={`status-dot status-dot--${connStatus}`} />
          {expanded && <span className="muted" style={{ fontSize: "0.82rem" }}>{connLabel}</span>}
        </div>
      </aside>

      <main className="main-content">
        {connected === false ? (
          <div className="card">
            <p>We can't reach the server right now.</p>
            <p className="faint">Please make sure it's running, then refresh this page.</p>
          </div>
        ) : (
          <Outlet />
        )}
      </main>
    </div>
  );
}
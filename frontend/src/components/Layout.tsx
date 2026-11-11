import { Link, NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { useCursorFx } from "../hooks/useCursorFx";
import { toggleTheme } from "../hooks/useTheme";

const traderLinks = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/practice", label: "Practice" },
  { to: "/stats", label: "Statistics" },
  { to: "/journal", label: "Journal" },
  { to: "/feedback", label: "Feedback" },
  { to: "/profile", label: "Profile" },
];

export default function Layout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  useCursorFx();

  if (!user) return <Navigate to="/login" replace />;
  const admin = user.role === "Admin";

  return (
    <>
      <header className="bar">
        <div className="bar-in">
          <Link className="logo" to={admin ? "/admin" : "/dashboard"}>
            Epoch<i>.</i>
          </Link>
          <nav className="nav" aria-label="Main">
            {admin ? (
              <NavLink to="/admin" className="active">
                Admin workspace
              </NavLink>
            ) : (
              traderLinks.map((l) => (
                <NavLink key={l.to} to={l.to} className={({ isActive }) => (isActive ? "active" : undefined)}>
                  {l.label}
                </NavLink>
              ))
            )}
          </nav>
          <div className="bar-end">
            <button className="btn ghost small" type="button" onClick={toggleTheme}>
              Theme
            </button>
            <button
              className="btn small"
              type="button"
              onClick={() => {
                signOut();
                navigate("/login");
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}

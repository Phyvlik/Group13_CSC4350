import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/replay", label: "Replay" },
  { to: "/journal", label: "Journal" },
  { to: "/stats", label: "Stats" },
];

export default function Layout() {
  return (
    <>
      <header>
        <nav style={{ display: "flex", gap: "1rem", padding: "1rem" }}>
          <strong>Epoch</strong>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to}>
              {link.label}
            </NavLink>
          ))}
          <NavLink to="/login" style={{ marginLeft: "auto" }}>
            Log in
          </NavLink>
        </nav>
      </header>
      <main style={{ padding: "1rem" }}>
        <Outlet />
      </main>
    </>
  );
}

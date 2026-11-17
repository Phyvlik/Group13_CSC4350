import { Navigate } from "react-router-dom";
import { api } from "../api/client";
import { ErrorPanel, Loading } from "../components/State";
import { useLoad } from "../hooks/useLoad";

/** Opens the session in progress, or the new-session form when there is none. */
export default function PracticeRedirect() {
  const { data, error } = useLoad(() => api.sessions(), []);
  if (error) return <ErrorPanel message={error} />;
  if (!data) return <Loading />;
  const live = data.filter((s) => s.status === "In progress").pop();
  return <Navigate to={live ? `/replay/${live.id}` : "/new"} replace />;
}

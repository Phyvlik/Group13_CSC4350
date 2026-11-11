import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";
import { ToastProvider } from "./components/Toasts";
import AdminPage from "./pages/Admin";
import DashboardPage from "./pages/Dashboard";
import FeedbackPage from "./pages/Feedback";
import JournalPage from "./pages/Journal";
import LoginPage from "./pages/Login";
import NewSessionPage from "./pages/NewSession";
import PracticeRedirect from "./pages/PracticeRedirect";
import ProfilePage from "./pages/Profile";
import ReplayPage from "./pages/Replay";
import StatsPage from "./pages/Stats";

function Home() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "Admin" ? "/admin" : "/dashboard"} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<LoginPage mode="signin" />} />
            <Route path="/signup" element={<LoginPage mode="signup" />} />
            <Route element={<Layout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/new" element={<NewSessionPage />} />
              <Route path="/practice" element={<PracticeRedirect />} />
              <Route path="/replay/:id" element={<ReplayPage />} />
              <Route path="/stats" element={<StatsPage />} />
              <Route path="/stats/:id" element={<StatsPage />} />
              <Route path="/journal" element={<JournalPage />} />
              <Route path="/journal/:id" element={<JournalPage />} />
              <Route path="/feedback" element={<FeedbackPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/admin" element={<AdminPage />} />
            </Route>
            <Route path="*" element={<Home />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

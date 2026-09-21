import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./shared/auth/AuthContext";
import ProtectedRoute from "./shared/auth/ProtectedRoute";
import Layout from "./shared/components/Layout";
import Login from "./features/auth/Login";
import Signup from "./features/auth/Signup";
import Dashboard from "./features/adaptive-aptitude/Dashboard";
import Practice from "./features/adaptive-aptitude/Practice";
import InterviewPage from "./features/interview-simulation/InterviewPage";
import JobsPage from "./features/job-recommendation/JobsPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<Dashboard />} />
              <Route path="practice" element={<Practice />} />
              <Route path="interview" element={<InterviewPage />} />
              <Route path="jobs" element={<JobsPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
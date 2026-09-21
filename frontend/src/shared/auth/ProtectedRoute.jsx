import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute() {
  const { student, loading } = useAuth();
  if (loading) return null;
  if (!student) return <Navigate to="/login" replace />;
  return <Outlet />;
}
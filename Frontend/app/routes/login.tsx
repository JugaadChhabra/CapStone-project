import React from "react";
import LoginForm from "../components/auth/LoginForm";

const LoginPage: React.FC = () => (
  <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
    <LoginForm />
  </div>
);

export default LoginPage;

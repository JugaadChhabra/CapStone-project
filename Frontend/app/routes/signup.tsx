import React from "react";
import SignupForm from "../components/auth/SignupForm";

const SignupPage: React.FC = () => (
  <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
    <SignupForm />
  </div>
);

export default SignupPage;

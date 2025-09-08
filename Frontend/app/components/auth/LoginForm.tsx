import React, { useState } from "react";
import Input from "../ui/Input";
import Button from "../ui/Button";
import Card from "../ui/Card";
import "./LoginForm.css";

const LoginForm: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // handle login logic here (API call, validation, etc.)
    // For now, redirect to dashboard
    window.location.href = "/dashboard";
  };

  return (
    <Card className="login-card">
      <form className="login-form" onSubmit={handleSubmit}>
        <h2>Login</h2>
        <Input
          type="email"
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          required
        />
        <Input
          type="password"
          placeholder="Password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          required
        />
        <Button type="submit">Sign In</Button>
        <div style={{ textAlign: 'center', marginTop: '0.5rem' }}>
          <span style={{ color: '#e0e0e0', fontSize: '1rem' }}>
            Don't have an account?{' '}
            <a href="/signup" style={{ color: '#fff', textDecoration: 'underline', opacity: 0.85 }}>Sign up</a>
          </span>
        </div>
      </form>
    </Card>
  );
};

export default LoginForm;

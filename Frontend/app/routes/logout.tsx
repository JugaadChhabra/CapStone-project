import React from "react";

const Logout: React.FC = () => {
  // You can add logout logic here (e.g., clearing tokens, redirecting)
  React.useEffect(() => {
    // Example: localStorage.removeItem('token');
    window.location.href = "/login";
  }, []);
  return <div>Logging out...</div>;
};

export default Logout;

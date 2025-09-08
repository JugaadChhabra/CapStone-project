import React from "react";

const Logout: React.FC = () => {
  React.useEffect(() => {
    window.location.href = "/";
  }, []);
  return null;
};

export default Logout;
import React from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";
import "./Layout.css";

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="glass-layout">
    <Sidebar />
    <div className="main-content">
      <Header />
      {children}
    </div>
  </div>
);

export default Layout;

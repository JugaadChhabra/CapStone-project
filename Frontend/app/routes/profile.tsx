import React from "react";
import ProfileCard from "../components/auth/ProfileCard";

const ProfilePage: React.FC = () => (
  <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
    <ProfileCard />
  </div>
);

export default ProfilePage;

import React from "react";
import Card from "../ui/Card";
import Button from "../ui/Button";
import "./ProfileCard.css";

const ProfileCard: React.FC = () => (
  <Card className="profile-card">
    <div className="profile-info">
      <div className="profile-avatar">U</div>
      <div className="profile-details">
        <div className="profile-name">User Name</div>
        <div className="profile-email">user@email.com</div>
      </div>
    </div>
  <Button onClick={() => (window.location.href = "/logout")}>Logout</Button>
  </Card>
);

export default ProfileCard;

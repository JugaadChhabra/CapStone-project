import React from "react";
import PortfolioCard from "../components/dashboard/PortfolioCard";
import StrategyOverview from "../components/dashboard/StrategyOverview";

const DashboardPage: React.FC = () => {
  // Sample data - this would come from API
  const portfolioData = [
    { symbol: "RELIANCE", change: 1.85, ltp: 2456.30 },
    { symbol: "TCS", change: -0.67, ltp: 3489.75 },
    { symbol: "INFY", change: 2.34, ltp: 1612.80 },
    { symbol: "HDFC", change: 0.45, ltp: 1587.90 },
    { symbol: "ICICIBANK", change: -1.23, ltp: 921.45 },
    { symbol: "HDFCBANK", change: 1.78, ltp: 1523.60 },
    { symbol: "BHARTIARTL", change: -0.89, ltp: 845.25 },
  ];

  const performanceData = [
    {
      title: "Open P&L",
      data: {
        all: { label: "Open P&L", value: "-1,218.00", percentage: -0.06, isPositive: false },
        long: { label: "Open P&L", value: "", percentage: 0 },
        short: { label: "Open P&L", value: "", percentage: 0 }
      }
    },
    {
      title: "Net profit",
      data: {
        all: { label: "Net profit", value: "+1,425,982.42", percentage: 485.26, isPositive: true },
        long: { label: "Net profit", value: "+1,460,048.39", percentage: 492.91, isPositive: true },
        short: { label: "Net profit", value: "-34,065.97", percentage: -9.65, isPositive: false }
      }
    },
    {
      title: "Gross profit",
      data: {
        all: { label: "Gross profit", value: "2,362,705.80", percentage: 472.64, isPositive: true },
        long: { label: "Gross profit", value: "1,908,027.63", percentage: 381.81, isPositive: true },
        short: { label: "Gross profit", value: "453,678.17", percentage: 90.74, isPositive: true }
      }
    },
    {
      title: "Gross loss",
      data: {
        all: { label: "Gross loss", value: "936,723.38", percentage: 187.34, isPositive: false },
        long: { label: "Gross loss", value: "448,979.24", percentage: 89.80, isPositive: false },
        short: { label: "Gross loss", value: "487,744.14", percentage: 97.55, isPositive: false }
      }
    },
    {
      title: "Commission paid",
      data: {
        all: { label: "Commission paid", value: "185,771.63", percentage: 0 },
        long: { label: "Commission paid", value: "97,424.11", percentage: 0 },
        short: { label: "Commission paid", value: "88,347.52", percentage: 0 }
      }
    },
    {
      title: "Buy & hold return",
      data: {
        all: { label: "Buy & hold return", value: "+23,216,503.80", percentage: 4643.30, isPositive: true },
        long: { label: "Buy & hold return", value: "", percentage: 0 },
        short: { label: "Buy & hold return", value: "", percentage: 0 }
      }
    }
  ];

  return (
    <div style={{ 
      minHeight: "100vh", 
      padding: "2rem", 
      display: "flex", 
      gap: "2rem",
      flexWrap: "wrap",
      alignItems: "flex-start"
    }}>
      <div style={{ flex: "1", minWidth: "600px" }}>
        <StrategyOverview
          strategyName="Supertrend Strategy Report"
          invested="₹8,50,000"
          current="₹12,75,430"
          dateRange="Mar 14, 2006 — Sep 8, 2025"
          performanceData={performanceData}
        />
      </div>
      
      <div style={{ minWidth: "300px" }}>
        <PortfolioCard
          holdings={portfolioData}
          totalValue={1275430}
          totalChange={2.34}
        />
      </div>
    </div>
  );
};

export default DashboardPage;

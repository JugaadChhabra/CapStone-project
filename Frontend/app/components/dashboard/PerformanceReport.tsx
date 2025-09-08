import React from "react";
import Card from "../ui/Card";
import "./PerformanceReport.css";

interface PerformanceMetric {
  label: string;
  value: string | number;
  percentage?: number;
  isPositive?: boolean;
}

interface PerformanceSection {
  title: string;
  data: {
    all?: PerformanceMetric;
    long?: PerformanceMetric;
    short?: PerformanceMetric;
  };
}

interface PerformanceReportProps {
  strategyName: string;
  invested: string;
  current: string;
  dateRange: string;
  sections: PerformanceSection[];
  selectedTabs?: string[];
}

const PerformanceReport: React.FC<PerformanceReportProps> = ({
  strategyName,
  invested,
  current,
  dateRange,
  sections,
  selectedTabs = ["Overview", "Performance", "Trades analysis"]
}) => {
  const formatValue = (value: string | number) => {
    if (typeof value === 'number') {
      return value.toLocaleString();
    }
    return value;
  };

  const formatPercentage = (percentage?: number, isPositive?: boolean) => {
    if (percentage === undefined) return '';
    const sign = percentage >= 0 ? '+' : '';
    const className = isPositive !== undefined ? 
      (isPositive ? 'positive' : 'negative') : 
      (percentage >= 0 ? 'positive' : 'negative');
    return <span className={className}>{sign}{percentage.toFixed(2)}%</span>;
  };

  return (
    <Card className="performance-report">
      <div className="performance-header">
        <div className="strategy-info">
          <h3>{strategyName}</h3>
          <div className="investment-summary">
            <div className="investment-line">Invested - {invested}</div>
            <div className="investment-line">Current - {current}</div>
          </div>
        </div>
        <div className="date-range">{dateRange}</div>
      </div>

      <div className="performance-tabs">
        {selectedTabs.map((tab, index) => (
          <button key={index} className={`tab ${index === 1 ? 'active' : ''}`}>
            {tab}
          </button>
        ))}
      </div>

      <div className="performance-metrics">
        <div className="metrics-header">
          <span className="metric-label">Metric</span>
          <span className="metric-all">All</span>
          <span className="metric-long">Long</span>
          <span className="metric-short">Short</span>
        </div>

        {sections.map((section, sectionIndex) => (
          <div key={sectionIndex} className="metric-row">
            <span className="metric-label">{section.title}</span>
            
            <div className="metric-value">
              {section.data.all && (
                <>
                  {formatValue(section.data.all.value)}
                  {formatPercentage(section.data.all.percentage, section.data.all.isPositive)}
                </>
              )}
            </div>
            
            <div className="metric-value">
              {section.data.long && (
                <>
                  {formatValue(section.data.long.value)}
                  {formatPercentage(section.data.long.percentage, section.data.long.isPositive)}
                </>
              )}
            </div>
            
            <div className="metric-value">
              {section.data.short && (
                <>
                  {formatValue(section.data.short.value)}
                  {formatPercentage(section.data.short.percentage, section.data.short.isPositive)}
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};

export default PerformanceReport;

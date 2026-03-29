import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import type { BarSeriesOption, LineSeriesOption, PieSeriesOption } from "echarts/charts";
import { BarChart, LineChart, PieChart } from "echarts/charts";
import type { GridComponentOption, LegendComponentOption, TooltipComponentOption } from "echarts/components";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsType } from "echarts/core";

import type { KeywordAnalysis, TrendAnalysis } from "../api";

echarts.use([BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

type AnalyticsChartOption = echarts.ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | PieSeriesOption
  | GridComponentOption
  | LegendComponentOption
  | TooltipComponentOption
>;

interface AnalyticsChartsProps {
  trends: TrendAnalysis | null;
  keywords: KeywordAnalysis | null;
  isLoading?: boolean;
}

// Chart colors matching the design system
const CHART_COLORS = {
  primary: ["#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe", "#dbeafe"],
  secondary: ["#8b5cf6", "#a78bfa", "#c4b5fd", "#ddd6fe", "#ede9fe"],
  success: ["#22c55e", "#4ade80", "#86efac", "#bbf7d0", "#dcfce7"],
  warning: ["#f59e0b", "#fbbf24", "#fcd34d", "#fde68a", "#fef3c7"],
  error: ["#ef4444", "#f87171", "#fca5a5", "#fecaca", "#fee2e2"],
  neutral: ["#64748b", "#94a3b8", "#cbd5e1", "#e2e8f0", "#f1f5f9"],
};

export function AnalyticsCharts({ trends, keywords, isLoading }: AnalyticsChartsProps) {
  const timeSeriesRef = useRef<HTMLDivElement>(null);
  const sourceDistRef = useRef<HTMLDivElement>(null);
  const scoreDistRef = useRef<HTMLDivElement>(null);
  const keywordsRef = useRef<HTMLDivElement>(null);

  const chartsRef = useRef<EChartsType[]>([]);

  // Initialize and update charts
  useEffect(() => {
    if (!timeSeriesRef.current || !sourceDistRef.current || !scoreDistRef.current || !keywordsRef.current) return;

    // Dispose existing charts
    chartsRef.current.forEach((chart) => chart.dispose());
    chartsRef.current = [];

    // Create new charts
    const timeSeriesChart = echarts.init(timeSeriesRef.current);
    const sourceDistChart = echarts.init(sourceDistRef.current);
    const scoreDistChart = echarts.init(scoreDistRef.current);
    const keywordsChart = echarts.init(keywordsRef.current);

    chartsRef.current = [timeSeriesChart, sourceDistChart, scoreDistChart, keywordsChart];

    // Common chart options
    const commonGrid = {
      left: "3%",
      right: "4%",
      bottom: "3%",
      top: "15%",
      containLabel: true,
    };

    const tooltip = {
      trigger: "axis" as const,
      backgroundColor: "rgba(255, 255, 255, 0.95)",
      borderColor: "#e2e8f0",
      borderWidth: 1,
      textStyle: { color: "#1e293b" },
      padding: [8, 12],
      borderRadius: 8,
      shadowColor: "rgba(0, 0, 0, 0.1)",
      shadowBlur: 10,
    };

    // 1. Time Series Chart - Publication Trends
    if (trends?.timeSeries) {
      const timeSeriesOption: AnalyticsChartOption = {
        grid: commonGrid,
        tooltip: {
          ...tooltip,
          formatter: (params: unknown) => {
            const p = params as Array<{ name: string; value: number }>;
            return `<div style="font-weight:600">${p[0].name}</div>
                    <div style="color:#3b82f6">文献数量: ${p[0].value}</div>`;
          },
        },
        xAxis: {
          type: "category",
          data: trends.timeSeries.map((t) => t.date),
          axisLine: { lineStyle: { color: "#cbd5e1" } },
          axisLabel: { color: "#64748b", rotate: 45 },
          axisTick: { show: false },
        },
        yAxis: {
          type: "value",
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: "#64748b" },
          splitLine: { lineStyle: { color: "#f1f5f9" } },
        },
        series: [
          {
            name: "文献数量",
            type: "line",
            data: trends.timeSeries.map((t) => t.count),
            smooth: true,
            symbol: "circle",
            symbolSize: 8,
            lineStyle: {
              color: "#3b82f6",
              width: 3,
            },
            itemStyle: {
              color: "#3b82f6",
              borderWidth: 2,
              borderColor: "#fff",
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: "rgba(59, 130, 246, 0.3)" },
                { offset: 1, color: "rgba(59, 130, 246, 0.05)" },
              ]),
            },
          },
        ],
      };
      timeSeriesChart.setOption(timeSeriesOption);
    }

    // 2. Source Distribution Pie Chart
    if (trends?.sourceDistribution) {
      const sourceData = Object.entries(trends.sourceDistribution).map(([name, value]) => ({
        name,
        value,
      }));

      const sourceDistOption: AnalyticsChartOption = {
        tooltip: {
          trigger: "item" as const,
          backgroundColor: "rgba(255, 255, 255, 0.95)",
          borderColor: "#e2e8f0",
          borderWidth: 1,
          textStyle: { color: "#1e293b" },
          formatter: (params: unknown) => {
            const p = params as { name: string; value: number; percent: number };
            return `<div style="font-weight:600">${p.name}</div>
                    <div>数量: ${p.value}</div>
                    <div>占比: ${p.percent}%</div>`;
          },
        },
        legend: {
          orient: "vertical",
          right: "5%",
          top: "center",
          textStyle: { color: "#64748b" },
        },
        series: [
          {
            name: "来源分布",
            type: "pie",
            radius: ["40%", "70%"],
            center: ["35%", "50%"],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 8,
              borderColor: "#fff",
              borderWidth: 2,
            },
            label: { show: false },
            emphasis: {
              label: {
                show: true,
                fontSize: 14,
                fontWeight: "bold",
              },
            },
            data: sourceData,
            color: CHART_COLORS.primary,
          },
        ],
      };
      sourceDistChart.setOption(sourceDistOption);
    }

    // 3. Score Distribution Bar Chart
    if (trends?.scoreDistribution) {
      const scoreData = Object.entries(trends.scoreDistribution)
        .sort((a, b) => parseFloat(a[0]) - parseFloat(b[0]));

      const scoreDistOption: AnalyticsChartOption = {
        grid: commonGrid,
        tooltip: {
          ...tooltip,
          formatter: (params: unknown) => {
            const p = params as Array<{ name: string; value: number }>;
            return `<div style="font-weight:600">相关度: ${p[0].name}</div>
                    <div>数量: ${p[0].value}</div>`;
          },
        },
        xAxis: {
          type: "category",
          data: scoreData.map(([range]) => range),
          axisLine: { lineStyle: { color: "#cbd5e1" } },
          axisLabel: { color: "#64748b" },
          axisTick: { show: false },
        },
        yAxis: {
          type: "value",
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: "#64748b" },
          splitLine: { lineStyle: { color: "#f1f5f9" } },
        },
        series: [
          {
            name: "数量",
            type: "bar",
            data: scoreData.map(([, count]) => count),
            barWidth: "60%",
            itemStyle: {
              borderRadius: [4, 4, 0, 0],
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: "#8b5cf6" },
                { offset: 1, color: "#a78bfa" },
              ]),
            },
          },
        ],
      };
      scoreDistChart.setOption(scoreDistOption);
    }

    // 4. Keywords Bar Chart
    if (keywords?.topKeywords) {
      const top20Keywords = keywords.topKeywords.slice(0, 20).reverse();

      const keywordsOption: AnalyticsChartOption = {
        grid: {
          left: "3%",
          right: "8%",
          bottom: "3%",
          top: "5%",
          containLabel: true,
        },
        tooltip: {
          trigger: "axis" as const,
          axisPointer: { type: "shadow" },
          backgroundColor: "rgba(255, 255, 255, 0.95)",
          borderColor: "#e2e8f0",
          borderWidth: 1,
          textStyle: { color: "#1e293b" },
        },
        xAxis: {
          type: "value",
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: "#64748b" },
          splitLine: { lineStyle: { color: "#f1f5f9" } },
        },
        yAxis: {
          type: "category",
          data: top20Keywords.map((k) => k.word),
          axisLine: { lineStyle: { color: "#cbd5e1" } },
          axisLabel: { color: "#64748b" },
          axisTick: { show: false },
        },
        series: [
          {
            name: "出现次数",
            type: "bar",
            data: top20Keywords.map((k) => k.count),
            barWidth: "70%",
            itemStyle: {
              borderRadius: [0, 4, 4, 0],
              color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: "#22c55e" },
                { offset: 1, color: "#4ade80" },
              ]),
            },
          },
        ],
      };
      keywordsChart.setOption(keywordsOption);
    }

    // Handle resize
    const handleResize = () => {
      chartsRef.current.forEach((chart) => chart.resize());
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chartsRef.current.forEach((chart) => chart.dispose());
    };
  }, [trends, keywords]);

  if (isLoading) {
    return (
      <div className="analytics-loading">
        <div className="analytics-loading-spinner" />
        <span>加载分析数据...</span>
      </div>
    );
  }

  if (!trends && !keywords) {
    return (
      <div className="analytics-empty">
        <div className="analytics-empty-icon">📊</div>
        <p>暂无分析数据</p>
        <span>完成研究任务后可查看趋势分析</span>
      </div>
    );
  }

  return (
    <div className="analytics-charts">
      {/* Summary Cards */}
      <div className="analytics-summary">
        <div className="analytics-summary-card">
          <div className="analytics-summary-icon" style={{ background: "linear-gradient(135deg, #3b82f6, #60a5fa)" }}>
            📚
          </div>
          <div className="analytics-summary-content">
            <span className="analytics-summary-value">{trends?.totalItems || 0}</span>
            <span className="analytics-summary-label">文献总数</span>
          </div>
        </div>
        <div className="analytics-summary-card">
          <div className="analytics-summary-icon" style={{ background: "linear-gradient(135deg, #f59e0b, #fbbf24)" }}>
            ⭐
          </div>
          <div className="analytics-summary-content">
            <span className="analytics-summary-value">{trends?.favoritedItems || 0}</span>
            <span className="analytics-summary-label">收藏文献</span>
          </div>
        </div>
        <div className="analytics-summary-card">
          <div className="analytics-summary-icon" style={{ background: "linear-gradient(135deg, #22c55e, #4ade80)" }}>
            🏷️
          </div>
          <div className="analytics-summary-content">
            <span className="analytics-summary-value">{keywords?.vocabularySize || 0}</span>
            <span className="analytics-summary-label">关键词汇</span>
          </div>
        </div>
        <div className="analytics-summary-card">
          <div className="analytics-summary-icon" style={{ background: "linear-gradient(135deg, #8b5cf6, #a78bfa)" }}>
            📄
          </div>
          <div className="analytics-summary-content">
            <span className="analytics-summary-value">{keywords?.analyzedDocuments || 0}</span>
            <span className="analytics-summary-label">分析文献</span>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="analytics-charts-grid">
        {/* Time Series Chart */}
        <div className="analytics-chart-card wide">
          <div className="analytics-chart-header">
            <h3>📈 文献发表趋势</h3>
            <span className="analytics-chart-subtitle">按月份统计的文献数量分布</span>
          </div>
          <div ref={timeSeriesRef} className="analytics-chart-container" style={{ height: 280 }} />
        </div>

        {/* Source Distribution Chart */}
        <div className="analytics-chart-card">
          <div className="analytics-chart-header">
            <h3>🌐 来源分布</h3>
            <span className="analytics-chart-subtitle">不同数据源的文献占比</span>
          </div>
          <div ref={sourceDistRef} className="analytics-chart-container" style={{ height: 280 }} />
        </div>

        {/* Score Distribution Chart */}
        <div className="analytics-chart-card">
          <div className="analytics-chart-header">
            <h3>📊 相关度分布</h3>
            <span className="analytics-chart-subtitle">文献相关度评分分布</span>
          </div>
          <div ref={scoreDistRef} className="analytics-chart-container" style={{ height: 280 }} />
        </div>

        {/* Keywords Chart */}
        <div className="analytics-chart-card wide">
          <div className="analytics-chart-header">
            <h3>🔑 高频关键词</h3>
            <span className="analytics-chart-subtitle">文献中出现频率最高的关键词</span>
          </div>
          <div ref={keywordsRef} className="analytics-chart-container" style={{ height: 400 }} />
        </div>
      </div>
    </div>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  exportLibraryRis,
  getLibraryItems,
  getLibraryKeywords,
  getLibrarySummary,
  getLibraryTrends,
  toggleFavorite,
  type LibraryFilters,
  type LibraryItem,
  type KeywordAnalysis,
  type LibrarySummary,
  type TrendAnalysis,
} from "../api";
import { AnalyticsCharts } from "./AnalyticsCharts";

interface LibraryPageProps {
  onClose?: () => void;
}

const PAGE_SIZE_OPTIONS = [10, 20, 50];
const SOURCE_OPTIONS = [
  { value: "", label: "全部来源" },
  { value: "PAPER", label: "学术论文" },
  { value: "WEB", label: "网页" },
];
const SORT_OPTIONS = [
  { value: "created_at", label: "创建时间" },
  { value: "score", label: "相关度分数" },
  { value: "source_type", label: "来源类型" },
];

export function LibraryPage({ onClose }: LibraryPageProps) {
  // Data states
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<LibrarySummary | null>(null);
  const [trends, setTrends] = useState<TrendAnalysis | null>(null);
  const [keywords, setKeywords] = useState<KeywordAnalysis | null>(null);

  // Filter states
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sourceType, setSourceType] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [minScore, setMinScore] = useState<number | null>(null);
  const [favoritedOnly, setFavoritedOnly] = useState(false);
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [activeTab, setActiveTab] = useState<"list" | "trends" | "keywords">("list");

  // Loading states
  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyticsLoading, setIsAnalyticsLoading] = useState(false);

  const totalPages = Math.ceil(total / pageSize);

  const fetchItems = useCallback(async () => {
    setIsLoading(true);
    try {
      const filters: LibraryFilters = {
        page,
        page_size: pageSize,
        source_type: sourceType || undefined,
        search: searchQuery || undefined,
        min_score: minScore ?? undefined,
        favorited_only: favoritedOnly,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      const response = await getLibraryItems(filters);
      setItems(response.items);
      setTotal(response.total);
    } catch (error) {
      console.error("Failed to fetch library items:", error);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, sourceType, searchQuery, minScore, favoritedOnly, sortBy, sortOrder]);

  const fetchAnalytics = useCallback(async () => {
    setIsAnalyticsLoading(true);
    try {
      const [summaryData, trendsData, keywordsData] = await Promise.all([
        getLibrarySummary(),
        getLibraryTrends(90),
        getLibraryKeywords(50),
      ]);
      setSummary(summaryData);
      setTrends(trendsData);
      setKeywords(keywordsData);
    } catch (error) {
      console.error("Failed to fetch analytics:", error);
    } finally {
      setIsAnalyticsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const handleExportRis = async () => {
    try {
      await exportLibraryRis(favoritedOnly);
    } catch (error) {
      console.error("Failed to export RIS:", error);
      alert("导出失败，请重试");
    }
  };

  const handleToggleFavorite = async (evidenceId: string) => {
    try {
      const updated = await toggleFavorite(evidenceId);
      setItems((prev) =>
        prev.map((item) => (item.id === evidenceId ? { ...item, favorited: updated.favorited } : item))
      );
    } catch (error) {
      console.error("Failed to toggle favorite:", error);
    }
  };

  const handleSearch = () => {
    setPage(1);
    fetchItems();
  };

  const handleReset = () => {
    setPage(1);
    setSourceType("");
    setSearchQuery("");
    setMinScore(null);
    setFavoritedOnly(false);
    setSortBy("created_at");
    setSortOrder("desc");
  };

  const renderPagination = () => (
    <div className="library-pagination">
      <div className="library-pagination-info">
        共 {total} 条，第 {page}/{totalPages || 1} 页
      </div>
      <div className="library-pagination-controls">
        <button
          className="library-btn library-btn-secondary"
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1 || isLoading}
        >
          上一页
        </button>
        <span className="library-page-indicator">{page}</span>
        <button
          className="library-btn library-btn-secondary"
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page >= totalPages || isLoading}
        >
          下一页
        </button>
      </div>
      <div className="library-page-size">
        <label>每页:</label>
        <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}>
          {PAGE_SIZE_OPTIONS.map((size) => (
            <option key={size} value={size}>{size}</option>
          ))}
        </select>
      </div>
    </div>
  );

  const renderFilters = () => (
    <div className="library-filters">
      <div className="library-filter-group">
        <input
          type="text"
          placeholder="搜索标题、内容..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          className="library-search-input"
        />
        <button className="library-btn library-btn-primary" onClick={handleSearch}>
          搜索
        </button>
      </div>
      <div className="library-filter-row">
        <select value={sourceType} onChange={(e) => { setSourceType(e.target.value); setPage(1); }}>
          {SOURCE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <select value={sortBy} onChange={(e) => { setSortBy(e.target.value); setPage(1); }}>
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <button
          className="library-btn library-btn-secondary"
          onClick={() => { setSortOrder((o) => (o === "asc" ? "desc" : "asc")); setPage(1); }}
        >
          {sortOrder === "asc" ? "↑ 升序" : "↓ 降序"}
        </button>
        <label className="library-checkbox">
          <input
            type="checkbox"
            checked={favoritedOnly}
            onChange={(e) => { setFavoritedOnly(e.target.checked); setPage(1); }}
          />
          仅收藏
        </label>
        <button className="library-btn library-btn-ghost" onClick={handleReset}>
          重置
        </button>
      </div>
    </div>
  );

  const renderItemCard = (item: LibraryItem) => (
    <div key={item.id} className="library-card">
      <div className="library-card-header">
        <div className="library-card-title">
          <span className={`library-source-badge library-source-${item.sourceType.toLowerCase()}`}>
            {item.sourceType === "PAPER" ? "论文" : item.sourceType === "WEB" ? "网页" : item.sourceType}
          </span>
          <a href={item.url} target="_blank" rel="noopener noreferrer" className="library-title-link">
            {item.metadata.title || "无标题"}
          </a>
        </div>
        <button
          className={`library-favorite-btn ${item.favorited ? "favorited" : ""}`}
          onClick={() => handleToggleFavorite(item.id)}
          aria-label={item.favorited ? "取消收藏" : "收藏"}
        >
          {item.favorited ? "★" : "☆"}
        </button>
      </div>
      <div className="library-card-meta">
        {item.metadata.authors && item.metadata.authors.length > 0 && (
          <span className="library-meta-item">{item.metadata.authors.slice(0, 3).join(", ")}</span>
        )}
        {item.metadata.publishDate && (
          <span className="library-meta-item">{new Date(item.metadata.publishDate).toLocaleDateString("zh-CN")}</span>
        )}
        <span className="library-meta-item library-score">相关度: {(item.score * 100).toFixed(0)}%</span>
        {item.metadata.citationCount && item.metadata.citationCount > 0 && (
          <span className="library-meta-item">引用: {item.metadata.citationCount}</span>
        )}
      </div>
      <div className="library-card-content">
        {item.metadata.abstract || item.content.slice(0, 300)}...
      </div>
    </div>
  );

  const renderTrendsTab = () => {
    return (
      <AnalyticsCharts
        trends={trends}
        keywords={keywords}
        isLoading={isAnalyticsLoading}
      />
    );
  };

  const renderKeywordsTab = () => {
    if (!keywords || isAnalyticsLoading) {
      return (
        <div className="analytics-loading">
          <div className="analytics-loading-spinner" />
          <span>加载关键词分析...</span>
        </div>
      );
    }

    return (
      <div className="analytics-keywords-detail">
        <div className="analytics-keyword-cloud-section">
          <h3>词云</h3>
          <div className="analytics-keyword-cloud">
            {keywords.topKeywords.slice(0, 50).map((kw, idx) => {
              const maxCount = keywords.topKeywords[0]?.count || 1;
              const minSize = 14;
              const maxSize = 32;
              const size = minSize + (kw.count / maxCount) * (maxSize - minSize);
              const opacity = 0.5 + (kw.count / maxCount) * 0.5;

              return (
                <span
                  key={kw.word}
                  className="analytics-keyword-cloud-tag"
                  style={{
                    fontSize: `${size}px`,
                    opacity,
                  }}
                >
                  {kw.word}
                  <small>({kw.count})</small>
                </span>
              );
            })}
          </div>
        </div>

        <div className="analytics-phrases-section">
          <h3>常见短语</h3>
          <div className="analytics-phrases-list">
            {keywords.topPhrases.slice(0, 20).map((phrase, idx) => (
              <div key={phrase.phrase} className="analytics-phrase-item">
                <span className="analytics-phrase-rank">{idx + 1}</span>
                <span className="analytics-phrase-text">{phrase.phrase}</span>
                <span className="analytics-phrase-count">{phrase.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="library-page">
      <div className="library-header">
        <h1 className="library-title">文献库</h1>
        <div className="library-header-actions">
          <button className="library-btn library-btn-secondary" onClick={handleExportRis}>
            导出 RIS
          </button>
          {onClose && (
            <button className="library-close-btn" onClick={onClose} aria-label="关闭">
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="library-tabs">
        <button
          className={`library-tab ${activeTab === "list" ? "active" : ""}`}
          onClick={() => setActiveTab("list")}
        >
          文献列表
        </button>
        <button
          className={`library-tab ${activeTab === "trends" ? "active" : ""}`}
          onClick={() => setActiveTab("trends")}
        >
          趋势分析
        </button>
        <button
          className={`library-tab ${activeTab === "keywords" ? "active" : ""}`}
          onClick={() => setActiveTab("keywords")}
        >
          关键词分析
        </button>
      </div>

      <div className="library-content">
        {activeTab === "list" && (
          <>
            {renderFilters()}
            {isLoading ? (
              <div className="library-loading">加载中...</div>
            ) : items.length === 0 ? (
              <div className="library-empty">暂无文献</div>
            ) : (
              <>
                <div className="library-list">{items.map(renderItemCard)}</div>
                {renderPagination()}
              </>
            )}
          </>
        )}
        {activeTab === "trends" && renderTrendsTab()}
        {activeTab === "keywords" && renderKeywordsTab()}
      </div>
    </div>
  );
}

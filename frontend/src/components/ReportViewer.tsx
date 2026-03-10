import { memo, useMemo } from "react";

interface ReportViewerProps {
  markdown: string;
  downloading: boolean;
  expanded: boolean;
  closed: boolean;
  onDownload: () => void;
  onExport?: () => void;
  onToggleExpand: () => void;
  onToggleClose: () => void;
}

/**
 * ReportViewer component - displays final research report with expand/collapse controls.
 *
 * Performance optimization:
 * - Wrapped in React.memo to prevent unnecessary re-renders when parent re-renders
 * - Uses useMemo for line/char count calculations (avoids re-splitting on every render)
 */
function ReportViewerBase(props: ReportViewerProps) {
  const { markdown, downloading, expanded, closed, onDownload, onExport, onToggleExpand, onToggleClose } = props;

  // Memoize line/char count calculations to avoid re-splitting on every render
  // Only recalculate when markdown content actually changes
  const { lineCount, charCount } = useMemo(() => ({
    lineCount: markdown.split("\n").length,
    charCount: markdown.length,
  }), [markdown]);

  return (
    <div className="report-viewer">
      <div className="report-viewer-head">
        <div className="report-viewer-title">
          <strong>当前报告</strong>
          <span className="report-meta">{lineCount} 行 · {charCount} 字</span>
        </div>
        <div className="report-viewer-actions">
          <button
            className="ghost"
            type="button"
            onClick={onToggleExpand}
            aria-label={expanded ? "恢复默认宽度" : "全宽展示报告"}
            aria-pressed={expanded}
          >
            {expanded ? "恢复宽度" : "全宽展示"}
          </button>
          <button
            className="ghost"
            type="button"
            onClick={onToggleClose}
            aria-label={closed ? "打开报告预览" : "关闭报告预览"}
            aria-pressed={closed}
          >
            {closed ? "打开预览" : "关闭预览"}
          </button>
          <button
            className="ghost"
            type="button"
            onClick={onDownload}
            disabled={downloading}
            aria-label={downloading ? "下载中..." : "下载 Markdown 报告"}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }}>
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            {downloading ? "下载中..." : "下载"}
          </button>
          {onExport && (
            <button
              className="primary"
              type="button"
              onClick={onExport}
              aria-label="导出文章和引用列表"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{ display: 'inline-block', verticalAlign: 'middle', marginRight: '4px' }}>
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
              </svg>
              导出
            </button>
          )}
        </div>
      </div>
      {closed ? (
        <div className="report-viewer-closed">
          已关闭报告预览，可点击"打开预览"恢复。
        </div>
      ) : (
        <pre
          className="report-content"
          role="region"
          aria-label="报告内容"
          tabIndex={0}
        >
          {markdown}
        </pre>
      )}
    </div>
  );
}

// Wrap with React.memo for performance optimization
// This prevents re-renders when parent component re-renders but props haven't changed
export const ReportViewer = memo(ReportViewerBase);

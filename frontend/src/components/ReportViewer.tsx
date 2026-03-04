interface ReportViewerProps {
  markdown: string;
  downloading: boolean;
  expanded: boolean;
  closed: boolean;
  onDownload: () => void;
  onToggleExpand: () => void;
  onToggleClose: () => void;
}

export function ReportViewer(props: ReportViewerProps) {
  const { markdown, downloading, expanded, closed, onDownload, onToggleExpand, onToggleClose } = props;

  // Get line count for display
  const lineCount = markdown.split("\n").length;
  const charCount = markdown.length;

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
            {downloading ? "下载中..." : "下载 Markdown"}
          </button>
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

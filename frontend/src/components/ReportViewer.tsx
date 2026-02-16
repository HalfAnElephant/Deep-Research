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
  return (
    <div className="report-viewer">
      <div className="report-viewer-head">
        <strong>当前报告（可继续修改）</strong>
        <div className="report-viewer-actions">
          <button className="ghost" onClick={onToggleExpand}>
            {expanded ? "恢复宽度" : "全宽展示"}
          </button>
          <button className="ghost" onClick={onToggleClose}>
            {closed ? "打开预览" : "关闭预览"}
          </button>
          <button className="ghost" onClick={onDownload} disabled={downloading}>
            {downloading ? "下载中..." : "下载 Markdown"}
          </button>
        </div>
      </div>
      {closed ? <div className="report-viewer-closed">已关闭报告预览，可点击“打开预览”恢复。</div> : <pre>{markdown}</pre>}
    </div>
  );
}

interface ReportViewerProps {
  markdown: string;
  downloading: boolean;
  onDownload: () => void;
}

export function ReportViewer(props: ReportViewerProps) {
  const { markdown, downloading, onDownload } = props;
  return (
    <div className="report-viewer">
      <div className="report-viewer-head">
        <strong>最终报告</strong>
        <button className="ghost" onClick={onDownload} disabled={downloading}>
          {downloading ? "下载中..." : "下载 Markdown"}
        </button>
      </div>
      <pre>{markdown}</pre>
    </div>
  );
}

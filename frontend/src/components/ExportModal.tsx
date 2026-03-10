import { useState } from "react";
import { exportArticle, exportReferences } from "../api";

interface ExportModalProps {
  conversationId: string;
  onClose: () => void;
}

export function ExportModal(props: ExportModalProps) {
  const { conversationId, onClose } = props;
  const [exporting, setExporting] = useState<"article" | "references" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExportArticle = async () => {
    setExporting("article");
    setError(null);
    try {
      await exportArticle(conversationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出文章失败");
    } finally {
      setExporting(null);
    }
  };

  const handleExportReferences = async () => {
    setExporting("references");
    setError(null);
    try {
      await exportReferences(conversationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出引用列表失败");
    } finally {
      setExporting(null);
    }
  };

  const handleExportAll = async () => {
    setExporting("article");
    setError(null);
    try {
      await exportArticle(conversationId);
      setExporting("references");
      await exportReferences(conversationId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出失败");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content export-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>导出文章</h2>
          <button className="modal-close" onClick={onClose} aria-label="关闭">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="modal-body">
          <p className="export-description">
            选择要导出的内容。文章文件包含纯正文内容，引用列表包含所有文献的评分和详细说明。
          </p>

          {error && (
            <div className="export-error">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <div className="export-options">
            <div className="export-option">
              <div className="option-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                </svg>
              </div>
              <div className="option-info">
                <h3>文章文件</h3>
                <p>纯正文内容，引用标注在文中，参考文献列表在文末</p>
              </div>
              <button
                className="option-button"
                onClick={handleExportArticle}
                disabled={exporting !== null}
              >
                {exporting === "article" ? (
                  <span className="loading-spinner small" />
                ) : (
                  "下载"
                )}
              </button>
            </div>

            <div className="export-option">
              <div className="option-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                  <line x1="12" y1="6" x2="12" y2="12" />
                  <line x1="9" y1="9" x2="15" y2="9" />
                </svg>
              </div>
              <div className="option-info">
                <h3>引用列表</h3>
                <p>所有文献的详细信息，包含评分、来源和相关说明</p>
              </div>
              <button
                className="option-button"
                onClick={handleExportReferences}
                disabled={exporting !== null}
              >
                {exporting === "references" ? (
                  <span className="loading-spinner small" />
                ) : (
                  "下载"
                )}
              </button>
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button className="button ghost" onClick={onClose}>
            关闭
          </button>
          <button
            className="button primary"
            onClick={handleExportAll}
            disabled={exporting !== null}
          >
            {exporting ? (
              <>
                <span className="loading-spinner small" />
                导出中...
              </>
            ) : (
              "导出全部"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
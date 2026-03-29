import { useCallback, useEffect, useState } from "react";
import { getLLMSettings } from "../api";
import type { LLMOption, LLMProvider, LLMSettingsResponse } from "../types";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  selectedProvider: LLMProvider | null;
  onSelectProvider: (provider: LLMProvider) => void;
}

export function SettingsModal({
  open,
  onClose,
  selectedProvider,
  onSelectProvider,
}: SettingsModalProps) {
  const [settings, setSettings] = useState<LLMSettingsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError("");
    getLLMSettings()
      .then(setSettings)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [open]);

  const handleSelect = useCallback(
    (option: LLMOption) => {
      if (!option.configured) return;
      onSelectProvider(option.provider);
    },
    [onSelectProvider]
  );

  if (!open) return null;

  return (
    <div className="settings-modal-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal-header">
          <h2>设置</h2>
          <button className="settings-close-btn" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="settings-modal-body">
          <section className="settings-section">
            <h3>LLM 提供商</h3>
            <p className="settings-section-desc">选择用于生成研究方案的 AI 模型</p>

            {loading && <div className="settings-loading">加载中...</div>}
            {error && <div className="settings-error">{error}</div>}

            {settings && (
              <div className="llm-options">
                {settings.options.map((option) => (
                  <button
                    key={option.provider}
                    className={`llm-option ${selectedProvider === option.provider ? "selected" : ""} ${!option.configured ? "disabled" : ""}`}
                    onClick={() => handleSelect(option)}
                    disabled={!option.configured}
                  >
                    <div className="llm-option-header">
                      <span className="llm-option-label">{option.label}</span>
                      {selectedProvider === option.provider && (
                        <span className="llm-option-check">✓</span>
                      )}
                    </div>
                    <div className="llm-option-model">{option.model}</div>
                    {!option.configured && (
                      <div className="llm-option-unconfigured">未配置 API Key</div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="settings-modal-footer">
          <button className="settings-btn-primary" onClick={onClose}>
            完成
          </button>
        </div>
      </div>
    </div>
  );
}
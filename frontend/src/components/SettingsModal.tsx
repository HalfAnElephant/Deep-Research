import { useCallback, useEffect, useState } from "react";
import {
  getProviderConfigs,
  getTaskMapping,
  updateProviderConfig,
  updateTaskMapping,
} from "../api";
import type {
  LLMProvider,
  ProviderConfigResponse,
  TaskMappingResponse,
} from "../types";

type SettingsTab = "providers" | "tasks";

const PROVIDER_LABELS: Record<LLMProvider, string> = {
  openrouter: "OpenRouter",
  deepseek: "DeepSeek",
  openai: "OpenAI",
};

const TASK_LABELS: Record<keyof TaskMappingResponse, string> = {
  draft: "生成草稿",
  chat: "对话",
  article: "生成文章",
};

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
  const [activeTab, setActiveTab] = useState<SettingsTab>("providers");
  const [providers, setProviders] = useState<ProviderConfigResponse[]>([]);
  const [taskMapping, setTaskMapping] = useState<TaskMappingResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editingProvider, setEditingProvider] = useState<LLMProvider | null>(null);
  const [editForm, setEditForm] = useState({
    apiKey: "",
    baseUrl: "",
    model: "",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError("");
    Promise.all([getProviderConfigs(), getTaskMapping()])
      .then(([providersData, mappingData]) => {
        setProviders(providersData);
        setTaskMapping(mappingData);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [open]);

  const handleStartEdit = useCallback((provider: LLMProvider) => {
    const config = providers.find((p) => p.provider === provider);
    if (!config) return;
    setEditingProvider(provider);
    setEditForm({
      apiKey: "",
      baseUrl: config.baseUrl,
      model: config.model,
    });
  }, [providers]);

  const handleCancelEdit = useCallback(() => {
    setEditingProvider(null);
    setEditForm({ apiKey: "", baseUrl: "", model: "" });
  }, []);

  const handleSaveProvider = useCallback(async () => {
    if (!editingProvider) return;
    setSaving(true);
    try {
      const update: Record<string, string | boolean> = {};
      if (editForm.apiKey) update.apiKey = editForm.apiKey;
      if (editForm.baseUrl) update.baseUrl = editForm.baseUrl;
      if (editForm.model) update.model = editForm.model;

      await updateProviderConfig(editingProvider, update);
      const updatedProviders = await getProviderConfigs();
      setProviders(updatedProviders);
      setEditingProvider(null);
      setEditForm({ apiKey: "", baseUrl: "", model: "" });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [editingProvider, editForm]);

  const handleSetDefault = useCallback(async (provider: LLMProvider) => {
    setSaving(true);
    try {
      await updateProviderConfig(provider, { isDefault: true });
      const updatedProviders = await getProviderConfigs();
      setProviders(updatedProviders);
      onSelectProvider(provider);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [onSelectProvider]);

  const handleTaskMappingChange = useCallback(async (
    task: keyof TaskMappingResponse,
    provider: LLMProvider
  ) => {
    if (!taskMapping) return;
    setSaving(true);
    try {
      const updated = await updateTaskMapping({ [task]: provider });
      setTaskMapping(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }, [taskMapping]);

  if (!open) return null;

  return (
    <div className="settings-modal-overlay" onClick={onClose}>
      <div className="settings-modal settings-modal--wide" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal-header">
          <h2>API 配置</h2>
          <button className="settings-close-btn" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="settings-tabs">
          <button
            className={`settings-tab ${activeTab === "providers" ? "active" : ""}`}
            onClick={() => setActiveTab("providers")}
          >
            提供商配置
          </button>
          <button
            className={`settings-tab ${activeTab === "tasks" ? "active" : ""}`}
            onClick={() => setActiveTab("tasks")}
          >
            任务类型映射
          </button>
        </div>

        <div className="settings-modal-body">
          {loading && <div className="settings-loading">加载中...</div>}
          {error && <div className="settings-error">{error}</div>}

          {activeTab === "providers" && !loading && (
            <div className="provider-cards">
              {providers.map((config) => (
                <div
                  key={config.provider}
                  className={`provider-card ${config.isDefault ? "default" : ""} ${config.configured ? "configured" : "unconfigured"}`}
                >
                  <div className="provider-card-header">
                    <div className="provider-info">
                      <span className="provider-name">{config.label}</span>
                      {config.isDefault && <span className="provider-badge">默认</span>}
                    </div>
                    <span className={`provider-status ${config.configured ? "ok" : "warn"}`}>
                      {config.configured ? "已配置" : "未配置"}
                    </span>
                  </div>

                  {editingProvider === config.provider ? (
                    <div className="provider-edit-form">
                      <div className="form-field">
                        <label>API Key</label>
                        <input
                          type="password"
                          placeholder={config.apiKey || "输入新的 API Key"}
                          value={editForm.apiKey}
                          onChange={(e) => setEditForm({ ...editForm, apiKey: e.target.value })}
                        />
                      </div>
                      <div className="form-field">
                        <label>Base URL</label>
                        <input
                          type="text"
                          value={editForm.baseUrl}
                          onChange={(e) => setEditForm({ ...editForm, baseUrl: e.target.value })}
                        />
                      </div>
                      <div className="form-field">
                        <label>Model</label>
                        <input
                          type="text"
                          value={editForm.model}
                          onChange={(e) => setEditForm({ ...editForm, model: e.target.value })}
                        />
                      </div>
                      <div className="form-actions">
                        <button
                          className="btn-cancel"
                          onClick={handleCancelEdit}
                          disabled={saving}
                        >
                          取消
                        </button>
                        <button
                          className="btn-save"
                          onClick={handleSaveProvider}
                          disabled={saving}
                        >
                          {saving ? "保存中..." : "保存"}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="provider-details">
                        <div className="detail-row">
                          <span className="detail-label">API Key</span>
                          <span className="detail-value masked">{config.apiKey || "未设置"}</span>
                        </div>
                        <div className="detail-row">
                          <span className="detail-label">Model</span>
                          <span className="detail-value code">{config.model}</span>
                        </div>
                      </div>
                      <div className="provider-actions">
                        <button
                          className="btn-edit"
                          onClick={() => handleStartEdit(config.provider)}
                        >
                          编辑
                        </button>
                        {!config.isDefault && config.configured && (
                          <button
                            className="btn-set-default"
                            onClick={() => handleSetDefault(config.provider)}
                            disabled={saving}
                          >
                            设为默认
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}

          {activeTab === "tasks" && !loading && taskMapping && (
            <div className="task-mapping-section">
              <p className="section-desc">
                为不同类型的任务配置不同的 LLM 提供商，优化成本和性能。
              </p>
              <div className="task-mapping-list">
                {(Object.keys(TASK_LABELS) as Array<keyof TaskMappingResponse>).map((task) => (
                  <div key={task} className="task-mapping-item">
                    <div className="task-info">
                      <span className="task-name">{TASK_LABELS[task]}</span>
                      <span className="task-desc">
                        {task === "draft" && "生成研究计划和初始草稿"}
                        {task === "chat" && "用户对话和交互"}
                        {task === "article" && "最终文章生成和润色"}
                      </span>
                    </div>
                    <select
                      value={taskMapping[task]}
                      onChange={(e) => handleTaskMappingChange(task, e.target.value as LLMProvider)}
                      disabled={saving}
                      className="task-provider-select"
                    >
                      {providers.map((p) => (
                        <option key={p.provider} value={p.provider} disabled={!p.configured}>
                          {p.label} {!p.configured && "(未配置)"}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            </div>
          )}
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
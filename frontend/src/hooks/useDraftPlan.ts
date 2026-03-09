import { useState, useCallback } from "react";

/**
 * Custom hook for managing draft plan state.
 * Handles plan draft content, version tracking, dirty state, and editor mode.
 */
export function useDraftPlan() {
  const [planDraft, setPlanDraft] = useState("");
  const [planVersion, setPlanVersion] = useState(0);
  const [draftDirty, setDraftDirty] = useState(false);
  const [editorMode, setEditorMode] = useState<"edit" | "preview">("edit");

  /**
   * Update plan draft content and mark as dirty.
   */
  const updatePlanDraft = useCallback((value: string) => {
    setPlanDraft(value);
    setDraftDirty(true);
  }, []);

  /**
   * Apply a plan from a message (for opening in drawer).
   */
  const applyPlan = useCallback((markdown: string) => {
    setPlanDraft(markdown);
    setDraftDirty(true);
    setEditorMode("edit");
  }, []);

  /**
   * Sync plan from server response.
   * Only updates if not dirty or if version changed.
   */
  const syncPlanFromServer = useCallback(
    (markdown: string, version: number, forceSync: boolean = false) => {
      const shouldSync = forceSync || !draftDirty || version !== planVersion;
      if (shouldSync) {
        setPlanDraft(markdown);
        setPlanVersion(version);
        setDraftDirty(false);
      }
    },
    [draftDirty, planVersion]
  );

  /**
   * Mark the plan as saved (not dirty).
   */
  const markAsSaved = useCallback(() => {
    setDraftDirty(false);
  }, []);

  /**
   * Reset all draft plan state.
   */
  const resetDraftPlan = useCallback(() => {
    setPlanDraft("");
    setPlanVersion(0);
    setDraftDirty(false);
    setEditorMode("edit");
  }, []);

  return {
    // State
    planDraft,
    planVersion,
    draftDirty,
    editorMode,

    // Actions
    setPlanDraft,
    setPlanVersion,
    setDraftDirty,
    setEditorMode,
    updatePlanDraft,
    applyPlan,
    syncPlanFromServer,
    markAsSaved,
    resetDraftPlan,
  };
}
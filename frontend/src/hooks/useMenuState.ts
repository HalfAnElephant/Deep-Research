import { useState, useCallback } from "react";

/**
 * Custom hook for managing menu state in ConversationSidebar.
 * Handles global menu and item menu open/close state with proper coordination.
 */
export function useMenuState() {
  const [globalMenuOpen, setGlobalMenuOpen] = useState(false);
  const [activeItemMenuId, setActiveItemMenuId] = useState<string | null>(null);

  /**
   * Toggle global menu and close any open item menu.
   */
  const toggleGlobalMenu = useCallback(() => {
    setActiveItemMenuId(null);
    setGlobalMenuOpen((open) => !open);
  }, []);

  /**
   * Close global menu.
   */
  const closeGlobalMenu = useCallback(() => {
    setGlobalMenuOpen(false);
  }, []);

  /**
   * Toggle item menu for a specific conversation.
   * Opens the menu if it's closed, closes if it's open.
   * Also closes the global menu when opening an item menu.
   */
  const toggleItemMenu = useCallback((conversationId: string) => {
    setGlobalMenuOpen(false);
    setActiveItemMenuId((current) =>
      current === conversationId ? null : conversationId
    );
  }, []);

  /**
   * Close the currently open item menu.
   */
  const closeItemMenu = useCallback(() => {
    setActiveItemMenuId(null);
  }, []);

  /**
   * Close all menus (both global and item menus).
   */
  const closeAllMenus = useCallback(() => {
    setGlobalMenuOpen(false);
    setActiveItemMenuId(null);
  }, []);

  /**
   * Check if a specific item menu is open.
   */
  const isItemMenuOpen = useCallback(
    (conversationId: string) => activeItemMenuId === conversationId,
    [activeItemMenuId]
  );

  return {
    // State
    globalMenuOpen,
    activeItemMenuId,

    // Actions
    toggleGlobalMenu,
    closeGlobalMenu,
    toggleItemMenu,
    closeItemMenu,
    closeAllMenus,
    isItemMenuOpen,

    // Setters for direct control if needed
    setGlobalMenuOpen,
    setActiveItemMenuId,
  };
}
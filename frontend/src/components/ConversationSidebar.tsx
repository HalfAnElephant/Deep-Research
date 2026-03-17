import { useCallback, useEffect, useRef, useState } from "react";
import type { ConversationStatus, ConversationSummary } from "../types";
import { STATUS_LABEL, STATUS_DESCRIPTION } from "../constants";
import { useMenuState } from "../hooks";
import { formatLocalTime } from "../utils/formatTime";

/**
 * 根据会话主题生成合适的emoji
 * 使用简单的关键词匹配来选择emoji
 */
function getTopicEmoji(topic: string): string {
  const lowerTopic = topic.toLowerCase();

  // 科学研究相关
  if (lowerTopic.includes('ai') || lowerTopic.includes('人工智能') || lowerTopic.includes('机器学习') || lowerTopic.includes('深度学习')) return '🤖';
  if (lowerTopic.includes('医学') || lowerTopic.includes('医学') || lowerTopic.includes('健康') || lowerTopic.includes('医疗')) return '🏥';
  if (lowerTopic.includes('生物') || lowerTopic.includes('基因') || lowerTopic.includes('细胞')) return '🧬';
  if (lowerTopic.includes('化学') || lowerTopic.includes('分子') || lowerTopic.includes('药物')) return '⚗️';
  if (lowerTopic.includes('物理') || lowerTopic.includes('量子') || lowerTopic.includes('粒子')) return '⚛️';
  if (lowerTopic.includes('天文') || lowerTopic.includes('宇宙') || lowerTopic.includes('星球')) return '🌌';
  if (lowerTopic.includes('数学') || lowerTopic.includes('算法') || lowerTopic.includes('计算')) return '🔢';
  if (lowerTopic.includes('数据') || lowerTopic.includes('统计') || lowerTopic.includes('分析')) return '📊';
  if (lowerTopic.includes('环境') || lowerTopic.includes('气候') || lowerTopic.includes('生态')) return '🌿';
  if (lowerTopic.includes('能源') || lowerTopic.includes('电力') || lowerTopic.includes('可持续')) return '⚡';
  if (lowerTopic.includes('材料') || lowerTopic.includes('纳米') || lowerTopic.includes('合成')) return '🔬';
  if (lowerTopic.includes('心理') || lowerTopic.includes('认知') || lowerTopic.includes('神经')) return '🧠';
  if (lowerTopic.includes('经济') || lowerTopic.includes('金融') || lowerTopic.includes('市场')) return '💹';
  if (lowerTopic.includes('社会') || lowerTopic.includes('人口') || lowerTopic.includes('文化')) return '👥';
  if (lowerTopic.includes('教育') || lowerTopic.includes('学习') || lowerTopic.includes('教学')) return '📚';
  if (lowerTopic.includes('法律') || lowerTopic.includes('政策') || lowerTopic.includes('法规')) return '⚖️';
  if (lowerTopic.includes('历史') || lowerTopic.includes('考古') || lowerTopic.includes('文明')) return '🏛️';
  if (lowerTopic.includes('语言') || lowerTopic.includes('文字') || lowerTopic.includes('翻译')) return '💬';
  if (lowerTopic.includes('艺术') || lowerTopic.includes('设计') || lowerTopic.includes('创意')) return '🎨';
  if (lowerTopic.includes('音乐') || lowerTopic.includes('声音') || lowerTopic.includes('音频')) return '🎵';
  if (lowerTopic.includes('体育') || lowerTopic.includes('运动') || lowerTopic.includes('健身')) return '🏃';
  if (lowerTopic.includes('食品') || lowerTopic.includes('营养') || lowerTopic.includes('农业')) return '🌾';
  if (lowerTopic.includes('交通') || lowerTopic.includes('汽车') || lowerTopic.includes('航空')) return '🚀';
  if (lowerTopic.includes('建筑') || lowerTopic.includes('城市') || lowerTopic.includes('规划')) return '🏗️';
  if (lowerTopic.includes('网络') || lowerTopic.includes('安全') || lowerTopic.includes('隐私')) return '🔐';
  if (lowerTopic.includes('游戏') || lowerTopic.includes('娱乐') || lowerTopic.includes('媒体')) return '🎮';

  // 默认返回研究相关的emoji
  return '🔬';
}

// 键盘导航相关类型
type FocusArea = "list" | "globalMenu" | "itemMenu";

interface KeyboardNavigationState {
  focusedConversationIndex: number;
  focusedMenuIndex: number;
  currentFocusArea: FocusArea;
}

interface ConversationSidebarProps {
  summaries: ConversationSummary[];
  activeConversationId: string | null;
  creatingDraft: boolean;
  showMobileClose: boolean;
  refreshing: boolean;
  deletingConversationId: string | null;
  renamingConversationId: string | null;
  deletingAll: boolean;
  onCreateDraft: () => void;
  onRequestCloseMobile: () => void;
  onSelect: (conversationId: string) => void;
  onDelete: (conversationId: string) => void;
  onRename: (conversationId: string) => void;
  onDeleteAll: () => void;
}

export function ConversationSidebar(props: ConversationSidebarProps) {
  const {
    summaries,
    activeConversationId,
    creatingDraft,
    showMobileClose,
    refreshing,
    deletingConversationId,
    renamingConversationId,
    deletingAll,
    onCreateDraft,
    onRequestCloseMobile,
    onSelect,
    onDelete,
    onRename,
    onDeleteAll
  } = props;

  const {
    globalMenuOpen,
    activeItemMenuId,
    toggleGlobalMenu,
    closeGlobalMenu,
    toggleItemMenu,
    closeItemMenu,
    closeAllMenus,
    isItemMenuOpen
  } = useMenuState();

  // ============ 键盘导航状态 ============
  const [navState, setNavState] = useState<KeyboardNavigationState>({
    focusedConversationIndex: -1,
    focusedMenuIndex: 0,
    currentFocusArea: "list"
  });

  // Refs 用于焦点管理
  const sidebarRef = useRef<HTMLElement>(null);
  const globalMenuTriggerRef = useRef<HTMLButtonElement>(null);
  const globalMenuRef = useRef<HTMLDivElement>(null);
  const itemMenuTriggerRef = useRef<HTMLButtonElement>(null);
  const itemMenuRef = useRef<HTMLDivElement>(null);
  const conversationItemRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const liveRegionRef = useRef<HTMLDivElement>(null);

  // 公告消息状态
  const [announcement, setAnnouncement] = useState<string>("");

  // ============ 辅助函数 ============

  // 公告状态变化（用于屏幕阅读器）
  const announce = useCallback((message: string) => {
    setAnnouncement(message);
    // 短暂延迟后清空，允许重复公告相同消息
    setTimeout(() => setAnnouncement(""), 1000);
  }, []);

  // 获取当前聚焦的会话 ID
  const getFocusedConversationId = useCallback(() => {
    if (navState.focusedConversationIndex >= 0 && navState.focusedConversationIndex < summaries.length) {
      return summaries[navState.focusedConversationIndex].conversationId;
    }
    return null;
  }, [navState.focusedConversationIndex, summaries]);

  // 获取菜单项数量
  const getMenuItemCount = useCallback((isGlobal: boolean) => {
    if (isGlobal) {
      // 全局菜单只有一个"全部删除"项
      return 1;
    }
    // 会话菜单有"重命名"和"删除"两项
    return 2;
  }, []);

  // ============ 焦点管理 ============

  // 聚焦会话列表项
  const focusConversationItem = useCallback((index: number) => {
    if (index >= 0 && index < summaries.length) {
      const conversationId = summaries[index].conversationId;
      const buttonEl = conversationItemRefs.current.get(conversationId);
      if (buttonEl) {
        buttonEl.focus();
      }
    }
  }, [summaries]);

  // 聚焦菜单项
  const focusMenuItem = useCallback((menuRef: React.RefObject<HTMLDivElement | null>, index: number) => {
    if (menuRef.current) {
      const menuItems = menuRef.current.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])');
      if (index >= 0 && index < menuItems.length) {
        menuItems[index].focus();
      }
    }
  }, []);

  // 恢复焦点到触发元素
  const restoreFocusToTrigger = useCallback((isGlobal: boolean) => {
    if (isGlobal && globalMenuTriggerRef.current) {
      globalMenuTriggerRef.current.focus();
    } else if (!isGlobal && itemMenuTriggerRef.current) {
      itemMenuTriggerRef.current.focus();
    }
  }, []);

  // ============ 键盘事件处理 ============

  // 处理会话列表键盘导航
  const handleListKeyDown = useCallback((event: React.KeyboardEvent) => {
    const { key } = event;

    switch (key) {
      case "ArrowDown":
        event.preventDefault();
        setNavState(prev => {
          const newIndex = prev.focusedConversationIndex < summaries.length - 1
            ? prev.focusedConversationIndex + 1
            : 0;
          focusConversationItem(newIndex);
          return { ...prev, focusedConversationIndex: newIndex };
        });
        break;

      case "ArrowUp":
        event.preventDefault();
        setNavState(prev => {
          const newIndex = prev.focusedConversationIndex > 0
            ? prev.focusedConversationIndex - 1
            : summaries.length - 1;
          focusConversationItem(newIndex);
          return { ...prev, focusedConversationIndex: newIndex };
        });
        break;

      case "Enter":
      case " ": // Space 键
        event.preventDefault();
        if (navState.focusedConversationIndex >= 0) {
          const conversationId = summaries[navState.focusedConversationIndex]?.conversationId;
          if (conversationId) {
            closeAllMenus();
            onSelect(conversationId);
            announce(`已打开会话：${summaries[navState.focusedConversationIndex].topic}`);
          }
        }
        break;

      case "Delete":
      case "Backspace":
        event.preventDefault();
        if (navState.focusedConversationIndex >= 0) {
          const conversationId = summaries[navState.focusedConversationIndex]?.conversationId;
          if (conversationId) {
            closeAllMenus();
            onDelete(conversationId);
            announce(`正在删除会话：${summaries[navState.focusedConversationIndex].topic}`);
          }
        }
        break;

      case "F2":
        event.preventDefault();
        if (navState.focusedConversationIndex >= 0) {
          const conversationId = summaries[navState.focusedConversationIndex]?.conversationId;
          if (conversationId) {
            closeAllMenus();
            onRename(conversationId);
            announce(`正在重命名会话：${summaries[navState.focusedConversationIndex].topic}`);
          }
        }
        break;

      case "Home":
        event.preventDefault();
        setNavState(prev => ({ ...prev, focusedConversationIndex: 0 }));
        focusConversationItem(0);
        break;

      case "End":
        event.preventDefault();
        const lastIndex = summaries.length - 1;
        setNavState(prev => ({ ...prev, focusedConversationIndex: lastIndex }));
        focusConversationItem(lastIndex);
        break;
    }
  }, [summaries, navState.focusedConversationIndex, focusConversationItem, closeAllMenus, onSelect, onDelete, onRename, announce]);

  // 处理菜单键盘导航
  const handleMenuKeyDown = useCallback((
    event: React.KeyboardEvent,
    isGlobal: boolean
  ) => {
    const { key } = event;
    const menuRef = isGlobal ? globalMenuRef : itemMenuRef;
    const itemCount = getMenuItemCount(isGlobal);

    switch (key) {
      case "ArrowDown":
        event.preventDefault();
        setNavState(prev => {
          const newIndex = prev.focusedMenuIndex < itemCount - 1
            ? prev.focusedMenuIndex + 1
            : 0;
          focusMenuItem(menuRef, newIndex);
          return { ...prev, focusedMenuIndex: newIndex };
        });
        break;

      case "ArrowUp":
        event.preventDefault();
        setNavState(prev => {
          const newIndex = prev.focusedMenuIndex > 0
            ? prev.focusedMenuIndex - 1
            : itemCount - 1;
          focusMenuItem(menuRef, newIndex);
          return { ...prev, focusedMenuIndex: newIndex };
        });
        break;

      case "Enter":
      case " ":
        // 让 onClick 处理，这里只阻止默认行为
        break;

      case "Escape":
        event.preventDefault();
        if (isGlobal) {
          closeGlobalMenu();
        } else {
          closeItemMenu();
        }
        restoreFocusToTrigger(isGlobal);
        announce("菜单已关闭");
        break;

      case "Tab":
        // Tab 键关闭菜单并移动焦点
        if (isGlobal) {
          closeGlobalMenu();
        } else {
          closeItemMenu();
        }
        // 不阻止默认行为，允许 Tab 自然移动
        break;
    }
  }, [getMenuItemCount, focusMenuItem, closeGlobalMenu, closeItemMenu, restoreFocusToTrigger, announce]);

  // ============ 菜单打开时的焦点管理 ============

  // 全局菜单打开时聚焦第一个菜单项
  useEffect(() => {
    if (globalMenuOpen && globalMenuRef.current) {
      setNavState(prev => ({
        ...prev,
        currentFocusArea: "globalMenu",
        focusedMenuIndex: 0
      }));
      // 使用 setTimeout 确保 DOM 已渲染
      setTimeout(() => {
        focusMenuItem(globalMenuRef, 0);
      }, 0);
      announce("全局菜单已打开");
    }
  }, [globalMenuOpen, focusMenuItem, announce]);

  // 会话菜单打开时聚焦第一个菜单项
  useEffect(() => {
    if (activeItemMenuId && itemMenuRef.current) {
      setNavState(prev => ({
        ...prev,
        currentFocusArea: "itemMenu",
        focusedMenuIndex: 0
      }));
      // 使用 setTimeout 确保 DOM 已渲染
      setTimeout(() => {
        focusMenuItem(itemMenuRef, 0);
      }, 0);
      const conversation = summaries.find(s => s.conversationId === activeItemMenuId);
      if (conversation) {
        announce(`会话"${conversation.topic}"的菜单已打开`);
      }
    }
  }, [activeItemMenuId, focusMenuItem, summaries, announce]);

  // 初始化聚焦到当前活动会话或第一个会话
  useEffect(() => {
    if (summaries.length > 0 && navState.focusedConversationIndex === -1) {
      let initialIndex = 0;
      if (activeConversationId) {
        const activeIndex = summaries.findIndex(s => s.conversationId === activeConversationId);
        if (activeIndex >= 0) {
          initialIndex = activeIndex;
        }
      }
      setNavState(prev => ({ ...prev, focusedConversationIndex: initialIndex }));
    }
  }, [summaries, activeConversationId, navState.focusedConversationIndex]);

  // ============ 回调函数包装 ============

  // 打开全局菜单（保存触发元素引用）
  const handleToggleGlobalMenu = useCallback(() => {
    toggleGlobalMenu();
  }, [toggleGlobalMenu]);

  // 打开会话菜单（保存触发元素引用）
  const handleToggleItemMenu = useCallback((conversationId: string, triggerElement: HTMLButtonElement) => {
    itemMenuTriggerRef.current = triggerElement;
    toggleItemMenu(conversationId);
  }, [toggleItemMenu]);

  return (
    <aside
      ref={sidebarRef}
      className="sidebar"
      aria-label="会话列表"
    >
      {/* 屏幕阅读器公告区域 */}
      <div
        ref={liveRegionRef}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
        style={{
          position: "absolute",
          width: "1px",
          height: "1px",
          padding: 0,
          margin: "-1px",
          overflow: "hidden",
          clip: "rect(0, 0, 0, 0)",
          whiteSpace: "nowrap",
          border: 0
        }}
      >
        {announcement}
      </div>

      <div className="sidebar-head">
        <div className="sidebar-head-main">
          <h2>Deep Research</h2>
          <p>多会话研究空间</p>
        </div>
        {showMobileClose && (
          <button
            className="ghost pane-close mobile-only"
            type="button"
            onClick={onRequestCloseMobile}
            aria-label="关闭会话列表"
          >
            关闭
          </button>
        )}
      </div>

      <div className="sidebar-toolbar">
        <button
          className="primary"
          type="button"
          onClick={() => {
            closeAllMenus();
            onCreateDraft();
          }}
          aria-label={creatingDraft ? "等待首条输入" : "新建研究"}
        >
          {creatingDraft ? "等待首条输入" : "新建研究"}
        </button>
        <div className="menu-wrap">
          <button
            ref={globalMenuTriggerRef}
            className={`icon-button icon-button-small ${globalMenuOpen ? "active" : ""}`}
            type="button"
            onClick={handleToggleGlobalMenu}
            onKeyDown={(e) => {
              // Enter 或 Space 打开菜单时聚焦第一项
              if ((e.key === "Enter" || e.key === " ") && !globalMenuOpen) {
                // 菜单打开后会通过 useEffect 自动聚焦
              }
              if (globalMenuOpen) {
                handleMenuKeyDown(e, true);
              }
            }}
            title="更多操作"
            aria-label="打开更多会话操作"
            aria-haspopup="menu"
            aria-expanded={globalMenuOpen}
            aria-controls="sidebar-global-menu"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
              <circle cx="3" cy="8" r="1.5" />
              <circle cx="8" cy="8" r="1.5" />
              <circle cx="13" cy="8" r="1.5" />
            </svg>
          </button>
          {globalMenuOpen && (
            <div
              ref={globalMenuRef}
              className="menu-popover"
              id="sidebar-global-menu"
              role="menu"
              aria-label="更多会话操作"
              onKeyDown={(e) => handleMenuKeyDown(e, true)}
            >
              <button
                className="menu-item danger"
                type="button"
                role="menuitem"
                tabIndex={-1}
                onClick={() => {
                  closeGlobalMenu();
                  restoreFocusToTrigger(true);
                  onDeleteAll();
                }}
                disabled={deletingAll || summaries.length === 0}
                aria-label={deletingAll ? "删除中..." : summaries.length === 0 ? "没有会话可删除" : `删除全部 ${summaries.length} 个会话`}
              >
                {deletingAll ? "删除中..." : "全部删除"}
              </button>
            </div>
          )}
        </div>
      </div>

      <nav className="sidebar-list" aria-label="会话列表">
        <div className="sidebar-list-head">
          <span>会话列表</span>
          <span className="mono" aria-live="polite" aria-atomic="true">
            {refreshing ? "刷新中" : `${summaries.length} 个`}
          </span>
        </div>
        <ul
          className="sidebar-list-body"
          role="listbox"
          aria-label="会话列表"
          aria-activedescendant={navState.focusedConversationIndex >= 0 ? `conversation-item-${summaries[navState.focusedConversationIndex]?.conversationId}` : undefined}
          onKeyDown={handleListKeyDown}
        >
          {summaries.length === 0 ? (
            <li className="empty-item" role="status">
              暂无会话，点击"新建研究"开始。
            </li>
          ) : (
            summaries.map((conversation, index) => {
              const isMenuOpen = isItemMenuOpen(conversation.conversationId);
              const deleting = deletingConversationId === conversation.conversationId;
              const renaming = renamingConversationId === conversation.conversationId;
              const isActive = activeConversationId === conversation.conversationId;
              const isFocused = navState.focusedConversationIndex === index;

              return (
                <li
                  key={conversation.conversationId}
                  id={`conversation-item-${conversation.conversationId}`}
                  className={`conversation-item ${isActive ? "active" : ""}`}
                  role="option"
                  aria-selected={isActive}
                >
                  <button
                    ref={(el) => {
                      if (el) {
                        conversationItemRefs.current.set(conversation.conversationId, el);
                      } else {
                        conversationItemRefs.current.delete(conversation.conversationId);
                      }
                    }}
                    className="conversation-select"
                    type="button"
                    tabIndex={isFocused ? 0 : -1}
                    onClick={() => {
                      closeAllMenus();
                      setNavState(prev => ({ ...prev, focusedConversationIndex: index }));
                      onSelect(conversation.conversationId);
                    }}
                    onFocus={() => {
                      setNavState(prev => ({ ...prev, focusedConversationIndex: index }));
                    }}
                    aria-current={isActive ? "true" : undefined}
                    aria-describedby={`status-${conversation.conversationId}`}
                  >
                    <span className="conversation-emoji" aria-hidden="true">
                      {getTopicEmoji(conversation.topic)}
                    </span>
                    <div className="conversation-content">
                      <div className="conversation-topic">{conversation.topic}</div>
                      <div className="conversation-meta">
                        <span
                          id={`status-${conversation.conversationId}`}
                          className={`status-chip ${conversation.status.toLowerCase()}`}
                          aria-label={STATUS_DESCRIPTION[conversation.status]}
                        >
                          {STATUS_LABEL[conversation.status]}
                        </span>
                        <time className="mono" dateTime={conversation.updatedAt}>
                          {formatLocalTime(conversation.updatedAt)}
                        </time>
                      </div>
                    </div>
                  </button>

                  <div className="menu-wrap item-menu-wrap">
                    <button
                      ref={(el) => {
                        if (isMenuOpen && el) {
                          itemMenuTriggerRef.current = el;
                        }
                      }}
                      className={`icon-button icon-button-small ${isMenuOpen ? "active" : ""}`}
                      type="button"
                      onClick={(e) => {
                        handleToggleItemMenu(conversation.conversationId, e.currentTarget);
                      }}
                      onKeyDown={(e) => {
                        if (isMenuOpen) {
                          handleMenuKeyDown(e, false);
                        }
                      }}
                      title="会话操作"
                      aria-label={`打开会话"${conversation.topic}"操作`}
                      aria-haspopup="menu"
                      aria-expanded={isMenuOpen}
                      aria-controls={`conversation-menu-${conversation.conversationId}`}
                    >
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                        <circle cx="3" cy="8" r="1.5" />
                        <circle cx="8" cy="8" r="1.5" />
                        <circle cx="13" cy="8" r="1.5" />
                      </svg>
                    </button>
                    {isMenuOpen && (
                      <div
                        ref={itemMenuRef}
                        className="menu-popover item-menu"
                        id={`conversation-menu-${conversation.conversationId}`}
                        role="menu"
                        aria-label={`会话"${conversation.topic}"操作`}
                        onKeyDown={(e) => handleMenuKeyDown(e, false)}
                      >
                        <button
                          className="menu-item"
                          type="button"
                          role="menuitem"
                          tabIndex={-1}
                          onClick={() => {
                            closeItemMenu();
                            restoreFocusToTrigger(false);
                            onRename(conversation.conversationId);
                          }}
                          disabled={renaming || deleting}
                          aria-busy={renaming}
                        >
                          {renaming ? "重命名中..." : "重命名"}
                        </button>
                        <button
                          className="menu-item danger"
                          type="button"
                          role="menuitem"
                          tabIndex={-1}
                          onClick={() => {
                            closeItemMenu();
                            restoreFocusToTrigger(false);
                            onDelete(conversation.conversationId);
                          }}
                          disabled={deleting || renaming}
                          aria-busy={deleting}
                        >
                          {deleting ? "删除中..." : "删除"}
                        </button>
                      </div>
                    )}
                  </div>
                </li>
              );
            })
          )}
        </ul>
      </nav>
    </aside>
  );
}
/**
 * SessionSidebar - Displays grouped chat sessions with search
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Trash2, Pencil, MoreHorizontal, Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";
import { useChatStore } from "../../stores/chatStore";
import { SESSION_GROUP_LABELS, type SessionGroup } from "../../lib/chatApi";

interface SessionSidebarProps {
  onSelectSession: (sessionId: string) => void;
}

export function SessionSidebar({ onSelectSession }: SessionSidebarProps) {
  const {
    groupedSessions,
    sessionsLoading,
    sessionsError,
    currentSessionId,
    searchQuery,
    setSearchQuery,
    searchSessions,
    renameSession,
    deleteSession,
    hasMore,
    loadMoreSessions,
  } = useChatStore();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  // Filter groups that have sessions
  const activeGroups = useMemo(() => {
    return (Object.keys(groupedSessions) as SessionGroup[]).filter(
      (group) => groupedSessions[group].length > 0
    );
  }, [groupedSessions]);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);
    // Debounce search
    const timer = setTimeout(() => {
      searchSessions(query);
    }, 300);
    return () => clearTimeout(timer);
  };

  const handleStartEdit = (sessionId: string, currentTitle: string | null) => {
    setEditingId(sessionId);
    setEditingTitle(currentTitle || "");
    setMenuOpenId(null);
  };

  const handleSaveEdit = async (sessionId: string) => {
    if (editingTitle.trim()) {
      await renameSession(sessionId, editingTitle.trim());
    }
    setEditingId(null);
    setEditingTitle("");
  };

  const handleDelete = async (sessionId: string) => {
    setMenuOpenId(null);
    await deleteSession(sessionId);
  };

  useEffect(() => {
    if (editingId) {
      editInputRef.current?.focus();
    }
  }, [editingId]);

  if (sessionsError) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <p className="text-sm text-destructive">{sessionsError}</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Search */}
      <div className="p-2">
        <input
          type="text"
          placeholder="Search conversations..."
          value={searchQuery}
          onChange={handleSearch}
          className="w-full px-3 py-2 text-sm bg-muted rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-brand/50"
        />
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto">
        {sessionsLoading && activeGroups.length === 0 ? (
          <div className="flex items-center justify-center p-4">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        ) : activeGroups.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center">
            <p className="text-sm text-muted-foreground">No conversations yet</p>
            <p className="text-xs text-muted-foreground mt-1">
              Press Cmd+N to start a new chat
            </p>
          </div>
        ) : (
          <div className="space-y-4 p-2">
            {activeGroups.map((group) => (
              <div key={group}>
                <h3 className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {SESSION_GROUP_LABELS[group]}
                </h3>
                <div className="space-y-0.5">
                  {groupedSessions[group].map((session) => (
                    <div
                      key={session.id}
                      className={cn(
                        "group relative rounded-lg transition-colors",
                        currentSessionId === session.id
                          ? "bg-muted"
                          : "hover:bg-muted/50"
                      )}
                    >
                      {editingId === session.id ? (
                        <input
                          ref={editInputRef}
                          type="text"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onBlur={() => handleSaveEdit(session.id)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleSaveEdit(session.id);
                            if (e.key === "Escape") setEditingId(null);
                          }}
                          className="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-brand/50"
                        />
                      ) : (
                        <button
                          type="button"
                          onClick={() => onSelectSession(session.id)}
                          className="w-full text-left px-3 py-2 flex items-center gap-2"
                        >
                          <span className="flex-1 truncate text-sm">
                            {session.title || "New conversation"}
                          </span>
                          {session.message_count > 0 && (
                            <span className="text-xs text-muted-foreground">
                              {session.message_count}
                            </span>
                          )}
                        </button>
                      )}

                      {/* Actions Menu */}
                      {editingId !== session.id && (
                        <div className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <div className="relative">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setMenuOpenId(
                                  menuOpenId === session.id ? null : session.id
                                );
                              }}
                              className="p-1.5 hover:bg-muted rounded-md"
                            >
                              <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                            </button>

                            {menuOpenId === session.id && (
                              <div className="absolute right-0 top-full mt-1 bg-popover border border-border rounded-lg shadow-lg py-1 z-10 min-w-32">
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleStartEdit(session.id, session.title);
                                  }}
                                  className="w-full px-3 py-1.5 text-left text-sm hover:bg-muted flex items-center gap-2"
                                >
                                  <Pencil className="w-3.5 h-3.5" />
                                  Rename
                                </button>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDelete(session.id);
                                  }}
                                  className="w-full px-3 py-1.5 text-left text-sm hover:bg-muted flex items-center gap-2 text-destructive"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                  Delete
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {/* Load More */}
            {hasMore && (
              <button
                type="button"
                onClick={loadMoreSessions}
                disabled={sessionsLoading}
                className="w-full py-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                {sessionsLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin mx-auto" />
                ) : (
                  "Load more"
                )}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

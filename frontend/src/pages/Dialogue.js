import { useState, useEffect, useCallback } from "react";
import { MessageSquare, Search, Hash } from "lucide-react";
import { getThreads, getMessages, AGENT_META } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import AgentAvatar from "@/components/AgentAvatar";
import MessageBubble from "@/components/MessageBubble";

const THREAD_TYPE_ICON = {
  direct: MessageSquare,
  department: Hash,
  cross_functional: Hash,
  escalation: MessageSquare,
  review: MessageSquare,
};

export default function Dialogue() {
  const [threads, setThreads] = useState([]);
  const [activeThread, setActiveThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [search, setSearch] = useState("");

  const loadThreads = useCallback(async () => {
    try {
      const t = await getThreads();
      setThreads(t);
      if (t.length > 0 && !activeThread) {
        setActiveThread(t[0]);
      }
    } catch (e) {
      console.error(e);
    }
  }, [activeThread]);

  const loadMessages = useCallback(async () => {
    if (!activeThread) return;
    try {
      const msgs = await getMessages({ thread_id: activeThread.thread_id });
      setMessages(msgs);
    } catch (e) {
      console.error(e);
    }
  }, [activeThread]);

  useEffect(() => {
    loadThreads();
    const iv = setInterval(loadThreads, 5000);
    return () => clearInterval(iv);
  }, [loadThreads]);

  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  const filtered = threads.filter((t) => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      t.last_message?.toLowerCase().includes(s) ||
      t.participants?.some((p) => p.toLowerCase().includes(s))
    );
  });

  return (
    <div className="h-full flex flex-col bg-[#0A0A0A]" data-testid="dialogue-page">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#222222] shrink-0">
        <h2 className="font-['Chivo'] text-base font-bold tracking-tight text-white" data-testid="dialogue-title">
          Agent Dialogue
        </h2>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Thread List */}
        <div className="w-[320px] border-r border-[#222222] flex flex-col shrink-0" data-testid="thread-list-panel">
          {/* Search */}
          <div className="p-3 border-b border-[#222222]">
            <div className="flex items-center gap-2 bg-[#141414] border border-[#222222] rounded-sm px-3 py-2">
              <Search className="w-3.5 h-3.5 text-zinc-500" />
              <input
                type="text"
                placeholder="Search threads..."
                className="bg-transparent text-sm text-white placeholder:text-zinc-600 outline-none flex-1"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                data-testid="thread-search-input"
              />
            </div>
          </div>

          <ScrollArea className="flex-1">
            <div className="py-1">
              {filtered.length === 0 ? (
                <p className="text-xs text-zinc-600 text-center py-8">No threads found</p>
              ) : (
                filtered.map((thread) => {
                  const Icon = THREAD_TYPE_ICON[thread.thread_type] || MessageSquare;
                  const isActive = activeThread?.thread_id === thread.thread_id;
                  return (
                    <div
                      key={thread.thread_id}
                      className={`px-3 py-2.5 cursor-pointer transition-colors border-l-2 ${
                        isActive
                          ? "bg-[#1A1A1A] border-l-[#0030FF]"
                          : "border-l-transparent hover:bg-[#141414]"
                      }`}
                      onClick={() => setActiveThread(thread)}
                      data-testid={`thread-${thread.thread_id}`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <Icon className="w-3 h-3 text-zinc-500" />
                        <div className="flex items-center gap-1 flex-1 min-w-0">
                          {thread.participants?.slice(0, 3).map((p) => (
                            <span
                              key={p}
                              className="font-mono text-[9px] uppercase"
                              style={{ color: AGENT_META[p]?.color || "#A1A1AA" }}
                            >
                              {AGENT_META[p]?.name?.slice(0, 3) || p}
                            </span>
                          ))}
                          {(thread.participants?.length || 0) > 3 && (
                            <span className="text-[9px] text-zinc-600">
                              +{thread.participants.length - 3}
                            </span>
                          )}
                        </div>
                        <span className="font-mono text-[9px] text-zinc-600">
                          {thread.message_count}
                        </span>
                      </div>
                      <p className="text-[11px] text-zinc-400 truncate">
                        {thread.last_message?.slice(0, 80)}
                      </p>
                    </div>
                  );
                })
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Message View */}
        <div className="flex-1 flex flex-col" data-testid="message-view-panel">
          {activeThread ? (
            <>
              <div className="panel-header shrink-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                    {activeThread.thread_type}
                  </span>
                  <span className="text-[10px] text-zinc-600">|</span>
                  <div className="flex items-center gap-1">
                    {activeThread.participants?.map((p) => (
                      <AgentAvatar key={p} role={p} size="sm" />
                    ))}
                  </div>
                </div>
              </div>
              <ScrollArea className="flex-1 p-4">
                <div className="space-y-1">
                  {messages.map((msg, i) => (
                    <MessageBubble key={msg.id} message={msg} index={i} />
                  ))}
                </div>
              </ScrollArea>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-xs text-zinc-600">Select a thread to view messages</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

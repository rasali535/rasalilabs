import { useState, useEffect, useCallback, useRef } from "react";
import { MessageCircle, X, Send, ChevronDown } from "lucide-react";
import { AGENT_META, BACKEND_URL } from "@/lib/api";
import AgentAvatar from "@/components/AgentAvatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import axios from "axios";

export default function ChatDrawer() {
  const [open, setOpen] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState("ceo");
  const [message, setMessage] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAgentPicker, setShowAgentPicker] = useState(false);
  const scrollRef = useRef(null);

  const loadHistory = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/chat/history`);
      setChatMessages(res.data.reverse());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    if (open) loadHistory();
  }, [open, loadHistory]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatMessages]);

  const handleSend = async () => {
    if (!message.trim() || loading) return;
    const userMsg = message.trim();
    setMessage("");
    setLoading(true);

    // Optimistically add user message
    const tempUserMsg = {
      id: `temp-${Date.now()}`,
      from_agent: "user",
      to_agent: selectedAgent,
      content: userMsg,
      created_at: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await axios.post(`${BACKEND_URL}/api/chat`, {
        to_agent: selectedAgent,
        content: userMsg,
      });
      // Replace temp message and add agent response
      setChatMessages((prev) => [
        ...prev.filter((m) => m.id !== tempUserMsg.id),
        res.data.user_message,
        res.data.agent_response,
      ]);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const meta = AGENT_META[selectedAgent] || {};

  return (
    <>
      {/* Floating Chat Button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-20 right-6 z-50 w-12 h-12 rounded-sm bg-[#0030FF] hover:bg-[#0025CC] text-white flex items-center justify-center transition-all active:scale-95 shadow-lg shadow-[#0030FF]/20"
          data-testid="chat-toggle-btn"
        >
          <MessageCircle className="w-5 h-5" />
        </button>
      )}

      {/* Chat Panel */}
      {open && (
        <div
          className="fixed bottom-20 right-6 z-50 w-[380px] h-[520px] bg-[#0A0A0A] border border-[#222222] rounded-sm flex flex-col shadow-2xl"
          data-testid="chat-drawer"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-[#222222] shrink-0">
            <div className="flex items-center gap-2">
              <MessageCircle className="w-4 h-4 text-[#0030FF]" />
              <span className="font-['Chivo'] text-sm font-bold text-white">
                Agent Chat
              </span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-zinc-500 hover:text-white transition-colors"
              data-testid="chat-close-btn"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Agent Selector */}
          <div className="px-3 py-2 border-b border-[#222222] shrink-0">
            <div className="relative">
              <button
                onClick={() => setShowAgentPicker(!showAgentPicker)}
                className="w-full flex items-center justify-between px-2.5 py-1.5 bg-[#141414] border border-[#222222] rounded-sm hover:border-[#333] transition-colors"
                data-testid="agent-picker-btn"
              >
                <div className="flex items-center gap-2">
                  <AgentAvatar role={selectedAgent} size="sm" />
                  <span className="text-xs font-medium text-white">{meta.name}</span>
                  <span
                    className="font-mono text-[9px] uppercase tracking-wider"
                    style={{ color: meta.color }}
                  >
                    {meta.title}
                  </span>
                </div>
                <ChevronDown className="w-3 h-3 text-zinc-500" />
              </button>

              {showAgentPicker && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-[#141414] border border-[#222222] rounded-sm z-10 py-1 max-h-[200px] overflow-y-auto">
                  {Object.entries(AGENT_META).map(([role, agentMeta]) => (
                    <button
                      key={role}
                      onClick={() => {
                        setSelectedAgent(role);
                        setShowAgentPicker(false);
                      }}
                      className={`w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-[#1A1A1A] transition-colors ${
                        role === selectedAgent ? "bg-[#1A1A1A]" : ""
                      }`}
                      data-testid={`agent-pick-${role}`}
                    >
                      <AgentAvatar role={role} size="sm" />
                      <span className="text-xs text-white">{agentMeta.name}</span>
                      <span
                        className="font-mono text-[9px] uppercase tracking-wider ml-auto"
                        style={{ color: agentMeta.color }}
                      >
                        {agentMeta.title}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3" ref={scrollRef}>
            {chatMessages.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <p className="text-[11px] text-zinc-600 text-center">
                  Send a message to any agent.<br />
                  They&apos;ll respond based on their role.
                </p>
              </div>
            ) : (
              chatMessages.map((msg) => {
                const isUser = msg.from_agent === "user";
                const agentRole = isUser ? msg.to_agent : msg.from_agent;
                const agentColor = AGENT_META[agentRole]?.color || "#A1A1AA";
                return (
                  <div
                    key={msg.id}
                    className={`flex flex-col gap-1 ${isUser ? "items-end" : "items-start"}`}
                    data-testid={`chat-msg-${msg.id}`}
                  >
                    <span className="font-mono text-[9px] uppercase tracking-wider text-zinc-600">
                      {isUser ? "You" : AGENT_META[agentRole]?.name || agentRole}
                    </span>
                    <div
                      className={`max-w-[85%] px-3 py-2 rounded-sm text-[12px] leading-relaxed ${
                        isUser
                          ? "bg-[#0030FF]/20 border border-[#0030FF]/30 text-white"
                          : "bg-[#1A1A1A] border-l-2 text-zinc-300"
                      }`}
                      style={!isUser ? { borderLeftColor: agentColor } : {}}
                    >
                      {msg.content}
                    </div>
                  </div>
                );
              })
            )}
            {loading && (
              <div className="flex items-start gap-2">
                <span className="font-mono text-[10px] text-zinc-600 typing-indicator">
                  {AGENT_META[selectedAgent]?.name} is typing...
                </span>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="px-3 py-2.5 border-t border-[#222222] shrink-0">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                placeholder={`Message ${meta.name}...`}
                className="flex-1 bg-[#141414] border border-[#222222] focus:border-[#0030FF] focus:ring-1 focus:ring-[#0030FF] rounded-sm text-white px-3 py-2 text-xs outline-none"
                data-testid="chat-input"
              />
              <button
                onClick={handleSend}
                disabled={loading || !message.trim()}
                className="btn-primary p-2 flex items-center justify-center disabled:opacity-50"
                data-testid="chat-send-btn"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

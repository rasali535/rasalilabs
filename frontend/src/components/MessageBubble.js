import AgentAvatar from "@/components/AgentAvatar";
import { AGENT_META } from "@/lib/api";

export default function MessageBubble({ message, index = 0 }) {
  const meta = AGENT_META[message.from_agent] || { name: message.from_agent, color: "#A1A1AA", title: message.from_agent };
  const time = new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div
      className={`flex flex-col gap-1 w-full pb-3 animate-fade-in`}
      style={{ animationDelay: `${index * 0.05}s` }}
      data-testid={`message-${message.id}`}
    >
      <div className="flex items-center gap-2">
        <AgentAvatar role={message.from_agent} size="sm" />
        <span
          className="font-mono text-[11px] px-1.5 py-0.5 rounded-sm"
          style={{
            backgroundColor: `${meta.color}12`,
            border: `1px solid ${meta.color}30`,
            color: meta.color,
          }}
          data-testid={`message-agent-tag-${message.from_agent}`}
        >
          {meta.name}
        </span>
        {message.to_agent && (
          <span className="font-mono text-[10px] text-zinc-600">
            &rarr; {AGENT_META[message.to_agent]?.name || message.to_agent}
          </span>
        )}
        <span className="font-mono text-[10px] text-zinc-600 ml-auto">{time}</span>
      </div>
      <div
        className="text-[13px] leading-relaxed text-zinc-300 bg-[#1A1A1A]/50 p-3 rounded-sm border-l-2 ml-8"
        style={{ borderLeftColor: meta.color }}
      >
        {message.content}
      </div>
    </div>
  );
}

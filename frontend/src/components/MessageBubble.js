import AgentAvatar from "@/components/AgentAvatar";
import { AGENT_META } from "@/lib/api";

const MODEL_BADGE = {
  simulation: { label: "SIM", color: "#FFD700", bg: "rgba(255,215,0,0.08)", border: "rgba(255,215,0,0.2)" },
};

function getModelBadge(model) {
  if (!model || model === "simulation") return MODEL_BADGE.simulation;
  if (model.includes("qwen") || model.includes("coder") || model.includes("deepseek"))
    return { label: model.split(":")[0], color: "#38BDF8", bg: "rgba(56,189,248,0.08)", border: "rgba(56,189,248,0.2)" };
  return { label: model.split(":")[0], color: "#22C55E", bg: "rgba(34,197,94,0.08)", border: "rgba(34,197,94,0.2)" };
}

export default function MessageBubble({ message, index = 0 }) {
  const meta = AGENT_META[message.from_agent] || { name: message.from_agent, color: "#A1A1AA", title: message.from_agent };
  const time = new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const badge = message.model_used ? getModelBadge(message.model_used) : null;

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
        {badge && (
          <span
            className="font-mono text-[8px] uppercase tracking-wider px-1 py-0.5 rounded-sm"
            style={{ backgroundColor: badge.bg, border: `1px solid ${badge.border}`, color: badge.color }}
            data-testid={`model-badge-${message.id}`}
          >
            {badge.label}
          </span>
        )}
        {message.to_agent && message.to_agent !== "user" && (
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

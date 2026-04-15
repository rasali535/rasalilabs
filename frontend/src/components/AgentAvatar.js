import { AGENT_META } from "@/lib/api";

export default function AgentAvatar({ role, size = "sm", showName = false }) {
  const meta = AGENT_META[role] || { name: role, title: role.toUpperCase(), color: "#A1A1AA" };
  const sizeClass = size === "lg" ? "w-8 h-8 text-[11px]" : "w-6 h-6 text-[9px]";

  return (
    <div className="flex items-center gap-2" data-testid={`agent-avatar-${role}`}>
      <div
        className={`${sizeClass} rounded-sm flex items-center justify-center font-mono font-medium tracking-wider shrink-0`}
        style={{
          backgroundColor: `${meta.color}15`,
          border: `1px solid ${meta.color}40`,
          color: meta.color,
        }}
      >
        {meta.title.slice(0, 2).toUpperCase()}
      </div>
      {showName && (
        <div className="flex flex-col">
          <span className="text-xs font-medium text-white leading-tight">{meta.name}</span>
          <span className="font-mono text-[10px] uppercase tracking-wider" style={{ color: meta.color }}>
            {meta.title}
          </span>
        </div>
      )}
    </div>
  );
}

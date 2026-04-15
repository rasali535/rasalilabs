import { AGENT_META } from "@/lib/api";
import AgentAvatar from "@/components/AgentAvatar";

const STATUS_STYLES = {
  pending: { bg: "bg-yellow-500/10", text: "text-yellow-400", border: "border-yellow-500/30", label: "PENDING" },
  in_progress: { bg: "bg-blue-500/10", text: "text-blue-400", border: "border-blue-500/30", label: "IN PROGRESS" },
  in_review: { bg: "bg-purple-500/10", text: "text-purple-400", border: "border-purple-500/30", label: "IN REVIEW" },
  completed: { bg: "bg-green-500/10", text: "text-green-400", border: "border-green-500/30", label: "COMPLETED" },
  approved: { bg: "bg-green-500/10", text: "text-green-400", border: "border-green-500/30", label: "APPROVED" },
  rejected: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/30", label: "REJECTED" },
  blocked: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/30", label: "BLOCKED" },
};

const PRIORITY_STYLES = {
  high: "text-red-400",
  medium: "text-yellow-400",
  low: "text-zinc-500",
};

export default function TaskCard({ task, onClick }) {
  const status = STATUS_STYLES[task.status] || STATUS_STYLES.pending;
  const agent = AGENT_META[task.assigned_to] || null;

  return (
    <div
      className="bg-[#111111] border border-[#222222] hover:border-[#333333] transition-colors p-3 rounded-sm flex flex-col gap-2 cursor-pointer"
      onClick={() => onClick?.(task)}
      data-testid={`task-card-${task.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-[13px] font-medium text-white leading-tight flex-1">
          {task.title}
        </h4>
        <span
          className={`font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ${status.bg} ${status.text} ${status.border} shrink-0`}
        >
          {status.label}
        </span>
      </div>

      {task.description && (
        <p className="text-[12px] text-zinc-500 leading-relaxed line-clamp-2">
          {task.description}
        </p>
      )}

      <div className="flex items-center justify-between mt-1">
        <div className="flex items-center gap-2">
          {agent && <AgentAvatar role={task.assigned_to} size="sm" />}
          {agent && (
            <span className="font-mono text-[10px] uppercase tracking-wider" style={{ color: agent.color }}>
              {agent.name}
            </span>
          )}
        </div>
        <span className={`font-mono text-[9px] uppercase tracking-wider ${PRIORITY_STYLES[task.priority] || ""}`}>
          {task.priority}
        </span>
      </div>
    </div>
  );
}

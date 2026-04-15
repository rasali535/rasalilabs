import { useState, useEffect, useCallback } from "react";
import { CheckCircle, XCircle, Clock, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { getDecisions, voteDecision, AGENT_META } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import AgentAvatar from "@/components/AgentAvatar";

const STATUS_CONFIG = {
  approved: { icon: CheckCircle, color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/30" },
  rejected: { icon: XCircle, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/30" },
  pending: { icon: Clock, color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/30" },
  needs_revision: { icon: AlertTriangle, color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/30" },
  blocked: { icon: XCircle, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/30" },
  delegated: { icon: CheckCircle, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/30" },
};

export default function Approvals() {
  const [decisions, setDecisions] = useState([]);
  const [filter, setFilter] = useState("all");

  const loadDecisions = useCallback(async () => {
    try {
      const params = {};
      if (filter !== "all") params.status = filter;
      const d = await getDecisions(params);
      setDecisions(d);
    } catch (e) {
      console.error(e);
    }
  }, [filter]);

  useEffect(() => {
    loadDecisions();
    const iv = setInterval(loadDecisions, 5000);
    return () => clearInterval(iv);
  }, [loadDecisions]);

  const handleVote = async (decisionId, agentRole, vote) => {
    try {
      await voteDecision(decisionId, { agent_role: agentRole, vote });
      toast.success(`${AGENT_META[agentRole]?.name || agentRole} voted: ${vote}`);
      loadDecisions();
    } catch (e) {
      toast.error("Vote failed");
    }
  };

  const pendingCount = decisions.filter((d) => d.status === "pending").length;

  return (
    <div className="h-full flex flex-col bg-[#0A0A0A]" data-testid="approvals-page">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#222222] flex items-center justify-between shrink-0">
        <div>
          <h2 className="font-['Chivo'] text-base font-bold tracking-tight text-white" data-testid="approvals-title">
            Approvals Queue
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
            {pendingCount} pending
          </span>
        </div>
        <div className="flex items-center gap-1">
          {["all", "pending", "approved", "rejected"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`font-mono text-[10px] uppercase tracking-wider px-3 py-1.5 rounded-sm transition-colors ${
                filter === f
                  ? "bg-[#1A1A1A] text-white"
                  : "text-zinc-500 hover:text-zinc-300 hover:bg-[#141414]"
              }`}
              data-testid={`filter-${f}-btn`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-3">
          {decisions.length === 0 ? (
            <div className="text-center py-12">
              <Clock className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
              <p className="text-sm text-zinc-500">No decisions to review</p>
            </div>
          ) : (
            decisions.map((dec) => {
              const cfg = STATUS_CONFIG[dec.status] || STATUS_CONFIG.pending;
              const StatusIcon = cfg.icon;
              return (
                <div
                  key={dec.id}
                  className="bg-[#111111] border border-[#222222] rounded-sm p-4"
                  data-testid={`approval-card-${dec.id}`}
                >
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-white mb-1">{dec.title}</h3>
                      {dec.description && (
                        <p className="text-[12px] text-zinc-500">{dec.description}</p>
                      )}
                    </div>
                    <span
                      className={`font-mono text-[9px] uppercase tracking-wider px-2 py-1 rounded-sm border flex items-center gap-1 shrink-0 ${cfg.color} ${cfg.bg} ${cfg.border}`}
                    >
                      <StatusIcon className="w-3 h-3" />
                      {dec.status}
                    </span>
                  </div>

                  {/* Votes */}
                  <div className="mb-3">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500 block mb-2">
                      Votes
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(dec.votes || {}).map(([role, vote]) => (
                        <div
                          key={role}
                          className="flex items-center gap-1.5 px-2 py-1 bg-[#1A1A1A] border border-[#222222] rounded-sm"
                          data-testid={`vote-${role}`}
                        >
                          <AgentAvatar role={role} size="sm" />
                          <span
                            className={`font-mono text-[9px] uppercase ${
                              vote === "approved"
                                ? "text-green-400"
                                : vote === "rejected"
                                ? "text-red-400"
                                : "text-yellow-400"
                            }`}
                          >
                            {vote}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Quick vote actions for pending */}
                  {dec.status === "pending" && (
                    <div className="flex items-center gap-2 pt-2 border-t border-[#222222]">
                      <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500 mr-2">
                        Quick vote as CEO:
                      </span>
                      <button
                        className="text-[11px] px-2.5 py-1 bg-green-500/10 border border-green-500/30 text-green-400 rounded-sm hover:bg-green-500/20 transition-colors"
                        onClick={() => handleVote(dec.id, "ceo", "approved")}
                        data-testid={`approve-btn-${dec.id}`}
                      >
                        Approve
                      </button>
                      <button
                        className="text-[11px] px-2.5 py-1 bg-red-500/10 border border-red-500/30 text-red-400 rounded-sm hover:bg-red-500/20 transition-colors"
                        onClick={() => handleVote(dec.id, "ceo", "rejected")}
                        data-testid={`reject-btn-${dec.id}`}
                      >
                        Reject
                      </button>
                    </div>
                  )}

                  <div className="flex items-center gap-3 mt-2 text-[10px] text-zinc-600 font-mono">
                    <span>Decided by: {AGENT_META[dec.decided_by]?.name || dec.decided_by}</span>
                    <span>{new Date(dec.created_at).toLocaleString()}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </ScrollArea>
    </div>
  );
}

import { useState, useEffect, useCallback } from "react";
import { ListTodo, Filter } from "lucide-react";
import { getTasks, AGENT_META } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import TaskCard from "@/components/TaskCard";
import AgentAvatar from "@/components/AgentAvatar";

const STATUS_ORDER = ["in_progress", "pending", "in_review", "blocked", "completed", "approved", "rejected"];

export default function Delegation() {
  const [tasks, setTasks] = useState([]);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterAgent, setFilterAgent] = useState("all");

  const loadTasks = useCallback(async () => {
    try {
      const params = {};
      if (filterStatus !== "all") params.status = filterStatus;
      if (filterAgent !== "all") params.assigned_to = filterAgent;
      const t = await getTasks(params);
      setTasks(t);
    } catch (e) {
      console.error(e);
    }
  }, [filterStatus, filterAgent]);

  useEffect(() => {
    loadTasks();
    const iv = setInterval(loadTasks, 5000);
    return () => clearInterval(iv);
  }, [loadTasks]);

  const grouped = {};
  for (const role of Object.keys(AGENT_META)) {
    grouped[role] = tasks.filter((t) => t.assigned_to === role);
  }

  const totalByStatus = {};
  for (const t of tasks) {
    totalByStatus[t.status] = (totalByStatus[t.status] || 0) + 1;
  }

  return (
    <div className="h-full flex flex-col bg-[#0A0A0A]" data-testid="delegation-page">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#222222] flex items-center justify-between shrink-0">
        <div>
          <h2 className="font-['Chivo'] text-base font-bold tracking-tight text-white" data-testid="delegation-title">
            Delegation Board
          </h2>
          <div className="flex items-center gap-3 mt-1">
            {STATUS_ORDER.filter((s) => totalByStatus[s]).map((s) => (
              <span key={s} className="font-mono text-[9px] uppercase tracking-wider text-zinc-500">
                {s.replace("_", " ")}: {totalByStatus[s]}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="bg-[#141414] border-[#222222] text-white text-xs h-8 w-[130px]" data-testid="filter-status-select">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent className="bg-[#141414] border-[#222222]">
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="blocked">Blocked</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filterAgent} onValueChange={setFilterAgent}>
            <SelectTrigger className="bg-[#141414] border-[#222222] text-white text-xs h-8 w-[130px]" data-testid="filter-agent-select">
              <SelectValue placeholder="Agent" />
            </SelectTrigger>
            <SelectContent className="bg-[#141414] border-[#222222]">
              <SelectItem value="all">All Agents</SelectItem>
              {Object.entries(AGENT_META).map(([role, meta]) => (
                <SelectItem key={role} value={role}>{meta.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4">
          {/* Kanban-style columns by agent */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(grouped)
              .filter(([_, taskList]) => taskList.length > 0 || filterAgent === "all")
              .filter(([role]) => filterAgent === "all" || role === filterAgent)
              .map(([role, taskList]) => {
                const meta = AGENT_META[role];
                return (
                  <div
                    key={role}
                    className="flex flex-col"
                    data-testid={`delegation-column-${role}`}
                  >
                    <div className="flex items-center gap-2 pb-2 mb-2 border-b border-[#222222]">
                      <AgentAvatar role={role} size="sm" />
                      <span className="text-xs font-medium text-white">{meta?.name}</span>
                      <span
                        className="font-mono text-[9px] uppercase tracking-wider ml-auto"
                        style={{ color: meta?.color }}
                      >
                        {taskList.length}
                      </span>
                    </div>
                    <div className="space-y-2">
                      {taskList.length === 0 ? (
                        <p className="text-[10px] text-zinc-600 text-center py-4">No tasks</p>
                      ) : (
                        taskList.map((task) => <TaskCard key={task.id} task={task} />)
                      )}
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}

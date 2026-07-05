import { useState, useEffect, useCallback } from "react";
import {
  DollarSign,
  TrendingUp,
  PieChart,
  BarChart3,
  ArrowDown,
  ArrowUp,
  Wallet,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AgentAvatar from "@/components/AgentAvatar";
import { AGENT_META, BACKEND_URL } from "@/lib/api";
import axios from "axios";

const DEPT_COLORS = {
  executive: "#FFFFFF",
  finance: "#FFD700",
  people: "#F472B6",
  design: "#A78BFA",
  engineering: "#38BDF8",
  operations: "#22C55E",
};

export default function Budget() {
  const [summary, setSummary] = useState(null);
  const [projects, setProjects] = useState([]);

  const loadData = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([
        axios.get(`${BACKEND_URL}/api/budget/summary`).then((r) => r.data),
        axios.get(`${BACKEND_URL}/api/budget/projects`).then((r) => r.data),
      ]);
      setSummary(s);
      setProjects(p);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    loadData();
    const iv = setInterval(loadData, 10000);
    return () => clearInterval(iv);
  }, [loadData]);

  if (!summary) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0A0A0A]">
        <span className="font-mono text-xs text-zinc-600 typing-indicator">Loading budget data...</span>
      </div>
    );
  }

  const maxDeptCost = Math.max(...Object.values(summary.by_department || {}), 1);
  const maxAgentCost = Math.max(...Object.values(summary.by_agent || {}).map((a) => a.cost), 1);

  return (
    <div className="h-full flex flex-col bg-[#0A0A0A]" data-testid="budget-page">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#222222] shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-[#FFD700]/10 border border-[#FFD700]/30 flex items-center justify-center">
            <DollarSign className="w-4 h-4 text-[#FFD700]" />
          </div>
          <div>
            <h1
              className="font-['Chivo'] text-xl font-bold tracking-tight text-white"
              data-testid="budget-title"
            >
              CFO Dashboard
            </h1>
            <p className="text-xs text-zinc-500 font-mono uppercase tracking-wider">
              Meridian &middot; Budget Tracking & Cost Analysis
            </p>
          </div>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-6">
          {/* Top Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="budget-summary-cards">
            <SummaryCard
              icon={Wallet}
              label="Total Budget"
              value={`$${summary.total_budget.toLocaleString()}`}
              color="#0030FF"
              testId="total-budget-card"
            />
            <SummaryCard
              icon={ArrowDown}
              label="Total Spent"
              value={`$${summary.total_spent.toLocaleString()}`}
              color="#FF2A2A"
              testId="total-spent-card"
            />
            <SummaryCard
              icon={ArrowUp}
              label="Remaining"
              value={`$${summary.remaining.toLocaleString()}`}
              color="#22C55E"
              testId="remaining-card"
            />
            <SummaryCard
              icon={TrendingUp}
              label="Utilization"
              value={`${summary.utilization_pct}%`}
              color="#FFD700"
              testId="utilization-card"
            />
          </div>

          {/* Utilization Bar */}
          <div className="bg-[#111111] border border-[#222222] rounded-sm p-4" data-testid="utilization-bar">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                Budget Utilization
              </span>
              <span className="font-mono text-[10px] text-zinc-400">
                ${summary.total_spent.toLocaleString()} / ${summary.total_budget.toLocaleString()}
              </span>
            </div>
            <Progress
              value={summary.utilization_pct}
              className="h-2 bg-[#1A1A1A]"
            />
          </div>

          {/* Tabs: By Department / By Agent / By Project */}
          <Tabs defaultValue="department" className="space-y-4">
            <TabsList className="bg-transparent border-b border-[#222222] rounded-none px-0 h-auto py-0">
              <TabsTrigger
                value="department"
                className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-4 text-zinc-500"
                data-testid="tab-department"
              >
                <PieChart className="w-3 h-3 mr-1.5" />
                By Department
              </TabsTrigger>
              <TabsTrigger
                value="agent"
                className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-4 text-zinc-500"
                data-testid="tab-agent"
              >
                <BarChart3 className="w-3 h-3 mr-1.5" />
                By Agent
              </TabsTrigger>
              <TabsTrigger
                value="project"
                className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-4 text-zinc-500"
                data-testid="tab-project"
              >
                <DollarSign className="w-3 h-3 mr-1.5" />
                By Project
              </TabsTrigger>
            </TabsList>

            {/* Department Breakdown */}
            <TabsContent value="department" className="m-0">
              <div className="space-y-3" data-testid="department-breakdown">
                {Object.entries(summary.by_department || {})
                  .sort(([, a], [, b]) => b - a)
                  .map(([dept, cost]) => (
                    <div
                      key={dept}
                      className="bg-[#111111] border border-[#222222] rounded-sm p-3"
                      data-testid={`dept-${dept}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: DEPT_COLORS[dept] || "#A1A1AA" }}
                          />
                          <span className="text-xs font-medium text-white capitalize">{dept}</span>
                        </div>
                        <span className="font-mono text-xs text-zinc-400">
                          ${cost.toLocaleString()}
                        </span>
                      </div>
                      <div className="w-full h-1.5 bg-[#1A1A1A] rounded-sm overflow-hidden">
                        <div
                          className="h-full rounded-sm transition-all duration-500"
                          style={{
                            width: `${(cost / maxDeptCost) * 100}%`,
                            backgroundColor: DEPT_COLORS[dept] || "#A1A1AA",
                          }}
                        />
                      </div>
                    </div>
                  ))}
              </div>
            </TabsContent>

            {/* Agent Breakdown */}
            <TabsContent value="agent" className="m-0">
              <div className="space-y-2" data-testid="agent-breakdown">
                {Object.entries(summary.by_agent || {})
                  .sort(([, a], [, b]) => b.cost - a.cost)
                  .map(([role, data]) => {
                    const agentMeta = AGENT_META[role] || {};
                    return (
                      <div
                        key={role}
                        className="bg-[#111111] border border-[#222222] rounded-sm p-3 flex items-center gap-3"
                        data-testid={`agent-budget-${role}`}
                      >
                        <AgentAvatar role={role} size="lg" showName />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="font-mono text-[9px] uppercase tracking-wider text-zinc-500">
                              {data.tasks} tasks
                            </span>
                            <span className="font-mono text-xs text-white font-medium">
                              ${data.cost.toLocaleString()}
                            </span>
                          </div>
                          <div className="w-full h-1.5 bg-[#1A1A1A] rounded-sm overflow-hidden">
                            <div
                              className="h-full rounded-sm transition-all duration-500"
                              style={{
                                width: `${(data.cost / maxAgentCost) * 100}%`,
                                backgroundColor: agentMeta.color || "#A1A1AA",
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </TabsContent>

            {/* Project Breakdown */}
            <TabsContent value="project" className="m-0">
              <div className="space-y-3" data-testid="project-breakdown">
                {projects.length === 0 ? (
                  <p className="text-xs text-zinc-600 text-center py-8">No project budget data</p>
                ) : (
                  projects.map((proj) => (
                    <div
                      key={proj.project_id}
                      className="bg-[#111111] border border-[#222222] rounded-sm p-4"
                      data-testid={`project-budget-${proj.project_id}`}
                    >
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div className="flex-1 min-w-0">
                          <p className="text-[13px] font-medium text-white truncate mb-1">
                            {proj.goal}
                          </p>
                          <div className="flex items-center gap-3">
                            <span
                              className={`font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ${
                                proj.status === "completed"
                                  ? "text-green-400 bg-green-500/10 border-green-500/30"
                                  : "text-blue-400 bg-blue-500/10 border-blue-500/30"
                              }`}
                            >
                              {proj.status}
                            </span>
                            <span className="font-mono text-[9px] text-zinc-500">
                              {proj.task_count} tasks
                            </span>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="font-mono text-sm font-medium text-white">
                            ${proj.spent.toLocaleString()}
                          </p>
                          <p className="font-mono text-[9px] text-zinc-500">
                            of ${proj.budget.toLocaleString()}
                          </p>
                        </div>
                      </div>

                      <div className="w-full h-1.5 bg-[#1A1A1A] rounded-sm overflow-hidden mb-3">
                        <div
                          className="h-full bg-[#0030FF] rounded-sm transition-all duration-500"
                          style={{
                            width: `${proj.budget > 0 ? (proj.spent / proj.budget) * 100 : 0}%`,
                          }}
                        />
                      </div>

                      {/* Agent cost breakdown for this project */}
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(proj.agent_costs || {}).map(([role, agentData]) => (
                          <div
                            key={role}
                            className="flex items-center gap-1.5 px-2 py-1 bg-[#1A1A1A] border border-[#222222] rounded-sm"
                          >
                            <AgentAvatar role={role} size="sm" />
                            <span className="font-mono text-[9px] text-zinc-400">
                              ${agentData.cost.toLocaleString()}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </ScrollArea>
    </div>
  );
}

function SummaryCard({ icon: Icon, label, value, color, testId }) {
  return (
    <div
      className="bg-[#111111] border border-[#222222] rounded-sm p-4"
      data-testid={testId}
    >
      <div className="flex items-center gap-2 mb-2">
        <div
          className="w-6 h-6 rounded-sm flex items-center justify-center"
          style={{ backgroundColor: `${color}15`, border: `1px solid ${color}30` }}
        >
          <Icon className="w-3.5 h-3.5" style={{ color }} />
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
          {label}
        </span>
      </div>
      <p className="font-['Chivo'] text-xl font-bold text-white">{value}</p>
    </div>
  );
}

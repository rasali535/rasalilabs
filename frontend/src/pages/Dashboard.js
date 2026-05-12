import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Plus,
  Zap,
  FolderOpen,
  MessageSquare,
  ListTodo,
  ShieldCheck,
  Users,
  TrendingUp,
  FileOutput,
} from "lucide-react";
import { getStats, getProjects, createProject, getAgents, AGENT_META, getLogoUrl } from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import AgentAvatar from "@/components/AgentAvatar";

const STAT_CARDS = [
  { key: "projects", icon: FolderOpen, label: "Projects", getValue: (s) => s.projects?.total || 0 },
  { key: "tasks", icon: ListTodo, label: "Tasks", getValue: (s) => s.tasks?.total || 0 },
  { key: "meetings", icon: Users, label: "Meetings", getValue: (s) => s.meetings || 0 },
  { key: "messages", icon: MessageSquare, label: "Messages", getValue: (s) => s.messages || 0 },
  { key: "decisions", icon: ShieldCheck, label: "Decisions", getValue: (s) => s.decisions || 0 },
  { key: "artifacts", icon: FileOutput, label: "Artifacts", getValue: (s) => s.artifacts || 0 },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({});
  const [projects, setProjects] = useState([]);
  const [agents, setAgents] = useState([]);
  const [showNewProject, setShowNewProject] = useState(false);
  const [goal, setGoal] = useState("");
  const [outputFormat, setOutputFormat] = useState("html");
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [s, p, a] = await Promise.all([getStats(), getProjects(), getAgents()]);
      setStats(s);
      setProjects(p);
      setAgents(a);
    } catch (e) {
      console.error("Failed to load dashboard data", e);
    }
  }, []);

  useEffect(() => {
    loadData();
    const iv = setInterval(loadData, 5000);
    return () => clearInterval(iv);
  }, [loadData]);

  const handleCreateProject = async () => {
    if (!goal.trim()) return;
    setLoading(true);
    try {
      const project = await createProject({ goal: goal.trim(), output_format: outputFormat });
      toast.success("Project created! Kickoff meeting starting...");
      setShowNewProject(false);
      setGoal("");
      loadData();
      setTimeout(() => navigate(`/boardroom`), 1500);
    } catch (e) {
      toast.error("Failed to create project");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#0A0A0A]" data-testid="dashboard-page">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#222222] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <img 
            src={getLogoUrl()} 
            alt="Ras Ali Labs" 
            className="w-10 h-10 object-contain"
          />
          <div>
            <h1 className="font-['Chivo'] text-xl font-bold tracking-tight text-white" data-testid="dashboard-title">
              Command Center
            </h1>
            <p className="text-xs text-zinc-500 mt-0.5 font-mono uppercase tracking-wider">
              Ras Ali Labs | AI Workflow Engine
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowNewProject(true)}
          className="btn-primary flex items-center gap-2 px-4 py-2 text-sm"
          data-testid="new-project-btn"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-6">
          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="stats-grid">
            {STAT_CARDS.map((card, i) => (
              <div
                key={card.key}
                className={`bg-[#111111] border border-[#222222] rounded-sm p-4 animate-fade-in stagger-${i + 1}`}
                data-testid={`stat-${card.key}`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <card.icon className="w-4 h-4 text-zinc-500" strokeWidth={1.5} />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                    {card.label}
                  </span>
                </div>
                <p className="font-['Chivo'] text-2xl font-bold text-white">
                  {card.getValue(stats)}
                </p>
              </div>
            ))}
          </div>

          {/* Agent Team */}
          <div>
            <h3 className="font-['Chivo'] text-sm font-bold tracking-tight text-zinc-400 uppercase mb-3">
              Agent Team
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="agent-team-grid">
              {agents.map((agent) => {
                const meta = AGENT_META[agent.role] || {};
                return (
                  <div
                    key={agent.id}
                    className="bg-[#111111] border border-[#222222] hover:border-[#333333] transition-colors rounded-sm p-3 flex items-center gap-3 cursor-pointer"
                    data-testid={`agent-card-${agent.role}`}
                  >
                    <AgentAvatar role={agent.role} size="lg" />
                    <div className="flex flex-col min-w-0">
                      <span className="text-sm font-medium text-white truncate">{agent.name}</span>
                      <span
                        className="font-mono text-[10px] uppercase tracking-wider"
                        style={{ color: meta.color }}
                      >
                        {agent.title}
                      </span>
                    </div>
                    <span className="status-dot status-active ml-auto shrink-0 pulse-dot" />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recent Projects */}
          <div>
            <h3 className="font-['Chivo'] text-sm font-bold tracking-tight text-zinc-400 uppercase mb-3">
              Recent Projects
            </h3>
            {projects.length === 0 ? (
              <div
                className="bg-[#111111] border border-[#222222] rounded-sm p-8 text-center"
                data-testid="no-projects"
              >
                <Zap className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
                <p className="text-sm text-zinc-500">No projects yet. Submit a goal to get started.</p>
              </div>
            ) : (
              <div className="space-y-2" data-testid="projects-list">
                {projects.slice(0, 5).map((project) => (
                  <div
                    key={project.id}
                    className="bg-[#111111] border border-[#222222] hover:border-[#333333] transition-colors rounded-sm p-4 cursor-pointer flex items-center justify-between"
                    onClick={() => navigate(`/projects`)}
                    data-testid={`project-row-${project.id}`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white truncate">{project.goal}</p>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                          {project.output_format}
                        </span>
                        <span className="font-mono text-[10px] text-zinc-600">
                          {new Date(project.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <span
                      className={`font-mono text-[10px] uppercase tracking-wider px-2 py-1 rounded-sm border ${
                        project.status === "completed"
                          ? "text-green-400 bg-green-500/10 border-green-500/30"
                          : project.status === "in_progress"
                          ? "text-blue-400 bg-blue-500/10 border-blue-500/30"
                          : "text-yellow-400 bg-yellow-500/10 border-yellow-500/30"
                      }`}
                    >
                      {project.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </ScrollArea>

      {/* New Project Dialog */}
      <Dialog open={showNewProject} onOpenChange={setShowNewProject}>
        <DialogContent className="bg-[#111111] border border-[#222222] text-white max-w-lg" data-testid="new-project-dialog">
          <DialogHeader>
            <DialogTitle className="font-['Chivo'] text-lg font-bold tracking-tight">
              New Project Goal
            </DialogTitle>
            <DialogDescription className="text-xs text-zinc-500">
              Submit a business objective for the labs to execute.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <label className="font-mono text-xs text-zinc-400 uppercase tracking-widest mb-1.5 block">
                Business Objective
              </label>
              <textarea
                className="w-full bg-[#141414] border border-[#222222] focus:border-[#0030FF] focus:ring-1 focus:ring-[#0030FF] rounded-sm text-white px-3 py-2 text-sm resize-none h-24 outline-none"
                placeholder="e.g. Build a landing page and deliver HTML + PNG preview"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                data-testid="project-goal-input"
              />
            </div>
            <div>
              <label className="font-mono text-xs text-zinc-400 uppercase tracking-widest mb-1.5 block">
                Output Format
              </label>
              <Select value={outputFormat} onValueChange={setOutputFormat}>
                <SelectTrigger className="bg-[#141414] border-[#222222] text-white" data-testid="output-format-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#141414] border-[#222222]">
                  <SelectItem value="html">HTML</SelectItem>
                  <SelectItem value="json">JSON</SelectItem>
                  <SelectItem value="code">Code Files</SelectItem>
                  <SelectItem value="pdf">PDF</SelectItem>
                  <SelectItem value="png">PNG</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <button
              className="btn-secondary px-4 py-2 text-sm"
              onClick={() => setShowNewProject(false)}
              data-testid="cancel-project-btn"
            >
              Cancel
            </button>
            <button
              className="btn-primary px-4 py-2 text-sm flex items-center gap-2"
              onClick={handleCreateProject}
              disabled={loading || !goal.trim()}
              data-testid="submit-project-btn"
            >
              {loading ? (
                <span className="font-mono text-xs typing-indicator">...</span>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Launch Project
                </>
              )}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  FolderOpen,
  Play,
  FileOutput,
  Download,
  Eye,
  Users,
  ListTodo,
  MessageSquare,
  Image,
  FileText,
} from "lucide-react";
import {
  getProjects,
  getProject,
  getMeetings,
  getTasks,
  getArtifacts,
  executeProject,
  renderArtifact,
  AGENT_META,
} from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AgentAvatar from "@/components/AgentAvatar";
import TaskCard from "@/components/TaskCard";

export default function Projects() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [selected, setSelected] = useState(null);
  const [meetings, setMeetings] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [previewArtifact, setPreviewArtifact] = useState(null);

  const loadProjects = useCallback(async () => {
    try {
      const p = await getProjects();
      setProjects(p);
      if (p.length > 0 && !selected) setSelected(p[0]);
    } catch (e) {
      console.error(e);
    }
  }, [selected]);

  const loadDetails = useCallback(async () => {
    if (!selected) return;
    try {
      const [m, t, a] = await Promise.all([
        getMeetings(selected.id),
        getTasks({ project_id: selected.id }),
        getArtifacts(selected.id),
      ]);
      setMeetings(m);
      setTasks(t);
      setArtifacts(a);
    } catch (e) {
      console.error(e);
    }
  }, [selected]);

  useEffect(() => {
    loadProjects();
    const iv = setInterval(loadProjects, 5000);
    return () => clearInterval(iv);
  }, [loadProjects]);

  useEffect(() => {
    loadDetails();
    const iv = setInterval(loadDetails, 3000);
    return () => clearInterval(iv);
  }, [loadDetails]);

  const handleExecute = async (projectId) => {
    try {
      await executeProject(projectId);
      toast.success("Execution started!");
    } catch (e) {
      toast.error("Failed to execute");
    }
  };

  const STATUS_STYLE = {
    planning: "text-yellow-400 bg-yellow-500/10 border-yellow-500/30",
    in_progress: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    completed: "text-green-400 bg-green-500/10 border-green-500/30",
  };

  return (
    <div className="h-full flex flex-col bg-[#0A0A0A]" data-testid="projects-page">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#222222] shrink-0">
        <h2 className="font-['Chivo'] text-base font-bold tracking-tight text-white" data-testid="projects-title">
          Projects
        </h2>
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Project List */}
        <div className="w-[320px] border-r border-[#222222] flex flex-col shrink-0" data-testid="project-list-panel">
          <ScrollArea className="flex-1">
            <div className="py-1">
              {projects.length === 0 ? (
                <p className="text-xs text-zinc-600 text-center py-8">No projects yet</p>
              ) : (
                projects.map((p) => {
                  const isActive = selected?.id === p.id;
                  return (
                    <div
                      key={p.id}
                      className={`px-3 py-3 cursor-pointer transition-colors border-l-2 ${
                        isActive
                          ? "bg-[#1A1A1A] border-l-[#0030FF]"
                          : "border-l-transparent hover:bg-[#141414]"
                      }`}
                      onClick={() => setSelected(p)}
                      data-testid={`project-item-${p.id}`}
                    >
                      <p className="text-[13px] font-medium text-white truncate mb-1">
                        {p.goal}
                      </p>
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ${
                            STATUS_STYLE[p.status] || STATUS_STYLE.planning
                          }`}
                        >
                          {p.status}
                        </span>
                        <span className="font-mono text-[9px] text-zinc-600">
                          {p.output_format}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </ScrollArea>
        </div>

        {/* Project Detail */}
        <div className="flex-1 flex flex-col" data-testid="project-detail-panel">
          {selected ? (
            <>
              {/* Project Header */}
              <div className="px-4 py-3 border-b border-[#222222] shrink-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium text-white mb-1">{selected.goal}</h3>
                    <div className="flex items-center gap-3">
                      <span
                        className={`font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ${
                          STATUS_STYLE[selected.status] || STATUS_STYLE.planning
                        }`}
                      >
                        {selected.status}
                      </span>
                      <span className="font-mono text-[10px] text-zinc-500">
                        Format: {selected.output_format}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="btn-secondary px-3 py-1.5 text-xs flex items-center gap-1.5"
                      onClick={() => navigate("/boardroom")}
                      data-testid="go-boardroom-btn"
                    >
                      <Users className="w-3 h-3" />
                      Boardroom
                    </button>
                    <button
                      className="btn-primary px-3 py-1.5 text-xs flex items-center gap-1.5"
                      onClick={() => handleExecute(selected.id)}
                      data-testid="execute-btn"
                    >
                      <Play className="w-3 h-3" />
                      Execute
                    </button>
                  </div>
                </div>
              </div>

              {/* Tabs: Tasks / Artifacts / Meetings */}
              <Tabs defaultValue="tasks" className="flex-1 flex flex-col min-h-0">
                <TabsList className="bg-transparent border-b border-[#222222] rounded-none px-4 h-auto py-0 shrink-0">
                  <TabsTrigger
                    value="tasks"
                    className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-3 text-zinc-500"
                    data-testid="project-tab-tasks"
                  >
                    <ListTodo className="w-3 h-3 mr-1.5" />
                    Tasks ({tasks.length})
                  </TabsTrigger>
                  <TabsTrigger
                    value="artifacts"
                    className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-3 text-zinc-500"
                    data-testid="project-tab-artifacts"
                  >
                    <FileOutput className="w-3 h-3 mr-1.5" />
                    Artifacts ({artifacts.length})
                  </TabsTrigger>
                  <TabsTrigger
                    value="meetings"
                    className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-3 text-zinc-500"
                    data-testid="project-tab-meetings"
                  >
                    <MessageSquare className="w-3 h-3 mr-1.5" />
                    Meetings ({meetings.length})
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="tasks" className="flex-1 m-0 overflow-hidden">
                  <ScrollArea className="h-full p-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {tasks.map((task) => (
                        <TaskCard key={task.id} task={task} />
                      ))}
                    </div>
                  </ScrollArea>
                </TabsContent>

                <TabsContent value="artifacts" className="flex-1 m-0 overflow-hidden">
                  <ScrollArea className="h-full p-4">
                    <div className="space-y-2">
                      {artifacts.length === 0 ? (
                        <p className="text-xs text-zinc-600 text-center py-8">
                          No artifacts generated yet. Execute the project first.
                        </p>
                      ) : (
                        artifacts.map((art) => (
                          <div
                            key={art.id}
                            className="bg-[#111111] border border-[#222222] rounded-sm p-3 flex items-center justify-between"
                            data-testid={`artifact-${art.id}`}
                          >
                            <div className="flex items-center gap-3">
                              <FileOutput className="w-4 h-4 text-zinc-500" />
                              <div>
                                <p className="text-[13px] font-medium text-white">{art.name}</p>
                                <span className="font-mono text-[9px] uppercase tracking-wider text-zinc-500">
                                  {art.artifact_type}
                                </span>
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              {art.content && art.artifact_type !== "png" && art.artifact_type !== "pdf" && (
                                <button
                                  className="btn-secondary px-2 py-1 text-[10px] flex items-center gap-1"
                                  onClick={() => setPreviewArtifact(art)}
                                  data-testid={`preview-artifact-${art.id}`}
                                >
                                  <Eye className="w-3 h-3" />
                                  Preview
                                </button>
                              )}
                              {art.artifact_type === "png" && art.content && (
                                <button
                                  className="btn-secondary px-2 py-1 text-[10px] flex items-center gap-1"
                                  onClick={() => setPreviewArtifact(art)}
                                  data-testid={`preview-png-${art.id}`}
                                >
                                  <Image className="w-3 h-3" />
                                  View PNG
                                </button>
                              )}
                              {art.artifact_type === "pdf" && art.content && (
                                <button
                                  className="btn-secondary px-2 py-1 text-[10px] flex items-center gap-1"
                                  onClick={() => {
                                    // Download PDF from base64
                                    const byteChars = atob(art.content);
                                    const byteNums = new Array(byteChars.length);
                                    for (let i = 0; i < byteChars.length; i++) byteNums[i] = byteChars.charCodeAt(i);
                                    const blob = new Blob([new Uint8Array(byteNums)], { type: "application/pdf" });
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement("a");
                                    a.href = url;
                                    a.download = art.name;
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  }}
                                  data-testid={`download-pdf-${art.id}`}
                                >
                                  <FileText className="w-3 h-3" />
                                  Download PDF
                                </button>
                              )}
                              {art.artifact_type === "html" && (
                                <>
                                  <button
                                    className="px-2 py-1 text-[10px] flex items-center gap-1 bg-purple-500/10 border border-purple-500/30 text-purple-400 rounded-sm hover:bg-purple-500/20 transition-colors"
                                    onClick={async () => {
                                      try {
                                        toast.info("Rendering PNG...");
                                        await renderArtifact({ artifact_id: art.id, render_type: "png" });
                                        toast.success("PNG rendered!");
                                        loadDetails();
                                      } catch (e) {
                                        toast.error("PNG render failed");
                                      }
                                    }}
                                    data-testid={`render-png-${art.id}`}
                                  >
                                    <Image className="w-3 h-3" />
                                    Render PNG
                                  </button>
                                  <button
                                    className="px-2 py-1 text-[10px] flex items-center gap-1 bg-orange-500/10 border border-orange-500/30 text-orange-400 rounded-sm hover:bg-orange-500/20 transition-colors"
                                    onClick={async () => {
                                      try {
                                        toast.info("Generating PDF...");
                                        await renderArtifact({ artifact_id: art.id, render_type: "pdf" });
                                        toast.success("PDF generated!");
                                        loadDetails();
                                      } catch (e) {
                                        toast.error("PDF generation failed");
                                      }
                                    }}
                                    data-testid={`render-pdf-${art.id}`}
                                  >
                                    <FileText className="w-3 h-3" />
                                    Render PDF
                                  </button>
                                </>
                              )}
                              {art.content && art.artifact_type !== "png" && art.artifact_type !== "pdf" && (
                                <button
                                  className="btn-primary px-2 py-1 text-[10px] flex items-center gap-1"
                                  onClick={() => {
                                    const blob = new Blob([art.content], { type: "text/plain" });
                                    const url = URL.createObjectURL(blob);
                                    const a = document.createElement("a");
                                    a.href = url;
                                    a.download = art.name;
                                    a.click();
                                    URL.revokeObjectURL(url);
                                  }}
                                  data-testid={`download-artifact-${art.id}`}
                                >
                                  <Download className="w-3 h-3" />
                                  Download
                                </button>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </ScrollArea>
                </TabsContent>

                <TabsContent value="meetings" className="flex-1 m-0 overflow-hidden">
                  <ScrollArea className="h-full p-4">
                    <div className="space-y-2">
                      {meetings.map((m) => (
                        <div
                          key={m.id}
                          className="bg-[#111111] border border-[#222222] rounded-sm p-3 cursor-pointer hover:border-[#333333] transition-colors"
                          onClick={() => navigate(`/boardroom/${m.id}`)}
                          data-testid={`meeting-${m.id}`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-[13px] font-medium text-white">{m.title}</span>
                            <span
                              className={`font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ${
                                m.status === "completed"
                                  ? "text-green-400 bg-green-500/10 border-green-500/30"
                                  : "text-blue-400 bg-blue-500/10 border-blue-500/30"
                              }`}
                            >
                              {m.status}
                            </span>
                          </div>
                          {m.summary && (
                            <p className="text-[11px] text-zinc-400 line-clamp-2">{m.summary}</p>
                          )}
                          <div className="flex items-center gap-1 mt-2">
                            {m.participants?.slice(0, 5).map((p) => (
                              <AgentAvatar key={p} role={p} size="sm" />
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </TabsContent>
              </Tabs>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-xs text-zinc-600">Select a project to view details</p>
            </div>
          )}
        </div>
      </div>

      {/* Artifact Preview Dialog */}
      <Dialog open={!!previewArtifact} onOpenChange={() => setPreviewArtifact(null)}>
        <DialogContent className="bg-[#111111] border border-[#222222] text-white max-w-3xl max-h-[80vh]" data-testid="artifact-preview-dialog">
          <DialogHeader>
            <DialogTitle className="font-['Chivo'] text-sm font-bold tracking-tight">
              {previewArtifact?.name}
            </DialogTitle>
          </DialogHeader>
          <ScrollArea className="max-h-[60vh]">
            {previewArtifact?.artifact_type === "html" ? (
              <div className="rounded-sm border border-[#222222] overflow-hidden">
                <iframe
                  srcDoc={previewArtifact.content}
                  className="w-full h-[400px] bg-white"
                  title="HTML Preview"
                  sandbox="allow-scripts"
                  data-testid="html-preview-iframe"
                />
              </div>
            ) : previewArtifact?.artifact_type === "png" ? (
              <div className="rounded-sm border border-[#222222] overflow-hidden">
                <img
                  src={`data:image/png;base64,${previewArtifact.content}`}
                  alt="PNG Preview"
                  className="w-full"
                  data-testid="png-preview-img"
                />
              </div>
            ) : (
              <pre className="bg-[#0A0A0A] border border-[#222222] rounded-sm p-4 text-[12px] font-mono text-zinc-300 overflow-x-auto whitespace-pre-wrap">
                {previewArtifact?.content}
              </pre>
            )}
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
}

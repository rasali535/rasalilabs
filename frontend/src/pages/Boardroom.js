import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Play,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronRight,
  FileOutput,
} from "lucide-react";
import { toast } from "sonner";
import {
  getMeetings,
  getMeeting,
  getMessages,
  getTasks,
  getDecisions,
  executeProject,
  getProjects,
  AGENT_META,
} from "@/lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AgentAvatar from "@/components/AgentAvatar";
import MessageBubble from "@/components/MessageBubble";
import TaskCard from "@/components/TaskCard";

export default function Boardroom() {
  const { meetingId: paramMeetingId } = useParams();
  const navigate = useNavigate();
  const [meetings, setMeetings] = useState([]);
  const [activeMeeting, setActiveMeeting] = useState(null);
  const [messages, setMessages] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [executing, setExecuting] = useState(false);
  const scrollRef = useRef(null);

  const loadMeetings = useCallback(async () => {
    try {
      const m = await getMeetings();
      setMeetings(m);
      if (m.length > 0 && !activeMeeting) {
        const target = paramMeetingId ? m.find((x) => x.id === paramMeetingId) : m[0];
        if (target) setActiveMeeting(target);
        else setActiveMeeting(m[0]);
      }
    } catch (e) {
      console.error(e);
    }
  }, [paramMeetingId, activeMeeting]);

  const loadMeetingData = useCallback(async () => {
    if (!activeMeeting) return;
    try {
      const [msgs, t, d] = await Promise.all([
        getMessages({ meeting_id: activeMeeting.id }),
        getTasks({ project_id: activeMeeting.project_id }),
        getDecisions({ project_id: activeMeeting.project_id }),
      ]);
      setMessages(msgs);
      setTasks(t);
      setDecisions(d);
    } catch (e) {
      console.error(e);
    }
  }, [activeMeeting]);

  useEffect(() => {
    loadMeetings();
  }, [loadMeetings]);

  useEffect(() => {
    loadMeetingData();
    const iv = setInterval(loadMeetingData, 3000);
    return () => clearInterval(iv);
  }, [loadMeetingData]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleExecute = async () => {
    if (!activeMeeting?.project_id) return;
    setExecuting(true);
    try {
      await executeProject(activeMeeting.project_id);
      toast.success("Execution started! Agents are working...");
      setTimeout(loadMeetingData, 2000);
    } catch (e) {
      toast.error("Failed to start execution");
    } finally {
      setExecuting(false);
    }
  };

  const nextAction = tasks.find((t) => t.status === "pending" || t.status === "in_progress");

  if (meetings.length === 0) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0A0A0A]" data-testid="boardroom-empty">
        <div className="text-center">
          <p className="text-sm text-zinc-500 mb-3">No meetings yet.</p>
          <button
            onClick={() => navigate("/")}
            className="btn-primary px-4 py-2 text-sm"
            data-testid="go-create-project-btn"
          >
            Create a Project
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-[#0A0A0A]" data-testid="boardroom-page">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#222222] flex items-center gap-3 shrink-0">
        <h2 className="font-['Chivo'] text-base font-bold tracking-tight text-white" data-testid="boardroom-title">
          Boardroom
        </h2>
        {activeMeeting && (
          <>
            <ChevronRight className="w-3 h-3 text-zinc-600" />
            <span className="text-xs text-zinc-400 truncate max-w-[300px]">{activeMeeting.title}</span>
            <span
              className={`font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border ml-2 ${
                activeMeeting.status === "completed"
                  ? "text-green-400 bg-green-500/10 border-green-500/30"
                  : "text-blue-400 bg-blue-500/10 border-blue-500/30"
              }`}
              data-testid="meeting-status-badge"
            >
              {activeMeeting.status}
            </span>
          </>
        )}
      </div>

      {/* Main Grid */}
      <div className="flex-1 grid grid-cols-12 min-h-0">
        {/* Left Panel - Participants */}
        <div
          className="col-span-2 border-r border-[#222222] flex flex-col bg-[#0A0A0A]"
          data-testid="boardroom-participants-panel"
        >
          <div className="panel-header">
            <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
              Participants
            </span>
          </div>
          <ScrollArea className="flex-1 p-3">
            <div className="space-y-2">
              {(activeMeeting?.participants || Object.keys(AGENT_META)).map((role) => {
                const meta = AGENT_META[role];
                if (!meta) return null;
                const hasSpoken = messages.some((m) => m.from_agent === role);
                return (
                  <div
                    key={role}
                    className="flex items-center gap-2 py-1.5 px-2 rounded-sm hover:bg-[#141414] transition-colors"
                    data-testid={`participant-${role}`}
                  >
                    <AgentAvatar role={role} size="sm" />
                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="text-[11px] font-medium text-white truncate">{meta.name}</span>
                      <span
                        className="font-mono text-[9px] uppercase tracking-wider"
                        style={{ color: meta.color }}
                      >
                        {meta.title}
                      </span>
                    </div>
                    <span
                      className={`status-dot ${hasSpoken ? "status-active" : "status-idle"}`}
                    />
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </div>

        {/* Center Panel - Dialogue */}
        <div
          className="col-span-7 flex flex-col bg-[#111111]"
          data-testid="boardroom-dialogue-panel"
        >
          <div className="panel-header">
            <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
              Meeting Transcript
            </span>
            <span className="font-mono text-[10px] text-zinc-600">
              {messages.length} messages
            </span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-1" ref={scrollRef}>
            {messages.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <p className="font-mono text-xs text-zinc-600 typing-indicator">
                  Waiting for meeting to begin...
                </p>
              </div>
            ) : (
              messages.map((msg, i) => (
                <MessageBubble key={msg.id} message={msg} index={i} />
              ))
            )}
          </div>

          {/* Bottom Execution Bar */}
          <div
            className="border-t border-[#222222] p-4 bg-[#0A0A0A]"
            data-testid="boardroom-execution-bar"
          >
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1 min-w-0">
                {nextAction ? (
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                      Next:
                    </span>
                    <span className="text-xs text-white truncate">{nextAction.title}</span>
                    {nextAction.assigned_to && (
                      <AgentAvatar role={nextAction.assigned_to} size="sm" />
                    )}
                  </div>
                ) : (
                  <span className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider">
                    All tasks scheduled
                  </span>
                )}
              </div>
              <button
                className="btn-primary px-6 py-2.5 text-sm flex items-center gap-2 whitespace-nowrap"
                onClick={handleExecute}
                disabled={executing}
                data-testid="execute-project-btn"
              >
                {executing ? (
                  <span className="font-mono text-xs typing-indicator">Executing...</span>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Execute Project
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right Panel - Agenda / Approvals / Delegation */}
        <div
          className="col-span-3 border-l border-[#222222] flex flex-col bg-[#0A0A0A]"
          data-testid="boardroom-right-panel"
        >
          <Tabs defaultValue="agenda" className="flex flex-col h-full">
            <TabsList className="bg-transparent border-b border-[#222222] rounded-none px-2 h-auto py-0 shrink-0">
              <TabsTrigger
                value="agenda"
                className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-3 text-zinc-500"
                data-testid="tab-agenda"
              >
                Agenda
              </TabsTrigger>
              <TabsTrigger
                value="approvals"
                className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-3 text-zinc-500"
                data-testid="tab-approvals"
              >
                Approvals
              </TabsTrigger>
              <TabsTrigger
                value="tasks"
                className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-3 text-zinc-500"
                data-testid="tab-tasks"
              >
                Tasks
              </TabsTrigger>
            </TabsList>

            <TabsContent value="agenda" className="flex-1 m-0 overflow-hidden">
              <ScrollArea className="h-full p-3">
                <div className="space-y-2">
                  {(activeMeeting?.agenda_items || []).map((item, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 py-2 px-2 bg-[#111111] border border-[#222222] rounded-sm"
                      data-testid={`agenda-item-${i}`}
                    >
                      <CheckCircle className="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
                      <span className="text-[12px] text-zinc-300">{item}</span>
                    </div>
                  ))}
                  {activeMeeting?.summary && (
                    <div className="mt-4 p-3 bg-[#111111] border border-[#222222] rounded-sm">
                      <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500 block mb-2">
                        Meeting Summary
                      </span>
                      <p className="text-[12px] text-zinc-300 leading-relaxed">{activeMeeting.summary}</p>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="approvals" className="flex-1 m-0 overflow-hidden">
              <ScrollArea className="h-full p-3">
                <div className="space-y-2">
                  {decisions.length === 0 ? (
                    <p className="text-xs text-zinc-600 text-center py-4">No decisions yet</p>
                  ) : (
                    decisions.map((dec) => (
                      <div
                        key={dec.id}
                        className="p-3 bg-[#111111] border border-[#222222] rounded-sm"
                        data-testid={`decision-${dec.id}`}
                      >
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <span className="text-[12px] font-medium text-white">{dec.title}</span>
                          <span
                            className={`font-mono text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border shrink-0 ${
                              dec.status === "approved"
                                ? "text-green-400 bg-green-500/10 border-green-500/30"
                                : dec.status === "rejected"
                                ? "text-red-400 bg-red-500/10 border-red-500/30"
                                : "text-yellow-400 bg-yellow-500/10 border-yellow-500/30"
                            }`}
                          >
                            {dec.status}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(dec.votes || {}).map(([role, vote]) => (
                            <span
                              key={role}
                              className="font-mono text-[9px] px-1 py-0.5 rounded-sm bg-[#1A1A1A] border border-[#222222]"
                              style={{ color: AGENT_META[role]?.color || "#A1A1AA" }}
                            >
                              {role.toUpperCase()}: {vote === "approved" ? "Y" : vote === "rejected" ? "N" : "?"}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="tasks" className="flex-1 m-0 overflow-hidden">
              <ScrollArea className="h-full p-3">
                <div className="space-y-2">
                  {tasks.length === 0 ? (
                    <p className="text-xs text-zinc-600 text-center py-4">No tasks yet</p>
                  ) : (
                    tasks.map((task) => <TaskCard key={task.id} task={task} />)
                  )}
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  Cpu,
  RefreshCw,
  Check,
  X,
  Zap,
  Download,
  Play,
  Settings2,
  ArrowRight,
  Loader2,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AgentAvatar from "@/components/AgentAvatar";
import api, { AGENT_META } from "@/lib/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || (window.location.origin.includes("vercel.app") ? "https://rasalilabs.vercel.app" : window.location.origin.replace(":3000", ":4001"));

const MODE_LABELS = {
  aiml: { label: "AI/ML Mix", desc: "Routes coding tasks to Qwen and reasoning to GPT-4o-Mini via AI/ML API" },
  auto: { label: "Local Auto", desc: "Routes to local Llama (reasoning) or Qwen (coding) when Ollama is active" },
  llama_only: { label: "Llama Only", desc: "All agents use the reasoning model for everything" },
  qwen_only: { label: "Qwen Only", desc: "All agents use the coding model for everything" },
  simulation: { label: "Simulation", desc: "No LLM calls. Uses predefined responses for all agents" },
};

export default function Models() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(null);
  const [testResult, setTestResult] = useState(null);

  // Editable form state
  const [mode, setMode] = useState("auto");

  const [roleOverrides, setRoleOverrides] = useState({});

  const loadModels = useCallback(async () => {
    try {
      const res = await api.get("/models");
      if (res && res.data) {
        setData(res.data);
        setMode(res.data.config.mode);
        setRoleOverrides(res.data.config.role_overrides || {});
      }
    } catch (e) {
      console.error(e);
      // Mode defaults if API fails
      setMode("aiml");
      toast.error(e.message || "Failed to load configuration");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const handleSaveMode = async (newMode) => {
    try {
      await api.post("/models/config", {
        mode: newMode,
        role_overrides: roleOverrides,
      });
      setMode(newMode);
      toast.success("Configuration updated successfully");
      loadModels();
    } catch (e) {
      toast.error(e.message || "Failed to update configuration");
    }
  };

  const handleRoleOverrideChange = (role, newModel) => {
    setRoleOverrides((prev) => ({ ...prev, [role]: newModel }));
  };

  const handleTest = async (modelName) => {
    setTesting(modelName);
    setTestResult(null);
    try {
      const res = await api.get(`/models/test/${encodeURIComponent(modelName)}`);
      setTestResult(res.data);
      if (res.data.status === "ok") {
        toast.success(`${modelName} responded successfully`);
      } else {
        toast.error(`Test failed for ${modelName}`);
      }
    } catch (e) {
      toast.error(e.message || "Failed to test model");
    } finally {
      setTesting(null);
    }
  };



  const setRoleOverride = (role, model) => {
    if (!model || model === "__default__") {
      const next = { ...roleOverrides };
      delete next[role];
      setRoleOverrides(next);
    } else {
      setRoleOverrides({ ...roleOverrides, [role]: model });
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0A0A0A]">
        <span className="font-mono text-xs text-zinc-600 typing-indicator">Loading model config...</span>
      </div>
    );
  }


  const routingTable = data?.routing_table || {};

  return (
    <div className="h-full flex flex-col bg-[#0A0A0A]" data-testid="models-page">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#222222] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-[#0030FF]/10 border border-[#0030FF]/30 flex items-center justify-center">
            <Cpu className="w-4 h-4 text-[#0030FF]" />
          </div>
          <div>
            <h1 className="font-['Chivo'] text-xl font-bold tracking-tight text-white" data-testid="models-title">
              Model Router
            </h1>
            <p className="text-xs text-zinc-500 font-mono uppercase tracking-wider">
              AI/ML API Routing
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadModels}
            className="btn-secondary px-3 py-1.5 text-xs flex items-center gap-1.5"
            data-testid="refresh-models-btn"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
          <button
            onClick={() => handleSaveMode(mode)}
            disabled={saving}
            className="btn-primary px-4 py-1.5 text-xs flex items-center gap-1.5"
            data-testid="save-config-btn"
          >
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
            Save Config
          </button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-6">
          {/* Routing Mode */}
          <div className="grid grid-cols-1 gap-4">
            <div className="bg-[#111111] border border-[#222222] rounded-sm p-4" data-testid="routing-mode-card">
              <label className="font-mono text-[10px] text-zinc-400 uppercase tracking-widest mb-2 block">
                Routing Mode (AI/ML API)
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                {Object.entries(MODE_LABELS).map(([key, { label, desc }]) => (
                  <button
                    key={key}
                    onClick={() => setMode(key)}
                    className={`p-3 rounded-sm border text-left transition-colors ${
                      mode === key
                        ? "bg-[#0030FF]/10 border-[#0030FF]/50 text-white"
                        : "bg-[#141414] border-[#222222] text-zinc-400 hover:border-[#333]"
                    }`}
                    data-testid={`mode-${key}-btn`}
                  >
                    <span className="text-xs font-medium block">{label}</span>
                    <span className="text-[10px] text-zinc-500 block mt-0.5">{desc}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Test Result */}
          {testResult && (
            <div
              className={`border rounded-sm p-4 ${
                testResult.status === "ok"
                  ? "bg-green-500/5 border-green-500/30"
                  : "bg-red-500/5 border-red-500/30"
              }`}
              data-testid="test-result"
            >
              <div className="flex items-center gap-2 mb-2">
                {testResult.status === "ok" ? (
                  <Check className="w-4 h-4 text-green-400" />
                ) : (
                  <X className="w-4 h-4 text-red-400" />
                )}
                <span className="text-xs font-medium text-white">
                  {testResult.status === "ok" ? `${testResult.model} responded` : "Test failed"}
                </span>
                {testResult.total_duration_ms && (
                  <span className="font-mono text-[9px] text-zinc-500 ml-auto">
                    {testResult.total_duration_ms.toFixed(0)}ms
                  </span>
                )}
              </div>
              <p className="text-[12px] text-zinc-400 font-mono">
                {testResult.response || testResult.detail}
              </p>
            </div>
          )}

          {/* Tabs: Routing Table / Available Models / Pull */}
          <Tabs defaultValue="routing" className="space-y-4">
            <TabsList className="bg-transparent border-b border-[#222222] rounded-none px-0 h-auto py-0">
              <TabsTrigger
                value="routing"
                className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-4 text-zinc-500"
                data-testid="tab-routing"
              >
                Routing Table
              </TabsTrigger>

              <TabsTrigger
                value="overrides"
                className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-4 text-zinc-500"
                data-testid="tab-overrides"
              >
                Per-Agent Overrides
              </TabsTrigger>
            </TabsList>

            {/* Routing Table */}
            <TabsContent value="routing" className="m-0">
              <div className="space-y-2" data-testid="routing-table">
                {Object.entries(routingTable).map(([role, tasks]) => {
                  const meta = AGENT_META[role] || {};
                  return (
                    <div key={role} className="bg-[#111111] border border-[#222222] rounded-sm p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <AgentAvatar role={role} size="sm" />
                        <span className="text-xs font-medium text-white">{meta.name}</span>
                        <span className="font-mono text-[9px] uppercase tracking-wider" style={{ color: meta.color }}>
                          {meta.title}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {Object.entries(tasks).map(([taskType, info]) => (
                          <div key={taskType} className="flex items-center gap-1.5 px-2 py-1 bg-[#1A1A1A] border border-[#222222] rounded-sm">
                            <span className="font-mono text-[9px] text-zinc-500 uppercase">{taskType}</span>
                            <ArrowRight className="w-2.5 h-2.5 text-zinc-600" />
                            <span className={`font-mono text-[9px] font-medium ${info.model === "simulation" ? "text-yellow-400" : info.model.includes("qwen") ? "text-blue-400" : "text-green-400"}`}>
                              {info.model}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </TabsContent>


            {/* Per-Agent Overrides */}
            <TabsContent value="overrides" className="m-0">
              <div className="space-y-2" data-testid="role-overrides">
                <p className="text-[11px] text-zinc-500 mb-3">
                  Override the default model for specific agents. Leave blank to use the default routing.
                </p>
                {Object.entries(AGENT_META).map(([role, meta]) => (
                  <div key={role} className="bg-[#111111] border border-[#222222] rounded-sm p-3 flex items-center gap-3">
                    <AgentAvatar role={role} size="sm" showName />
                    <div className="flex-1">
                      <input
                        type="text"
                        value={roleOverrides[role] || ""}
                        onChange={(e) => setRoleOverride(role, e.target.value)}
                        placeholder="Default routing"
                        className="w-full bg-[#141414] border border-[#222222] focus:border-[#0030FF] rounded-sm text-white px-3 py-1.5 text-xs font-mono outline-none"
                        data-testid={`override-${role}-input`}
                      />
                    </div>
                    {roleOverrides[role] && (
                      <button
                        onClick={() => setRoleOverride(role, "")}
                        className="text-zinc-500 hover:text-white"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </ScrollArea>
    </div>
  );
}

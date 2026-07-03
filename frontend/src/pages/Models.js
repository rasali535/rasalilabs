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
import { AGENT_META } from "@/lib/api";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || window.location.origin.replace(":3000", ":4001");

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
  const [pullModel, setPullModel] = useState("");
  const [pulling, setPulling] = useState(false);

  // Editable form state
  const [mode, setMode] = useState("auto");
  const [reasoningModel, setReasoningModel] = useState("");
  const [codingModel, setCodingModel] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [roleOverrides, setRoleOverrides] = useState({});

  const loadModels = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/models`);
      setData(res.data);
      setMode(res.data.config.mode);
      setReasoningModel(res.data.config.reasoning_model);
      setCodingModel(res.data.config.coding_model);
      setOllamaUrl(res.data.config.ollama_url);
      setRoleOverrides(res.data.config.role_overrides || {});
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.post(`${BACKEND_URL}/api/models/config`, {
        mode,
        reasoning_model: reasoningModel,
        coding_model: codingModel,
        ollama_url: ollamaUrl,
        role_overrides: roleOverrides,
      });
      toast.success("Model config saved!");
      loadModels();
    } catch (e) {
      toast.error("Failed to save config");
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async (modelName) => {
    setTesting(modelName);
    setTestResult(null);
    try {
      const res = await axios.get(`${BACKEND_URL}/api/models/test/${encodeURIComponent(modelName)}`);
      setTestResult(res.data);
    } catch (e) {
      setTestResult({ status: "error", detail: "Request failed" });
    } finally {
      setTesting(null);
    }
  };

  const handlePull = async () => {
    if (!pullModel.trim()) return;
    setPulling(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/models/pull`, { model_name: pullModel.trim() });
      toast.success(`Pull started for ${pullModel}`);
      setPullModel("");
      setTimeout(loadModels, 3000);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Pull failed");
    } finally {
      setPulling(false);
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

  const ollamaOk = data?.ollama_available;
  const availableModels = data?.available_models || [];
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
              Ollama &middot; Llama + Qwen Switching
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className={`status-dot ${ollamaOk ? "status-active pulse-dot" : "status-error"}`} />
            <span className={`font-mono text-[10px] uppercase tracking-wider ${ollamaOk ? "text-green-400" : "text-red-400"}`} data-testid="ollama-status">
              Ollama {ollamaOk ? "Connected" : "Offline"}
            </span>
          </div>
          <button
            onClick={loadModels}
            className="btn-secondary px-3 py-1.5 text-xs flex items-center gap-1.5"
            data-testid="refresh-models-btn"
          >
            <RefreshCw className="w-3 h-3" />
            Refresh
          </button>
          <button
            onClick={handleSave}
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
          {/* Connection + Mode */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Ollama URL */}
            <div className="bg-[#111111] border border-[#222222] rounded-sm p-4" data-testid="ollama-url-card">
              <label className="font-mono text-[10px] text-zinc-400 uppercase tracking-widest mb-2 block">
                Ollama Endpoint
              </label>
              <input
                type="text"
                value={ollamaUrl}
                onChange={(e) => setOllamaUrl(e.target.value)}
                className="w-full bg-[#141414] border border-[#222222] focus:border-[#0030FF] focus:ring-1 focus:ring-[#0030FF] rounded-sm text-white px-3 py-2 text-sm font-mono outline-none"
                data-testid="ollama-url-input"
              />
              <p className="text-[10px] text-zinc-600 mt-1.5">
                {ollamaOk
                  ? `Connected. ${availableModels.length} model(s) available.`
                  : "Not reachable. System is in simulation fallback."}
              </p>
            </div>

            {/* Routing Mode */}
            <div className="bg-[#111111] border border-[#222222] rounded-sm p-4" data-testid="routing-mode-card">
              <label className="font-mono text-[10px] text-zinc-400 uppercase tracking-widest mb-2 block">
                Routing Mode
              </label>
              <div className="grid grid-cols-2 gap-2">
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

          {/* Model Assignment */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-[#111111] border border-[#222222] rounded-sm p-4" data-testid="reasoning-model-card">
              <label className="font-mono text-[10px] text-zinc-400 uppercase tracking-widest mb-2 block">
                Reasoning Model (Llama)
              </label>
              <p className="text-[10px] text-zinc-600 mb-2">Used for: CEO, CFO, HR, UX — planning, approvals, dialogue</p>
              <input
                type="text"
                value={reasoningModel}
                onChange={(e) => setReasoningModel(e.target.value)}
                className="w-full bg-[#141414] border border-[#222222] focus:border-[#0030FF] focus:ring-1 focus:ring-[#0030FF] rounded-sm text-white px-3 py-2 text-sm font-mono outline-none"
                placeholder="e.g. llama3.2, mistral, gemma2"
                data-testid="reasoning-model-input"
              />
              <button
                className="mt-2 text-[10px] text-[#0030FF] hover:text-white transition-colors flex items-center gap-1"
                onClick={() => handleTest(reasoningModel)}
                disabled={testing === reasoningModel}
                data-testid="test-reasoning-btn"
              >
                {testing === reasoningModel ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                Test Model
              </button>
            </div>

            <div className="bg-[#111111] border border-[#222222] rounded-sm p-4" data-testid="coding-model-card">
              <label className="font-mono text-[10px] text-zinc-400 uppercase tracking-widest mb-2 block">
                Coding Model (Qwen)
              </label>
              <p className="text-[10px] text-zinc-600 mb-2">Used for: Developer, Frontend, Backend — implementation, debugging</p>
              <input
                type="text"
                value={codingModel}
                onChange={(e) => setCodingModel(e.target.value)}
                className="w-full bg-[#141414] border border-[#222222] focus:border-[#0030FF] focus:ring-1 focus:ring-[#0030FF] rounded-sm text-white px-3 py-2 text-sm font-mono outline-none"
                placeholder="e.g. qwen2.5-coder, codellama, deepseek-coder"
                data-testid="coding-model-input"
              />
              <button
                className="mt-2 text-[10px] text-[#0030FF] hover:text-white transition-colors flex items-center gap-1"
                onClick={() => handleTest(codingModel)}
                disabled={testing === codingModel}
                data-testid="test-coding-btn"
              >
                {testing === codingModel ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                Test Model
              </button>
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
                value="available"
                className="font-mono text-[10px] uppercase tracking-wider data-[state=active]:bg-transparent data-[state=active]:text-white data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-[#0030FF] rounded-none py-3 px-4 text-zinc-500"
                data-testid="tab-available"
              >
                Available Models ({availableModels.length})
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

            {/* Available Models */}
            <TabsContent value="available" className="m-0">
              <div className="space-y-2" data-testid="available-models">
                {/* Pull new model */}
                <div className="bg-[#111111] border border-[#222222] rounded-sm p-3 flex items-center gap-3">
                  <input
                    type="text"
                    value={pullModel}
                    onChange={(e) => setPullModel(e.target.value)}
                    placeholder="Pull model (e.g. llama3.2, qwen2.5-coder)"
                    className="flex-1 bg-[#141414] border border-[#222222] focus:border-[#0030FF] rounded-sm text-white px-3 py-1.5 text-xs font-mono outline-none"
                    data-testid="pull-model-input"
                  />
                  <button
                    onClick={handlePull}
                    disabled={pulling || !pullModel.trim()}
                    className="btn-primary px-3 py-1.5 text-xs flex items-center gap-1.5 disabled:opacity-50"
                    data-testid="pull-model-btn"
                  >
                    {pulling ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                    Pull
                  </button>
                </div>

                {availableModels.length === 0 ? (
                  <div className="text-center py-8">
                    <Cpu className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
                    <p className="text-xs text-zinc-500">
                      {ollamaOk ? "No models found. Pull one to get started." : "Ollama is offline. Start it to see available models."}
                    </p>
                  </div>
                ) : (
                  availableModels.map((m) => (
                    <div key={m.name} className="bg-[#111111] border border-[#222222] rounded-sm p-3 flex items-center justify-between" data-testid={`model-${m.name}`}>
                      <div>
                        <p className="text-xs font-medium text-white font-mono">{m.name}</p>
                        <div className="flex items-center gap-3 mt-0.5">
                          <span className="font-mono text-[9px] text-zinc-500">
                            {(m.size / 1e9).toFixed(1)}GB
                          </span>
                          <span className="font-mono text-[9px] text-zinc-600">{m.digest}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {m.name === reasoningModel && (
                          <span className="font-mono text-[9px] px-1.5 py-0.5 bg-green-500/10 border border-green-500/30 text-green-400 rounded-sm">
                            REASONING
                          </span>
                        )}
                        {m.name === codingModel && (
                          <span className="font-mono text-[9px] px-1.5 py-0.5 bg-blue-500/10 border border-blue-500/30 text-blue-400 rounded-sm">
                            CODING
                          </span>
                        )}
                        <button
                          className="text-[10px] text-[#0030FF] hover:text-white transition-colors flex items-center gap-1"
                          onClick={() => handleTest(m.name)}
                          disabled={testing === m.name}
                        >
                          {testing === m.name ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                          Test
                        </button>
                      </div>
                    </div>
                  ))
                )}
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

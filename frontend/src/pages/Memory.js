import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  Brain,
  Search,
  Plus,
  Zap,
  Trash2,
  Database,
  RefreshCw,
  GitBranch,
  FileText,
  Activity,
  Sparkles,
  HelpCircle
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import axios from "axios";
import { BACKEND_URL } from "@/lib/api";
export default function Memory() {
  const [status, setStatus] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Recall State
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  
  // Remember State
  const [rememberText, setRememberText] = useState("");
  const [remembering, setRemembering] = useState(false);
  
  // Improve State
  const [improving, setImproving] = useState(false);
  
  // Forget State
  const [forgetting, setForgetting] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/cognee/status`);
      setStatus(res.data);
      if (res.data.datasets) {
        setDatasets(res.data.datasets);
      }
    } catch (e) {
      console.error("Failed to load Cognee status", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleRecall = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchResults([]);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/cognee/recall`, {
        query: searchQuery.trim(),
        top_k: 8
      });
      setSearchResults(res.data.results || []);
      if ((res.data.results || []).length === 0) {
        toast.info("No semantic matches found in graph.");
      } else {
        toast.success(`Found ${res.data.results.length} relevant memories.`);
      }
    } catch (err) {
      console.error(err);
      toast.error("Failed to query knowledge graph.");
    } finally {
      setSearching(false);
    }
  };

  const handleRemember = async (e) => {
    e.preventDefault();
    if (!rememberText.trim()) return;
    setRemembering(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/cognee/remember`, {
        text: rememberText.trim()
      });
      if (res.data.status === "stored") {
        toast.success("Memory permanently stored in Cognee!");
        setRememberText("");
        loadStatus();
      } else {
        toast.error("Failed to store memory.");
      }
    } catch (err) {
      console.error(err);
      toast.error("Memory ingestion error.");
    } finally {
      setRemembering(false);
    }
  };

  const handleImprove = async () => {
    setImproving(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/cognee/improve`, {});
      if (res.data.status === "success") {
        toast.success("Graph mapping & Ontario enrichment complete!");
      } else {
        toast.error("Graph improvement failed.");
      }
    } catch (err) {
      console.error(err);
      toast.error("Error optimizing knowledge graph.");
    } finally {
      setImproving(false);
    }
  };

  const handleForget = async (datasetName) => {
    if (!window.confirm(`Are you sure you want to prune memory for dataset "${datasetName || 'rasalilabs'}"?`)) {
      return;
    }
    setForgetting(true);
    try {
      const res = await axios.post(`${BACKEND_URL}/api/cognee/forget`, {
        dataset: datasetName,
        everything: false,
        memory_only: true
      });
      if (res.data.status === "success") {
        toast.success("Graph memory cleared. Source files preserved.");
        loadStatus();
      } else {
        toast.error("Forget request failed.");
      }
    } catch (err) {
      console.error(err);
      toast.error("Error executing forget operation.");
    } finally {
      setForgetting(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-[#0A0A0A]">
        <span className="font-mono text-xs text-zinc-600 typing-indicator">Connecting to Cognee Cloud...</span>
      </div>
    );
  }

  const isConnected = status?.status === "connected";

  return (
    <div className="h-full flex flex-col bg-[#0A0A0A]" data-testid="memory-page">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#222222] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-[#0030FF]/10 border border-[#0030FF]/30 flex items-center justify-center">
            <Brain className="w-4 h-4 text-[#0030FF]" />
          </div>
          <div>
            <h1 className="font-['Chivo'] text-xl font-bold tracking-tight text-white" data-testid="memory-title">
              Cognitive Memory
            </h1>
            <p className="text-xs text-zinc-500 font-mono uppercase tracking-wider">
              Hybrid Graph-Vector Memory &middot; Persistent Knowledge Lifecycle
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 bg-[#111111] px-3 py-1.5 rounded-sm border border-[#222222]">
            <span className={`status-dot ${isConnected ? "status-active pulse-dot" : "status-error"}`} />
            <span className="font-mono text-[10px] uppercase tracking-wider text-white">
              Tenant: {isConnected ? status.tenant_id.slice(0, 8) + "..." : "Offline"}
            </span>
          </div>
          <button
            onClick={loadStatus}
            className="btn-secondary p-1.5 text-zinc-400 hover:text-white"
            title="Refresh status"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-6 space-y-6">
          
          {/* Operations Overview Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-[#111111] border border-[#222222] rounded-sm p-4 relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-24 h-24 bg-[#0030FF]/5 rounded-bl-full pointer-events-none transition-all group-hover:bg-[#0030FF]/10" />
              <div className="flex items-center gap-2 mb-2">
                <Plus className="w-4 h-4 text-[#0030FF]" />
                <span className="font-mono text-[11px] uppercase tracking-wider text-white font-bold">remember()</span>
              </div>
              <p className="text-[11px] text-zinc-400">
                Structures raw text, files, and updates straight into the tenant's permanent graph representation.
              </p>
            </div>

            <div className="bg-[#111111] border border-[#222222] rounded-sm p-4 relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-24 h-24 bg-green-500/5 rounded-bl-full pointer-events-none transition-all group-hover:bg-green-500/10" />
              <div className="flex items-center gap-2 mb-2">
                <Search className="w-4 h-4 text-green-400" />
                <span className="font-mono text-[11px] uppercase tracking-wider text-white font-bold">recall()</span>
              </div>
              <p className="text-[11px] text-zinc-400">
                Traverses relationships and routes searches between semantic vector spaces and cypher subgraphs.
              </p>
            </div>

            <div className="bg-[#111111] border border-[#222222] rounded-sm p-4 relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-24 h-24 bg-yellow-500/5 rounded-bl-full pointer-events-none transition-all group-hover:bg-yellow-500/10" />
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-4 h-4 text-yellow-400" />
                <span className="font-mono text-[11px] uppercase tracking-wider text-white font-bold">improve()</span>
              </div>
              <p className="text-[11px] text-zinc-400">
                Cognifies raw data chunks, builds cross-entity schemas, and adapts semantic nodes.
              </p>
            </div>

            <div className="bg-[#111111] border border-[#222222] rounded-sm p-4 relative overflow-hidden group">
              <div className="absolute top-0 right-0 w-24 h-24 bg-red-500/5 rounded-bl-full pointer-events-none transition-all group-hover:bg-red-500/10" />
              <div className="flex items-center gap-2 mb-2">
                <Trash2 className="w-4 h-4 text-red-400" />
                <span className="font-mono text-[11px] uppercase tracking-wider text-white font-bold">forget()</span>
              </div>
              <p className="text-[11px] text-zinc-400">
                Surgically prunes obsolete documents or entire vector datasets without resetting the ecosystem.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            {/* Left Col: Remember & Improve */}
            <div className="lg:col-span-1 space-y-6">
              
              {/* remember() Panel */}
              <div className="bg-[#111111] border border-[#222222] rounded-sm p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Plus className="w-4 h-4 text-[#0030FF]" />
                  <h3 className="text-xs font-mono uppercase tracking-wider text-white font-bold">Remember Node Ingestion</h3>
                </div>
                <form onSubmit={handleRemember} className="space-y-3">
                  <textarea
                    value={rememberText}
                    onChange={(e) => setRememberText(e.target.value)}
                    placeholder="Enter facts, meeting decisions, or context here... (e.g. 'CEO approved database schema migration on Friday')"
                    rows={4}
                    className="w-full bg-[#141414] border border-[#222222] focus:border-[#0030FF] focus:ring-1 focus:ring-[#0030FF] rounded-sm text-zinc-100 p-3 text-xs outline-none resize-none font-sans"
                  />
                  <button
                    type="submit"
                    disabled={remembering || !rememberText.trim()}
                    className="w-full btn-primary py-2 text-xs flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {remembering ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                    Ingest into Graph
                  </button>
                </form>
              </div>

              {/* improve() Panel */}
              <div className="bg-[#111111] border border-[#222222] rounded-sm p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="w-4 h-4 text-yellow-400" />
                  <h3 className="text-xs font-mono uppercase tracking-wider text-white font-bold">Optimize & Ontologize</h3>
                </div>
                <p className="text-[11px] text-zinc-500 mb-4">
                  Runs the Cognee Ontario parser and cognification pipeline. This triggers semantic classification, entity extraction, and builds relationships from new raw ingestions.
                </p>
                <button
                  onClick={handleImprove}
                  disabled={improving}
                  className="w-full btn-secondary border-yellow-500/20 hover:border-yellow-500/40 text-yellow-400 py-2 text-xs flex items-center justify-center gap-2"
                >
                  {improving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-yellow-400" />}
                  Run improve() / cognify()
                </button>
              </div>

              {/* forget() Panel / Datasets */}
              <div className="bg-[#111111] border border-[#222222] rounded-sm p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Database className="w-4 h-4 text-zinc-400" />
                  <h3 className="text-xs font-mono uppercase tracking-wider text-white font-bold">Active Graph Datasets</h3>
                </div>
                
                <div className="space-y-2">
                  {datasets.length === 0 ? (
                    <p className="text-[11px] text-zinc-600 text-center py-4">No active datasets.</p>
                  ) : (
                    datasets.map((ds) => (
                      <div
                        key={ds.id}
                        className="bg-[#141414] border border-[#222222] rounded-sm p-3 flex items-center justify-between"
                      >
                        <div>
                          <p className="text-xs text-white font-mono">{ds.name}</p>
                          <p className="text-[9px] text-zinc-600 font-mono mt-0.5">
                            Created: {new Date(ds.createdAt).toLocaleDateString()}
                          </p>
                        </div>
                        <button
                          onClick={() => handleForget(ds.name)}
                          disabled={forgetting}
                          className="p-1.5 text-zinc-500 hover:text-red-400 transition-colors"
                          title="Forget dataset memory"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>

            </div>

            {/* Right Col: recall() Interactive Query */}
            <div className="lg:col-span-2 space-y-6">
              
              {/* recall() Search Interface */}
              <div className="bg-[#111111] border border-[#222222] rounded-sm p-4 flex flex-col h-[600px]">
                <div className="flex items-center gap-2 mb-3">
                  <Search className="w-4 h-4 text-green-400" />
                  <h3 className="text-xs font-mono uppercase tracking-wider text-white font-bold">Interactive Memory Recall</h3>
                </div>
                
                <form onSubmit={handleRecall} className="flex gap-2 mb-4">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search query... (e.g. 'What are the developer tasks?' or 'hiring decisions')"
                    className="flex-1 bg-[#141414] border border-[#222222] focus:border-[#0030FF] rounded-sm text-zinc-100 px-3 py-2 text-xs outline-none"
                  />
                  <button
                    type="submit"
                    disabled={searching || !searchQuery.trim()}
                    className="btn-primary px-4 py-2 text-xs flex items-center gap-2 disabled:opacity-50"
                  >
                    {searching ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                    Recall
                  </button>
                </form>

                {/* Search Results Display */}
                <div className="flex-1 overflow-y-auto border border-[#222222] bg-[#141414] rounded-sm p-3 space-y-3">
                  {searching ? (
                    <div className="h-full flex items-center justify-center">
                      <span className="font-mono text-xs text-zinc-600 typing-indicator">Searching graph traversals...</span>
                    </div>
                  ) : searchResults.length === 0 ? (
                    <div className="h-full flex flex-col items-center justify-center text-center p-4">
                      <Brain className="w-8 h-8 text-zinc-700 mb-2" />
                      <p className="text-xs text-zinc-500 font-medium">Memory is ready.</p>
                      <p className="text-[10px] text-zinc-600 max-w-[280px] mt-1">
                        Use recall() above to search the hybrid graph-vector layers for persistent context.
                      </p>
                    </div>
                  ) : (
                    searchResults.map((node, idx) => {
                      const label = node.node_name || node.label || node.id || `Memory Node #${idx + 1}`;
                      const desc = node.node_description || node.text || node.content || node.answer || "";
                      const type = node.node_type || node.source || "Entity";

                      return (
                        <div
                          key={idx}
                          className="bg-[#111111] border border-[#222222] rounded-sm p-3 hover:border-zinc-700 transition-colors"
                        >
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-sm bg-[#0030FF]/10 text-[#0030FF] border border-[#0030FF]/20 uppercase">
                              {type}
                            </span>
                            <h4 className="text-xs font-semibold text-white font-mono truncate">{label}</h4>
                          </div>
                          
                          {desc && (
                            <p className="text-xs text-zinc-400 font-sans leading-relaxed mt-1">
                              {desc}
                            </p>
                          )}

                          {node.relationships && node.relationships.length > 0 && (
                            <div className="mt-2.5 pt-2 border-t border-[#222222] flex flex-wrap gap-1.5">
                              {node.relationships.map((rel, rIdx) => (
                                <div key={rIdx} className="flex items-center gap-1 text-[9px] font-mono text-zinc-500">
                                  <GitBranch className="w-2.5 h-2.5" />
                                  <span>{rel.type}</span>
                                  <span className="text-zinc-400 font-medium">{rel.target}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>

            </div>

          </div>

        </div>
      </ScrollArea>
    </div>
  );
}
